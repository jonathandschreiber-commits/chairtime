"""Test-only programmable voice recording delivery and shop-scoped playback.

Twilio RecordingSids are not HighLevel message IDs. Persist the signed voice
call's DID binding and each completed recording before scheduling owner SMS.
No provider numbers, telephone routing or deployment settings are changed.
"""
import hashlib
import hmac
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import Column, DateTime, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func

from app.database import Base, SessionLocal
from app.models import Shop
from app.routes.reminders import send_highlevel_sms
from app.voice_relay_models import DayTelloVoiceRelayAssignment
from app.voice_relay_recordings import verified_recording_reference, verified_recording_url
from app.voicemail_models import DayTelloVoicemailShopSettings
from app.voicemail_owner_links import (
    decode_recording_link, link_cipher, owner_phone_for_test_shop, test_link_origin,
)

router = APIRouter()
logger = logging.getLogger(__name__)
CALL = re.compile(r"^CA[a-fA-F0-9]{32}$")
MAX_AUDIO_BYTES = 15 * 1024 * 1024
# Recovery must not compete with normal post-callback background dispatch.
RECOVERY_MIN_AGE = timedelta(minutes=5)


class DayTelloVoiceRelayCall(Base):
    """Durable signed inbound CallSid -> tenant/DID association."""
    __tablename__ = "daytello_voice_relay_calls"
    call_sid = Column(String(34), primary_key=True)
    account_sid = Column(String(34), nullable=False)
    shop_id = Column(String(128), nullable=False, index=True)
    relay_number = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class DayTelloVoiceRelayRecording(Base):
    """One SMS attempt per completed recording; duplicate callbacks are safe."""
    __tablename__ = "daytello_voice_relay_recordings"
    recording_sid = Column(String(34), primary_key=True)
    account_sid = Column(String(34), nullable=False)
    call_sid = Column(String(34), nullable=False)
    shop_id = Column(String(128), nullable=False, index=True)
    relay_number = Column(String(20), nullable=False)
    notification_status = Column(String(24), nullable=False, default="disabled")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


def remember_relay_call(db, fields, binding):
    """Persist the only tenant that can receive callbacks for this CallSid."""
    call_sid = fields["CallSid"]
    account_sid = fields.get("AccountSid", "")
    configured = os.getenv("DAYTELLO_VOICE_RELAY_ACCOUNT_SID", "").strip()
    if not configured or not re.fullmatch(r"AC[a-fA-F0-9]{32}", configured):
        raise HTTPException(503, "Voice provider account is not configured")
    if account_sid != configured:
        raise HTTPException(403, "Voice provider account mismatch")
    existing = db.get(DayTelloVoiceRelayCall, call_sid)
    if existing:
        if (existing.shop_id != binding.shop_id or
                existing.relay_number != binding.relay_number or
                existing.account_sid != account_sid):
            raise HTTPException(409, "Voice call belongs to a different route")
        return existing
    call = DayTelloVoiceRelayCall(
        call_sid=call_sid, account_sid=account_sid,
        shop_id=binding.shop_id, relay_number=binding.relay_number,
    )
    db.add(call)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Voice call was assigned concurrently")
    return call


def recorded_call_for_callback(db, fields):
    """Recording callbacks may omit To: use signed CallSid and stored DID."""
    call_sid = fields.get("CallSid", "")
    if not CALL.fullmatch(call_sid):
        raise HTTPException(422, "Invalid call identifier")
    call = db.get(DayTelloVoiceRelayCall, call_sid)
    if not call:
        raise HTTPException(404, "Unknown voice call")
    if fields.get("AccountSid") != call.account_sid:
        raise HTTPException(403, "Voice provider account mismatch")
    if fields.get("To") and fields["To"] != call.relay_number:
        raise HTTPException(409, "Voice callback destination mismatch")
    return call


def make_relay_recording_link(recording, recipient):
    """Purpose-bound link expires in 24 hours and is revoked on owner phone change."""
    if not isinstance(recipient, str) or not re.fullmatch(r"\+1[2-9][0-9]{2}[2-9][0-9]{6}", recipient):
        raise HTTPException(409, "Verified owner recipient required")
    expires = int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
    payload = {
        "purpose": "voice-relay",
        "location": recording.account_sid,
        "message": recording.recording_sid,
        "shop": recording.shop_id,
        "recipient_hash": hashlib.sha256(recipient.encode("ascii")).hexdigest(),
        "expires": expires,
    }
    token = link_cipher().encrypt(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    return test_link_origin() + "/api/daytello/voice-relay/listen/" + token


def accept_completed_recording(db, fields, binding, settings):
    """Signed callback -> exclusive recording receipt; no SMS in request path."""
    account_sid, recording_sid = verified_recording_reference(
        fields, os.getenv("DAYTELLO_VOICE_RELAY_ACCOUNT_SID", "").strip(),
    )
    if fields.get("RecordingUrl"):
        verified_recording_url(fields["RecordingUrl"], account_sid, recording_sid)
    call = recorded_call_for_callback(db, fields)
    if (call.shop_id != binding.shop_id or call.relay_number != binding.relay_number):
        raise HTTPException(409, "Voice call tenant assignment changed")
    shop = db.get(Shop, call.shop_id)
    if not shop or not shop.ai_voice_enabled:
        raise HTTPException(409, "Voice call shop is inactive")
    expected_location = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    if not expected_location or shop.highlevel_location_id != expected_location:
        raise HTTPException(409, "SMS provider location mismatch")
    recipient = owner_phone_for_test_shop(shop.slug, settings, db=db, shop_id=shop.id)
    receipt = DayTelloVoiceRelayRecording(
        recording_sid=recording_sid, account_sid=account_sid,
        call_sid=call.call_sid, shop_id=call.shop_id,
        relay_number=call.relay_number,
        notification_status="queued" if recipient else "disabled",
    )
    db.add(receipt)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(DayTelloVoiceRelayRecording, recording_sid)
        if (existing and existing.shop_id == call.shop_id and
                existing.call_sid == call.call_sid and
                existing.account_sid == account_sid):
            return "duplicate", None
        raise HTTPException(409, "Recording belongs to a different call")
    return ("queued" if recipient else "disabled"), recording_sid if recipient else None


def relay_receipt_route_is_current(receipt, shop, settings, binding) -> bool:
    """Recheck tenant DID and location before SMS or recording playback.

    A recording callback can queue an alert before the owner changes a shop's
    voicemail number or HighLevel location. Never deliver against stale state.
    """
    expected_location = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    # An alert may have been queued before the relay provider account was
    # rotated. Never text a link for an old account: playback would reject it
    # and the recording may no longer be accessible to this installation.
    expected_account = os.getenv("DAYTELLO_VOICE_RELAY_ACCOUNT_SID", "").strip()
    return bool(
        expected_account and receipt.account_sid == expected_account and
        expected_location and shop and shop.ai_voice_enabled and
        settings and binding and binding.enabled and
        binding.shop_id == receipt.shop_id and
        binding.relay_number == receipt.relay_number and
        settings.receiving_number == receipt.relay_number and
        settings.location_id == expected_location and
        shop.highlevel_location_id == expected_location
    )


def _relay_sms_authorized(*, recovery=False):
    """Recovery permission is independent of ordinary callback SMS delivery."""
    return bool(
        os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") == "true" and
        os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") == "true" and
        os.getenv("DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED") == "true" and
        (not recovery or
         os.getenv("DAYTELLO_VOICE_RELAY_RECOVERY_WORKER_ENABLED") == "true")
    )


def send_relay_owner_alert(recording_sid, *, recovery=False):
    """Claim one SMS attempt atomically before any provider I/O.

    Duplicate background tasks may execute in separate workers. The durable
    queued -> sending transition prevents two workers from sending the same
    recording. Do not automatically retry an interrupted or ambiguous attempt:
    the provider might already have accepted the message.
    """
    # A queued background task may outlive a test-mode shutdown. Never claim
    # a receipt or send an owner SMS after the relay is explicitly disabled.
    if not _relay_sms_authorized(recovery=recovery):
        return
    with SessionLocal() as db:
        claimed = db.query(DayTelloVoiceRelayRecording).filter_by(
            recording_sid=recording_sid, notification_status="queued",
        ).update({"notification_status": "sending"}, synchronize_session=False)
        db.commit()
        if claimed != 1:
            return
    status = "failed"
    try:
        with SessionLocal() as db:
            receipt = db.get(DayTelloVoiceRelayRecording, recording_sid)
            if not receipt or receipt.notification_status != "sending":
                return
            shop = db.get(Shop, receipt.shop_id)
            settings = db.get(DayTelloVoicemailShopSettings, receipt.shop_id)
            binding = db.get(DayTelloVoiceRelayAssignment, receipt.shop_id)
            if not relay_receipt_route_is_current(receipt, shop, settings, binding):
                return
            recipient = owner_phone_for_test_shop(shop.slug, settings, db=db, shop_id=shop.id)
            if not recipient:
                return
            link = make_relay_recording_link(receipt, recipient)
            # Recheck immediately before provider I/O: a flag may be disabled
            # while the worker was validating the saved shop/recipient state.
            if not _relay_sms_authorized(recovery=recovery):
                return
            result = send_highlevel_sms(
                recipient, f"DayTello TEST: New voicemail for {shop.name}. Listen: {link}",
                shop_id=shop.id, shop_slug=shop.slug,
                purpose="voicemail-owner-notification", source_id=recording_sid,
            )
            status = "sent" if result.get("success") else "failed"
    except Exception:
        logger.exception("DayTello programmable voice owner SMS failed")
    finally:
        with SessionLocal() as db:
            receipt = db.get(DayTelloVoiceRelayRecording, recording_sid)
            if receipt and receipt.notification_status == "sending":
                receipt.notification_status = status
                db.commit()



def _eligible_queued_relay_sids(*, shop_id, limit):
    """Read a bounded, tenant-scoped snapshot of safely aged queued receipts."""
    if not isinstance(shop_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", shop_id):
        raise ValueError("Recovery requires an exact valid shop ID")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Recovery batch size must be between 1 and 100")
    # DateTime columns are timezone-naive UTC in the existing database.
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - RECOVERY_MIN_AGE
    with SessionLocal() as db:
        pending = db.query(DayTelloVoiceRelayRecording).filter_by(
            notification_status="queued", shop_id=shop_id,
        ).filter(
            DayTelloVoiceRelayRecording.created_at <= cutoff,
        ).order_by(
            DayTelloVoiceRelayRecording.created_at,
            DayTelloVoiceRelayRecording.recording_sid,
        ).limit(limit).all()
        return [item.recording_sid for item in pending]


def preview_queued_relay_alerts(*, shop_id, limit=25):
    """Read-only count for an isolated test operator; never contacts SMS provider.

    The result is capped at limit and represents a snapshot, not a guarantee
    that a subsequent recovery will claim or deliver the same receipts.
    """
    if (os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true" or
            os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true"):
        raise PermissionError("Recovery preview requires isolated test mode")
    return len(_eligible_queued_relay_sids(shop_id=shop_id, limit=limit))


def recover_queued_relay_alerts(*, shop_id, limit=25):
    """Explicit test-only recovery for alerts stranded before task dispatch.

    An operator-controlled worker may invoke this bounded helper later. It
    does not schedule itself or activate SMS. Only receipts queued for at
    least five minutes qualify. Atomic claiming prevents duplicate sends,
    and failed or ambiguous attempts are never retried automatically.
    """
    if (os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true" or
            os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true" or
            os.getenv("DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED") != "true" or
            os.getenv("DAYTELLO_VOICE_RELAY_RECOVERY_WORKER_ENABLED") != "true"):
        return 0
    recording_sids = _eligible_queued_relay_sids(shop_id=shop_id, limit=limit)
    examined = 0
    for recording_sid in recording_sids:
        # An operator may revoke recovery authorization while a batch runs.
        # Stop before examining another receipt, even if ordinary SMS delivery
        # remains enabled. The delivery helper separately rechecks SMS flags.
        if (os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true" or
                os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true" or
                os.getenv("DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED") != "true" or
                os.getenv("DAYTELLO_VOICE_RELAY_RECOVERY_WORKER_ENABLED") != "true"):
            break
        # The execution flag may be revoked after the batch-level check;
        # delivery rechecks it before claiming and before provider I/O.
        send_relay_owner_alert(recording_sid, recovery=True)
        examined += 1
    return examined

@router.get("/daytello/voice-relay/listen/{token}")
async def listen_to_relay_recording(token: str):
    """Authenticate the owner bearer link and proxy bounded provider audio."""
    if (os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true" or
            os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true"):
        raise HTTPException(404, "Recording link unavailable")
    payload = decode_recording_link(token)
    if payload.get("purpose") != "voice-relay":
        raise HTTPException(404, "Recording link unavailable")
    account_sid, recording_sid, shop_id = (
        payload["location"], payload["message"], payload["shop"],
    )
    verified_recording_reference(
        {"AccountSid": account_sid, "RecordingSid": recording_sid},
        os.getenv("DAYTELLO_VOICE_RELAY_ACCOUNT_SID", "").strip(),
    )
    with SessionLocal() as db:
        receipt = db.get(DayTelloVoiceRelayRecording, recording_sid)
        shop = db.get(Shop, shop_id)
        binding = db.get(DayTelloVoiceRelayAssignment, shop_id)
        settings = db.get(DayTelloVoicemailShopSettings, shop_id)
        if (not receipt or receipt.account_sid != account_sid or
                receipt.shop_id != shop_id or
                not relay_receipt_route_is_current(receipt, shop, settings, binding)):
            raise HTTPException(404, "Recording link unavailable")
        # Revocation must apply to previously issued links too: opting out,
        # losing consent, or changing the approved owner number denies playback.
        recipient = owner_phone_for_test_shop(shop.slug, settings, db=db, shop_id=shop.id)
        fingerprint = payload.get("recipient_hash")
        if (not recipient or not isinstance(fingerprint, str) or
                not hmac.compare_digest(hashlib.sha256(recipient.encode("ascii")).hexdigest(), fingerprint)):
            raise HTTPException(404, "Recording link unavailable")
    key_sid = os.getenv("DAYTELLO_VOICE_RELAY_API_KEY_SID", "").strip()
    key_secret = os.getenv("DAYTELLO_VOICE_RELAY_API_KEY_SECRET", "").strip()
    if not re.fullmatch(r"SK[a-fA-F0-9]{32}", key_sid) or not key_secret:
        raise HTTPException(503, "Recording service credentials unavailable")
    url = (
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}"
        f"/Recordings/{recording_sid}.mp3"
    )
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            async with client.stream(
                "GET", url, auth=(key_sid, key_secret),
                headers={"Accept": "audio/mpeg"},
            ) as response:
                # Never forward credentials to a redirected host.
                if response.status_code != 200:
                    raise HTTPException(502, "Recording is not available")
                media_type = response.headers.get("content-type", "").split(";")[0].lower()
                if media_type not in ("audio/mpeg", "audio/mp3", "audio/mpeg3"):
                    raise HTTPException(502, "Unexpected recording content")
                chunks, total = [], 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_AUDIO_BYTES:
                        raise HTTPException(502, "Recording exceeds size limit")
                    chunks.append(chunk)
                if not chunks:
                    raise HTTPException(502, "Recording is empty")
                return Response(
                    content=b"".join(chunks), media_type="audio/mpeg",
                    headers={
                        "Cache-Control": "private, no-store",
                        "Content-Disposition": "inline; filename=voicemail.mp3",
                        "X-Content-Type-Options": "nosniff",
                        "Referrer-Policy": "no-referrer",
                    },
                )
    except httpx.HTTPError:
        raise HTTPException(502, "Recording service unavailable")
