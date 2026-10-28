"""DayTello test voicemail owner delivery utilities.

Feature flags default to off. No change to customer-facing call routing.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

PHONE_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")
TOKEN_LIFETIME_SECONDS = 86400
PRODUCTION_HOST = "chairtime-production-94da.up.railway.app"

def test_link_origin():
    """Require explicit HTTPS testing origin, never issue production-domain links."""
    raw = os.getenv("DAYTELLO_VOICEMAIL_TEST_PUBLIC_ORIGIN", "").strip()
    if not raw:
        raise HTTPException(503, "Test recording link URL is not configured")
    try:
        parsed = urlsplit(raw)
        valid = (
            parsed.scheme == "https"
            and parsed.hostname is not None
            and parsed.hostname.lower() != PRODUCTION_HOST
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
            and parsed.path in ("", "/")
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(503, "Test recording link URL is invalid")
    return raw.rstrip("/")


def owner_phone_for_test_shop(shop_slug, settings=None):
    if os.getenv("DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED") != "true":
        return None
    if os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true":
        raise HTTPException(503, "Test mode is required")
    if settings is not None:
        # A provisioned shop's preference takes precedence; never fall back
        # to a legacy owner number when the owner has disabled notifications.
        if not settings.notifications_enabled:
            return None
        recipient = settings.owner_phone
    else:
        try:
            owner_map = json.loads(os.getenv("DAYTELLO_VOICEMAIL_OWNER_PHONE_MAP", ""))
        except ValueError:
            raise HTTPException(503, "Owner destination map missing")
        recipient = owner_map.get(shop_slug) if isinstance(owner_map, dict) else None
    allowlisted = os.getenv("DAYTELLO_VOICEMAIL_TEST_RECIPIENT", "")
    if not recipient or not PHONE_RE.fullmatch(str(recipient)) or recipient != allowlisted:
        raise HTTPException(503, "Owner SMS recipient is not approved")
    return recipient


def link_cipher():
    key = os.getenv("DAYTELLO_VOICEMAIL_LINK_KEY", "")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError):
        raise HTTPException(503, "Secure voicemail links are not configured")


def make_recording_link(location_id, message_id, shop_id):
    expires = int((datetime.now(timezone.utc) + timedelta(
        seconds=TOKEN_LIFETIME_SECONDS
    )).timestamp())
    data = json.dumps({
        "location": location_id, "message": message_id,
        "shop": shop_id, "expires": expires
    }, separators=(",", ":")).encode("utf-8")
    token = link_cipher().encrypt(data).decode("ascii")
    return test_link_origin() + "/api/daytello/voicemail/listen/" + token


def decode_recording_link(token):
    if not token or len(token) > 2048:
        raise HTTPException(404, "Recording link unavailable")
    try:
        raw = link_cipher().decrypt(token.encode("ascii"))
        payload = json.loads(raw)
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("expires"), int)
            or payload["expires"] < int(datetime.now(timezone.utc).timestamp())
            or any(not isinstance(payload.get(k), str) or not payload[k] for k in
                   ("location", "message", "shop"))
        ):
            raise ValueError("invalid recording link")
        return payload
    except (InvalidToken, ValueError, TypeError, UnicodeError):
        raise HTTPException(404, "Recording link unavailable")
