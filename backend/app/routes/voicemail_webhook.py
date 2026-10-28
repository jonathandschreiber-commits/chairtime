"""Receive signed HighLevel voicemail events. Intentionally sends no SMS.

This is a test-only ingestion feature. Routing is fail-closed: each dedicated
voicemail number must have an explicit shop mapping in an environment variable.
An OAuth Marketplace installation and real signed-event test are still needed.
"""
import base64
import binascii
import json
import os
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop
from app.voicemail_models import DayTelloVoicemailEvent, DayTelloVoicemailShopSettings
from app.voicemail_owner_links import owner_phone_for_test_shop
from app.routes.voicemail_owner_alert import send_owner_voicemail_alert

router = APIRouter()

# Official HighLevel Ed25519 webhook public key. Public, NOT a secret.
# https://marketplace.gohighlevel.com/docs/2021-07-28/webhook/WebhookIntegrationGuide/
GHL_WEBHOOK_ED25519_PUBLIC_KEY = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEAi2HR1srL4o18O8BRa7gVJY7G7bupbN3H9AwJrHCDiOg=\n"
    "-----END PUBLIC KEY-----\n"
)
MAX_WEBHOOK_SIZE = 64 * 1024
_PHONE = re.compile(r"^\+[1-9][0-9]{7,14}$")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def valid_phone(value):
    """Reject malformed addresses rather than guessing a telephone number."""
    return isinstance(value, str) and bool(_PHONE.fullmatch(value.strip()))


def verify_ghl_signature(body: bytes, signature_header: str | None) -> bool:
    """Verify the exact received bytes, never a re-serialized JSON object."""
    if not signature_header or signature_header == "N/A":
        return False
    try:
        signature = base64.b64decode(signature_header, validate=True)
        if len(signature) != 64:
            return False
        key = serialization.load_pem_public_key(
            GHL_WEBHOOK_ED25519_PUBLIC_KEY.encode("ascii")
        )
        key.verify(signature, body)
        return True
    except (ValueError, TypeError, binascii.Error, InvalidSignature):
        return False


def configured_routing_map() -> dict:
    """Mapping: E.164 voicemail destination -> exclusive DayTello shop slug."""
    raw = os.getenv("DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP", "").strip()
    if not raw:
        raise HTTPException(503, "Voicemail number routing is not configured")
    try:
        mapping = json.loads(raw)
    except (ValueError, TypeError):
        raise HTTPException(503, "Voicemail routing configuration invalid")
    if not isinstance(mapping, dict) or not mapping:
        raise HTTPException(503, "Voicemail routing configuration invalid")
    seen_shops = set()
    for number, slug in mapping.items():
        if (
            not valid_phone(number)
            or not isinstance(slug, str)
            or not _SLUG.fullmatch(slug)
            or slug in seen_shops
        ):
            raise HTTPException(503, "Voicemail routing configuration invalid")
        seen_shops.add(slug)
    return mapping


def is_voicemail_event(payload: dict) -> bool:
    """HighLevel sends a voicemail as CALL with status=voicemail."""
    return (
        payload.get("type") == "InboundMessage"
        and str(payload.get("direction", "")).lower() == "inbound"
        and str(payload.get("status", "")).lower() == "voicemail"
        and payload.get("messageTypeString") in ("TYPE_CALL", "TYPE_VOICEMAIL")
    )


@router.post("/daytello/voicemail", status_code=200)
async def receive_voicemail(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # The current Ed25519 header is mandatory. Legacy RSA is not accepted.
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_WEBHOOK_SIZE:
                raise HTTPException(413, "Webhook too large")
        except ValueError:
            raise HTTPException(400, "Invalid Content-Length")
    body = await request.body()
    if len(body) > MAX_WEBHOOK_SIZE:
        raise HTTPException(413, "Webhook too large")
    if not verify_ghl_signature(body, request.headers.get("x-ghl-signature")):
        raise HTTPException(401, "Invalid webhook signature")

    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid webhook JSON")
    if not isinstance(payload, dict):
        raise HTTPException(400, "Invalid webhook event")
    if not is_voicemail_event(payload):
        # HighLevel sends all inbound message types under this subscription.
        return {"accepted": True, "action": "ignored_non_voicemail"}

    expected_location = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    location_id = payload.get("locationId")
    if not expected_location:
        raise HTTPException(503, "HighLevel location is not configured")
    if not isinstance(location_id, str) or location_id != expected_location:
        # Never record or forward events from another HighLevel location.
        return {"accepted": True, "action": "ignored_other_location"}

    destination = payload.get("to")
    message_id = payload.get("messageId")
    if not valid_phone(destination) or not isinstance(message_id, str):
        raise HTTPException(422, "Voicemail event missing identifiers")
    if not message_id.strip() or len(message_id) > 128:
        raise HTTPException(422, "Invalid message identifier")
    # Explicit database binding takes precedence. Legacy routing stays
    # available only for shops not yet provisioned into the database.
    settings = db.query(DayTelloVoicemailShopSettings).filter(
        DayTelloVoicemailShopSettings.location_id == location_id,
        DayTelloVoicemailShopSettings.receiving_number == destination,
    ).one_or_none()
    if settings is not None:
        shop = db.query(Shop).filter(Shop.id == settings.shop_id).first()
        # During migration, both the old environment mapping and the new
        # database route may exist. They must never disagree about ownership:
        # a stale legacy number must not silently move to another tenant.
        legacy_raw = os.getenv("DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP", "").strip()
        if legacy_raw:
            legacy_slug = configured_routing_map().get(destination)
            if legacy_slug and shop and legacy_slug != shop.slug:
                raise HTTPException(503, "Conflicting voicemail shop assignments")
    else:
        routing = configured_routing_map()
        shop_slug = routing.get(destination)
        if not shop_slug:
            return {"accepted": True, "action": "ignored_unmapped_number"}
        shop = db.query(Shop).filter(Shop.slug == shop_slug).first()
        if shop and db.get(DayTelloVoicemailShopSettings, shop.id) is not None:
            # The shop has already migrated to its database voicemail route.
            # Do not continue receiving on an old, reassigned legacy number.
            raise HTTPException(503, "Stale legacy voicemail assignment")
    if not shop or not shop.ai_voice_enabled:
        return {"accepted": True, "action": "ignored_inactive_shop"}
    if shop.highlevel_location_id and shop.highlevel_location_id != location_id:
        return {"accepted": True, "action": "ignored_location_mismatch"}

    recipient = owner_phone_for_test_shop(shop.slug, settings) if shop else None
    event = DayTelloVoicemailEvent(
        location_id=location_id,
        message_id=message_id,
        shop_id=shop.id,
        receiving_number=destination,
        notification_status="queued" if recipient else "disabled",
    )
    try:
        db.add(event)
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"accepted": True, "action": "duplicate"}
    if recipient:
        background_tasks.add_task(
            send_owner_voicemail_alert, location_id, message_id,
            shop.slug, shop.name, shop.id, payload.get("from")
        )
        return {"accepted": True, "action": "queued_owner_notification"}
    return {"accepted": True, "action": "recorded_no_notification"}
