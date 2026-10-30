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


def approved_test_recipient(shop_slug, recipient):
    """Validate an owner's number against an explicit shop-specific test allowlist.

    This validation also works while SMS is disabled, so an owner may save
    their number for later activation without prematurely sending messages.
    """
    if os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true":
        raise HTTPException(503, "Test mode is required")
    raw_approvals = os.getenv("DAYTELLO_VOICEMAIL_TEST_RECIPIENT_MAP", "").strip()
    if raw_approvals:
        try:
            approvals = json.loads(raw_approvals)
        except ValueError:
            raise HTTPException(503, "Test recipient approvals are invalid")
        if not isinstance(approvals, dict) or any(
            not isinstance(slug, str)
            or not isinstance(number, str)
            or not PHONE_RE.fullmatch(number)
            for slug, number in approvals.items()
        ):
            raise HTTPException(503, "Test recipient approvals are invalid")
        allowlisted = approvals.get(shop_slug)
    else:
        allowlisted = os.getenv("DAYTELLO_VOICEMAIL_TEST_RECIPIENT", "")
    if not recipient or not PHONE_RE.fullmatch(str(recipient)) or recipient != allowlisted:
        raise HTTPException(503, "Owner SMS recipient is not approved")
    return recipient


def approved_owner_recipient(shop_slug, recipient, *, db=None, shop_id=None):
    """Allow a stored, verified owner phone without a per-shop env map.

    Existing test allowlists remain the default until the platform-wide
    verification feature is deliberately enabled. Never fall back to the
    allowlist if verification is enabled but the proof is missing.
    """
    if os.getenv("DAYTELLO_VOICEMAIL_OWNER_VERIFICATION_ENABLED") == "true":
        if db is None or not shop_id:
            raise HTTPException(503, "Owner SMS verification context unavailable")
        from app.voicemail_owner_verification import verified_owner_recipient
        return verified_owner_recipient(db, shop_id, recipient)
    return approved_test_recipient(shop_slug, recipient)


def owner_phone_for_test_shop(shop_slug, settings=None, *, db=None, shop_id=None):
    if os.getenv("DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED") != "true":
        return None
    if os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true":
        raise HTTPException(503, "Test mode is required")
    if settings is not None:
        # Never send for an unapproved or disabled shop preference.
        if not settings.notifications_enabled:
            return None
        recipient = settings.owner_phone
    else:
        try:
            owner_map = json.loads(os.getenv("DAYTELLO_VOICEMAIL_OWNER_PHONE_MAP", ""))
        except ValueError:
            raise HTTPException(503, "Owner destination map missing")
        recipient = owner_map.get(shop_slug) if isinstance(owner_map, dict) else None
    return approved_owner_recipient(
        shop_slug, recipient, db=db,
        shop_id=shop_id or (settings.shop_id if settings is not None else None),
    )


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
