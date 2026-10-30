"""Isolated, disabled-by-default programmable voice webhook routes.

No production number is redirected to these routes. Shop identification comes
from an exclusive database DID binding, never from a caller-supplied slug.
"""
import os
import re
from urllib.parse import urlsplit

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop
from app.voice_relay_models import DayTelloVoiceRelayAssignment
from app.voice_relay_security import verify_voice_provider_signature
from app.voice_relay_twiml import (
    forward_to_employee, after_employee_dial, completed_recording,
)
from app.voicemail_models import DayTelloVoicemailShopSettings
from app.voice_relay_delivery import (
    router as relay_recording_router, remember_relay_call,
    recorded_call_for_callback, accept_completed_recording,
    send_relay_owner_alert,
)

router = APIRouter()
router.include_router(relay_recording_router)
E164 = re.compile(r"^\+1[2-9][0-9]{2}[2-9][0-9]{6}$")
SID = re.compile(r"^CA[a-fA-F0-9]{32}$")


def _enabled():
    if os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true":
        raise HTTPException(404, "Unavailable")
    if not os.getenv("DAYTELLO_VOICE_RELAY_AUTH_TOKEN"):
        raise HTTPException(503, "Voice relay credentials unavailable")


def _origin() -> str:
    origin = os.getenv("DAYTELLO_VOICE_RELAY_PUBLIC_ORIGIN", "").rstrip("/")
    # Treat the configured public origin as a security boundary: reject
    # userinfo, malformed ports, control characters and URL components that
    # could alter the exact URL used for provider signature verification.
    try:
        u = urlsplit(origin)
        valid_port = u.port is None or 1 <= u.port <= 65535
    except ValueError:
        raise HTTPException(503, "Voice relay origin unavailable")
    if (not origin or origin != origin.strip() or
            any(ord(c) < 33 or ord(c) == 127 or c == "\\" for c in origin) or
            u.scheme != "https" or not u.hostname or
            u.username is not None or u.password is not None or
            not valid_port or u.path or u.query or u.fragment):
        raise HTTPException(503, "Voice relay origin unavailable")
    return origin


async def _verified(request: Request):
    _enabled()
    body = await request.body()
    if len(body) > 8192:
        raise HTTPException(413, "Voice callback too large")
    # Never accept lookalike MIME types or an encoding we do not decode.
    # Signed fields must be interpreted identically by us and the provider.
    content_type = request.headers.get("content-type", "")
    media_type, _, parameters = content_type.partition(";")
    if (media_type.strip().lower() != "application/x-www-form-urlencoded" or
            parameters.strip().lower() not in ("", "charset=utf-8", 'charset="utf-8"')):
        raise HTTPException(415, "Voice callback must be UTF-8 form encoded")
    from urllib.parse import parse_qsl
    try:
        parts = parse_qsl(
            body.decode("utf-8"), keep_blank_values=True, strict_parsing=True,
            encoding="utf-8", errors="strict", max_num_fields=64,
        )
    except (UnicodeError, ValueError):
        raise HTTPException(400, "Invalid voice callback")
    if len(parts) != len(set(k for k, _ in parts)):
        raise HTTPException(400, "Duplicate voice callback fields")
    fields = dict(parts)
    origin = _origin()
    url = origin + request.url.path
    if request.url.query:
        url += "?" + request.url.query
    if not verify_voice_provider_signature(
        url, fields, request.headers.get("x-twilio-signature", ""),
        os.environ["DAYTELLO_VOICE_RELAY_AUTH_TOKEN"],
    ):
        raise HTTPException(401, "Invalid voice provider signature")
    if not SID.fullmatch(fields.get("CallSid", "")):
        raise HTTPException(422, "Invalid call identifier")
    return fields, origin


def _assignment(db, did):
    if not E164.fullmatch(did or ""):
        raise HTTPException(422, "Invalid destination")
    binding = db.query(DayTelloVoiceRelayAssignment).filter(
        DayTelloVoiceRelayAssignment.relay_number == did
    ).one_or_none()
    if binding is None or not binding.enabled:
        raise HTTPException(404, "Voice number is not provisioned")
    shop = db.query(Shop).filter(Shop.id == binding.shop_id).one_or_none()
    settings = db.get(DayTelloVoicemailShopSettings, binding.shop_id)
    if (not shop or not shop.ai_voice_enabled or not settings or
            not settings.owner_phone or not E164.fullmatch(settings.owner_phone)):
        raise HTTPException(409, "Shop call routing is incomplete")
    # The enabled relay DID must still be the shop's saved voicemail DID.
    # Reject stale or cross-location settings before dialing an employee,
    # creating a recording, or accepting a recording-status callback.
    expected_location = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    if (settings.receiving_number != binding.relay_number or
            not expected_location or
            settings.location_id != expected_location or
            shop.highlevel_location_id != expected_location):
        raise HTTPException(409, "Shop relay route and location do not match")
    # A relay DID must never forward to itself or another shop's relay DID.
    # Reject even disabled assignments: those numbers could later be enabled.
    if settings.owner_phone == did:
        raise HTTPException(409, "Voicemail forwarding loop detected")
    another_relay = db.query(DayTelloVoiceRelayAssignment).filter(
        DayTelloVoiceRelayAssignment.relay_number == settings.owner_phone
    ).one_or_none()
    if another_relay is not None:
        raise HTTPException(409, "Forwarding to a relay DID is not permitted")
    # A HighLevel voicemail DID is also a routing destination even when it
    # is not registered in the separate programmable relay assignment table.
    # Forwarding to one could create a loop or cross-tenant call disclosure.
    voicemail_destination = db.query(DayTelloVoicemailShopSettings).filter(
        DayTelloVoicemailShopSettings.receiving_number == settings.owner_phone
    ).first()
    if voicemail_destination is not None:
        raise HTTPException(409, "Forwarding to a voicemail DID is not permitted")
    # The AI receptionist's own inbound number is another possible loop,
    # including numbers belonging to a different tenant. Never send the
    # employee leg into any shop's AI receptionist.
    ai_destination = db.query(Shop).filter(
        Shop.highlevel_phone_number == settings.owner_phone
    ).first()
    if ai_destination is not None:
        raise HTTPException(409, "Forwarding to an AI receptionist number is not permitted")
    # A published business line may forward back into an AI agent even for
    # this same shop. Block both same-shop recursion and cross-shop disclosure.
    business_destination = db.query(Shop).filter(
        Shop.phone == settings.owner_phone,
    ).first()
    if business_destination is not None:
        raise HTTPException(409, "Forwarding to a business routing number is not permitted")
    return binding, settings


def _xml(value):
    return Response(content=value, media_type="application/xml",
                    headers={"Cache-Control": "no-store"})


@router.post("/daytello/voice-relay/inbound")
async def relay_inbound(request: Request, db: Session = Depends(get_db)):
    fields, origin = await _verified(request)
    binding, settings = _assignment(db, fields.get("To"))
    remember_relay_call(db, fields, binding)
    return _xml(forward_to_employee(
        settings.owner_phone, origin + "/api/daytello/voice-relay/dial-finished",
    ))


@router.post("/daytello/voice-relay/dial-finished")
async def relay_dial_finished(request: Request, db: Session = Depends(get_db)):
    fields, origin = await _verified(request)
    # Every callback must belong to an inbound CallSid we previously stored.
    # A signed provider request with a plausible To alone is not a tenant
    # binding: never start voicemail for an unrelated or unknown call.
    call = recorded_call_for_callback(db, fields)
    _assignment(db, call.relay_number)
    status = fields.get("DialCallStatus", "")
    try:
        xml = after_employee_dial(
            status,
            origin + "/api/daytello/voice-relay/record-finished",
            origin + "/api/daytello/voice-relay/record-ready",
        )
    except ValueError:
        raise HTTPException(422, "Invalid dial completion")
    return _xml(xml)


@router.post("/daytello/voice-relay/record-finished")
async def relay_record_finished(request: Request, db: Session = Depends(get_db)):
    fields, _ = await _verified(request)
    # Every callback must belong to an inbound CallSid we previously stored.
    # A signed provider request with a plausible To alone is not a tenant
    # binding: never start voicemail for an unrelated or unknown call.
    call = recorded_call_for_callback(db, fields)
    _assignment(db, call.relay_number)
    return _xml(completed_recording())


@router.post("/daytello/voice-relay/record-ready")
async def relay_record_ready(request: Request, background_tasks: BackgroundTasks,
                             db: Session = Depends(get_db)):
    """Deduplicate a signed completed recording before scheduling owner SMS."""
    fields, _ = await _verified(request)
    # Twilio recording status callbacks need not include the original To.
    # Never use an arbitrary callback destination as tenant identity.
    call = recorded_call_for_callback(db, fields)
    binding, settings = _assignment(db, call.relay_number)
    if binding.shop_id != call.shop_id:
        raise HTTPException(409, "Voice call tenant assignment changed")
    if fields.get("RecordingStatus") != "completed":
        return {"accepted": True, "notification_sent": False,
                "action": "ignored_non_completed"}
    action, recording_sid = accept_completed_recording(db, fields, binding, settings)
    if recording_sid:
        background_tasks.add_task(send_relay_owner_alert, recording_sid)
    return {"accepted": True, "notification_sent": False, "action": action}
