"""Per-shop owner SMS consent and possession verification (no per-shop env allowlist).

The authenticated owner routes must call these helpers; this module never
purchases a number, changes telephone routing, or activates notifications.
Verification is opt-in, test-only and disabled by default. A successful
verification authorizes exactly one shop/phone combination, not other tenants.
"""
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.database import Base

E164 = re.compile(r"^\+1[2-9][0-9]{2}[2-9][0-9]{6}$")
CODE = re.compile(r"^[0-9]{6}$")
COOLDOWN = timedelta(seconds=90)
WINDOW = timedelta(hours=1)
LIFETIME = timedelta(minutes=10)
MAX_PER_WINDOW = 5
MAX_ATTEMPTS = 5


class DayTelloVoicemailOwnerVerification(Base):
    __tablename__ = "daytello_voicemail_owner_verifications"

    shop_id = Column(String(128), primary_key=True)
    phone = Column(String(20), nullable=False)
    challenge_salt = Column(String(32), nullable=True)
    challenge_digest = Column(String(64), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    window_started_at = Column(DateTime, nullable=True)
    sent_in_window = Column(Integer, nullable=False, default=0)
    failed_attempts = Column(Integer, nullable=False, default=0)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


def _now():
    # Use naive UTC consistently because SQLite does not round-trip timezone.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _secret():
    raw = os.getenv("DAYTELLO_VOICEMAIL_LINK_KEY", "")
    if len(raw) < 32:
        raise HTTPException(503, "Owner verification is not configured")
    return raw.encode("utf-8")


def _enabled():
    if (os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true"
            or os.getenv("DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED") != "true"
            or os.getenv("DAYTELLO_VOICEMAIL_OWNER_VERIFICATION_ENABLED") != "true"):
        raise HTTPException(404, "Owner verification is unavailable")


def _digest(shop_id, phone, salt, code):
    payload = "|".join((shop_id, phone, salt, code)).encode("utf-8")
    return hmac.new(_secret(), payload, hashlib.sha256).hexdigest()


def verified_owner_recipient(db, shop_id, phone):
    """Fail closed; the shop's verified phone cannot be silently replaced."""
    _enabled()
    if not isinstance(phone, str) or not E164.fullmatch(phone):
        raise HTTPException(409, "Owner SMS phone is invalid")
    proof = db.get(DayTelloVoicemailOwnerVerification, shop_id)
    if not proof or proof.phone != phone or proof.verified_at is None:
        raise HTTPException(409, "Owner SMS number must be verified")
    return phone


def start_owner_verification(db, shop_id, phone, *, consent, sender):
    """Send a one-time code to an authenticated owner's safe phone number.

    Caller must have checked owner/shop authorization, location and loop safety.
    Holding the shop row lock serializes challenges for the same shop on PG.
    """
    _enabled()
    if consent is not True:
        raise HTTPException(409, "Consent to receive a verification text is required")
    if not E164.fullmatch(phone or "") or not E164.fullmatch(sender or ""):
        raise HTTPException(422, "A valid owner number and SMS sender are required")
    from app.models import Shop
    from app.routes.reminders import send_highlevel_sms
    shop = db.query(Shop).filter(Shop.id == shop_id).with_for_update().one_or_none()
    if not shop or not shop.ai_voice_enabled:
        raise HTTPException(409, "AI Receptionist shop is not active")
    now = _now()
    proof = db.get(DayTelloVoicemailOwnerVerification, shop_id)
    if proof and proof.sent_at and now - proof.sent_at < COOLDOWN:
        raise HTTPException(429, "Wait before requesting another verification text")
    if proof and proof.window_started_at and now - proof.window_started_at < WINDOW:
        if proof.sent_in_window >= MAX_PER_WINDOW:
            raise HTTPException(429, "Verification text limit reached")
        count, started = proof.sent_in_window + 1, proof.window_started_at
    else:
        count, started = 1, now
    code = f"{secrets.randbelow(1000000):06d}"
    salt = secrets.token_hex(16)
    if proof is None:
        proof = DayTelloVoicemailOwnerVerification(shop_id=shop_id, phone=phone)
        db.add(proof)
    # Any new challenge revokes the previous verified phone and OTP.
    proof.phone = phone
    proof.challenge_salt = salt
    proof.challenge_digest = _digest(shop_id, phone, salt, code)
    proof.expires_at = now + LIFETIME
    proof.sent_at = now
    proof.window_started_at = started
    proof.sent_in_window = count
    proof.failed_attempts = 0
    proof.verified_at = None
    # SMS is submitted only after durable challenge state is saved.
    db.commit()
    result = send_highlevel_sms(
        phone, "DayTello: Your owner voicemail verification code is "
        + code + ". It expires in 10 minutes. Do not share this code.",
        shop_id=shop_id, shop_slug=shop.slug,
        purpose="voicemail-owner-notification",
        source_id="owner-verify-" + salt,
    )
    if not result.get("success"):
        # Invalidate a challenge if provider did not accept its SMS.
        proof = db.get(DayTelloVoicemailOwnerVerification, shop_id)
        if proof and proof.challenge_salt == salt:
            proof.challenge_digest = None
            proof.expires_at = None
            db.commit()
        raise HTTPException(502, "Verification text could not be sent")
    return {"verification_sent": True, "expires_in_seconds": 600,
            "notifications_enabled": False}


def confirm_owner_verification(db, shop_id, phone, code):
    """Consume the one-time challenge, with durable brute-force limits."""
    _enabled()
    if not isinstance(code, str) or not CODE.fullmatch(code):
        raise HTTPException(422, "Enter the six-digit verification code")
    from app.models import Shop
    shop = db.query(Shop).filter(Shop.id == shop_id).with_for_update().one_or_none()
    if not shop or not shop.ai_voice_enabled:
        raise HTTPException(409, "AI Receptionist shop is not active")
    proof = db.get(DayTelloVoicemailOwnerVerification, shop_id)
    now = _now()
    if (not proof or proof.phone != phone or not proof.challenge_digest
            or not proof.challenge_salt or not proof.expires_at
            or now > proof.expires_at or proof.failed_attempts >= MAX_ATTEMPTS):
        raise HTTPException(409, "Verification code is unavailable or expired")
    expected = _digest(shop_id, phone, proof.challenge_salt, code)
    if not hmac.compare_digest(expected, proof.challenge_digest):
        proof.failed_attempts += 1
        if proof.failed_attempts >= MAX_ATTEMPTS:
            proof.challenge_digest = None
        db.commit()
        raise HTTPException(409, "Verification code is incorrect")
    proof.verified_at = now
    proof.challenge_digest = None
    proof.challenge_salt = None
    proof.expires_at = None
    db.commit()
    return {"owner_number_verified": True, "notifications_enabled": False}


def disable_owner_voicemail_notifications(db, shop_id):
    """Owner opt-out: revoke SMS proof and stop future owner alerts atomically.

    This never changes provider call routing or voicemail capture. The
    authenticated route is responsible for checking shop ownership.
    """
    from app.models import Shop
    from app.voicemail_models import DayTelloVoicemailShopSettings

    # Serialize opt-out against verification/activation for this shop on PG.
    shop = db.query(Shop).filter(Shop.id == shop_id).with_for_update().one_or_none()
    if shop is None:
        raise HTTPException(404, "Shop not found")
    proof = db.get(DayTelloVoicemailOwnerVerification, shop_id)
    settings = db.get(DayTelloVoicemailShopSettings, shop_id)
    if proof is not None:
        proof.verified_at = None
        proof.challenge_digest = None
        proof.challenge_salt = None
        proof.expires_at = None
    if settings is not None:
        settings.notifications_enabled = False
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(502, "Could not disable voicemail notifications")
    return {
        "notifications_enabled": False,
        "owner_number_verified": False,
        "call_routing_changed": False,
        "message": "Owner voicemail texts disabled. Call routing was not changed.",
    }
