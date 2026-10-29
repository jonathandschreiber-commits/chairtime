"""Isolated, disabled-by-default programmable voice webhook routes.

No production number is redirected to these routes. Shop identification comes
from an exclusive database DID binding, never from a caller-supplied slug.
"""
import os
import re
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop
from app.voice_relay_models import DayTelloVoiceRelayAssignment
from app.voice_relay_security import verify_voice_provider_signature
from app.voice_relay_twiml import (
    forward_to_employee, after_employee_dial, completed_recording,
)
from app.voicemail_models import DayTelloVoicemailShopSettings

router = APIRouter()
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
    if "application/x-www-form-urlencoded" not in request.headers.get("content-type", ""):
        raise HTTPException(415, "Voice callback must be form encoded")
    from urllib.parse import parse_qsl
    try:
        parts = parse_qsl(body.decode("utf-8"), keep_blank_values=True, strict_parsing=True)
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
    # A relay DID must never forward to itself or another shop's relay DID.
    # Reject even disabled assignments: those numbers could later be enabled.
    if settings.owner_phone == did:
        raise HTTPException(409, "Voicemail forwarding loop detected")
    another_relay = db.query(DayTelloVoiceRelayAssignment).filter(
        DayTelloVoiceRelayAssignment.relay_number == settings.owner_phone
    ).one_or_none()
    if another_relay is not None:
        raise HTTPException(409, "Forwarding to a relay DID is not permitted")
    return binding, settings


def _xml(value):
    return Response(content=value, media_type="application/xml",
                    headers={"Cache-Control": "no-store"})


@router.post("/daytello/voice-relay/inbound")
async def relay_inbound(request: Request, db: Session = Depends(get_db)):
    fields, origin = await _verified(request)
    _, settings = _assignment(db, fields.get("To"))
    return _xml(forward_to_employee(
        settings.owner_phone, origin + "/api/daytello/voice-relay/dial-finished",
    ))


@router.post("/daytello/voice-relay/dial-finished")
async def relay_dial_finished(request: Request, db: Session = Depends(get_db)):
    fields, origin = await _verified(request)
    _assignment(db, fields.get("To"))
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
    _assignment(db, fields.get("To"))
    return _xml(completed_recording())


@router.post("/daytello/voice-relay/record-ready")
async def relay_record_ready(request: Request, db: Session = Depends(get_db)):
    """Do not text yet. Recording storage and delivery integration is pending."""
    fields, _ = await _verified(request)
    _assignment(db, fields.get("To"))
    if fields.get("RecordingStatus") != "completed":
        return {"accepted": True, "notification_sent": False}
    if not re.fullmatch(r"RE[a-fA-F0-9]{32}", fields.get("RecordingSid", "")):
        raise HTTPException(422, "Invalid recording identifier")
    return {"accepted": True, "notification_sent": False,
            "reason": "Recording delivery integration not enabled"}
