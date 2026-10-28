"""Single-number owner setup for call transfer and voicemail alerts.

Test-environment integration: owners provide one number; provisioning,
HighLevel configuration, and SMS safeguards remain server-controlled.
"""
import os
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.routes.auth import get_current_user
from app.routes.shops import require_owner_for_shop
from app.routes.ai_setup import (
    DayTelloStaffTransferRequest,
    daytello_save_staff_transfer,
)
from app.voicemail_models import DayTelloVoicemailShopSettings
from app.voicemail_auto_provision import ensure_test_voicemail_number
from app.voicemail_owner_links import (
    link_cipher,
    owner_phone_for_test_shop,
    test_link_origin,
)

router = APIRouter()
PHONE = re.compile(r"^\+1[2-9][0-9]{2}[2-9][0-9]{6}$")


class OwnerCallVoicemailNumber(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def validate_number(cls, value):
        if not PHONE.fullmatch(value):
            raise ValueError("Enter a 10-digit US/Canada number with country code +1")
        return value


def owner_shop(db: Session, shop_slug: str, current_user: User) -> Shop:
    clean_slug = require_owner_for_shop(shop_slug, current_user)
    shop = db.query(Shop).filter(Shop.slug == clean_slug).one_or_none()
    if shop is None:
        raise HTTPException(404, "Business not found")
    if not shop.ai_voice_enabled:
        raise HTTPException(409, "This business does not have AI Receptionist enabled")
    # Prevent ambiguity if user shop_slug and shop_id ever become inconsistent.
    if str(current_user.shop_id or "") != str(shop.id):
        raise HTTPException(403, "Business access mismatch")
    return shop


def public_status(shop: Shop, settings: DayTelloVoicemailShopSettings | None):
    return {
        "shop_slug": shop.slug,
        "ready": bool(settings),
        "phone_number": settings.owner_phone if settings else None,
        "notifications_enabled": bool(settings.notifications_enabled) if settings else False,
        "voicemail_number": settings.receiving_number if settings else None,
    }


@router.get("/shops/{shop_slug}/call-voicemail-number")
def get_owner_call_voicemail_number(
    shop_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shop = owner_shop(db, shop_slug, current_user)
    settings = db.get(DayTelloVoicemailShopSettings, shop.id)
    return public_status(shop, settings)


@router.put("/shops/{shop_slug}/call-voicemail-number")
def set_owner_call_voicemail_number(
    shop_slug: str,
    payload: OwnerCallVoicemailNumber,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save once; never report success unless transfer and notification agree."""
    shop = owner_shop(db, shop_slug, current_user)
    if os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true":
        raise HTTPException(409, "Call and voicemail setup is not yet enabled for this shop")
    if os.getenv("DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED") != "true":
        raise HTTPException(409, "Voicemail notification setup is not yet ready")

    settings = db.get(DayTelloVoicemailShopSettings, shop.id)
    if not settings:
        settings = ensure_test_voicemail_number(shop, db)
    location = str(shop.highlevel_location_id or "").strip()
    if (
        not location
        or location != settings.location_id
        or location != os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    ):
        raise HTTPException(409, "Voicemail connection needs verification")

    number = payload.phone_number
    # This temporary test allowlist prevents any new number receiving
    # voicemail SMS until it has been explicitly approved.
    settings_proxy = type("RequestedNotification", (), {
        "notifications_enabled": True, "owner_phone": number,
    })()
    owner_phone_for_test_shop(shop.slug, settings_proxy)
    link_cipher()
    test_link_origin()
    sender = os.getenv("HIGHLEVEL_SMS_FROM_NUMBER", "").strip()
    if not PHONE.fullmatch(sender):
        raise HTTPException(503, "SMS sender is not configured")

    # CRITICAL: transfer to the shop's *dedicated HighLevel voicemail DID*,
    # never directly to the owner's mobile/Google Voice. The latter would
    # bypass HighLevel's unanswered-call voicemail fallback.
    #
    # This action only configures the AI-to-voicemail-DID leg. Forwarding from
    # the DID to the owner, including timeout/backup, must be independently
    # provisioned and verified by the phone provider before completing
    # fully automatic onboarding. Do not claim that routing is configured
    # merely because the owner number was saved.
    transfer_destination = settings.receiving_number
    transfer_result = daytello_save_staff_transfer(
        DayTelloStaffTransferRequest(
            enabled=True, phone_number=transfer_destination,
            confirm_no_forwarding_loop=True,
        ),
        current_user=current_user, db=db,
    )
    if (not transfer_result.get("enabled")
            or transfer_result.get("phone_number") != transfer_destination):
        raise HTTPException(502, "HighLevel voicemail transfer was not verified; no notification changes saved")

    # SMS configuration changes only after HighLevel confirms transfer to the
    # dedicated voicemail number, not the owner's personal number.
    # Keep the current database preference untouched if the provider fails.
    settings.owner_phone = number
    settings.notifications_enabled = True
    try:
        db.commit()
    except Exception:
        db.rollback()
        # The external transfer may already have changed; never claim
        # that the combined configuration was saved successfully.
        raise HTTPException(
            502, "Call transfer changed but voicemail settings could not be saved; contact DayTello support"
        )
    db.refresh(settings)
    return {
        **public_status(shop, settings),
        "call_transfer_enabled": True,
        "live_call_test_required": True,
    }
