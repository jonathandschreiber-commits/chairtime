"""Test-only, platform-admin provisioning of verified voicemail receiving numbers.

No purchase, forwarding change, SMS, or agent reconfiguration is performed here.
HighLevel's live phone inventory is checked before the DB binding is created.
"""
import os
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.routes.ai_setup import get_location_phone_numbers
from app.routes.auth import get_current_user, is_platform_admin
from app.routes.voicemail_webhook import configured_routing_map
from app.voicemail_models import DayTelloVoicemailShopSettings

router = APIRouter()
PHONE = re.compile(r"^\+[1-9][0-9]{7,14}$")


class ProvisionVoicemailNumber(BaseModel):
    model_config = ConfigDict(extra="forbid")
    receiving_number: str

    @field_validator("receiving_number")
    @classmethod
    def check_number(cls, value):
        if not PHONE.fullmatch(value):
            raise ValueError("Use a +countrycode E.164 phone number")
        return value


@router.post("/daytello/admin/voicemail-shops/{shop_slug}/provision")
def provision_shop_voicemail(
    shop_slug: str,
    payload: ProvisionVoicemailNumber,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Only an authenticated, server-authorized platform admin may bind a number."""
    if os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true":
        raise HTTPException(404, "Test-only voicemail provisioning is unavailable")
    if not is_platform_admin(current_user):
        raise HTTPException(403, "Platform administrator access required")

    shop = db.query(Shop).filter(Shop.slug == shop_slug).one_or_none()
    if not shop:
        raise HTTPException(404, "Business not found")
    if not shop.ai_voice_enabled:
        raise HTTPException(409, "AI Receptionist is not enabled")

    location_id = str(shop.highlevel_location_id or "").strip()
    expected = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    if not location_id or not expected or location_id != expected:
        raise HTTPException(409, "Shop HighLevel location is not verified for this test")

    # A voicemail number cannot be silently taken over from another shop.
    existing = db.get(DayTelloVoicemailShopSettings, shop.id)
    if existing and (
        existing.location_id != location_id
        or existing.receiving_number != payload.receiving_number
    ):
        raise HTTPException(409, "Existing voicemail routing requires separate review")

    conflict = db.query(DayTelloVoicemailShopSettings).filter(
        DayTelloVoicemailShopSettings.location_id == location_id,
        DayTelloVoicemailShopSettings.receiving_number == payload.receiving_number,
        DayTelloVoicemailShopSettings.shop_id != shop.id,
    ).first()
    if conflict:
        raise HTTPException(409, "Voicemail number already belongs to another business")

    # Legacy Stan's Shop mappings remain authoritative during migration.
    if os.getenv("DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP", "").strip():
        legacy = configured_routing_map()
        if legacy.get(payload.receiving_number) not in (None, shop.slug):
            raise HTTPException(409, "Voicemail number is assigned in legacy routing")

    # Fail closed if the provider's phone inventory cannot be verified.
    _, numbers = get_location_phone_numbers(location_id)
    matches = [n for n in numbers if n.get("phoneNumber") == payload.receiving_number]
    if len(matches) != 1:
        raise HTTPException(409, "Number not verified in this HighLevel location")

    if not existing:
        existing = DayTelloVoicemailShopSettings(
            shop_id=shop.id,
            location_id=location_id,
            receiving_number=payload.receiving_number,
            owner_phone=None,
            notifications_enabled=False,
        )
        db.add(existing)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Conflicting voicemail phone assignment")
    return {
        "shop_slug": shop.slug,
        "location_id": location_id,
        "receiving_number": existing.receiving_number,
        "notifications_enabled": bool(existing.notifications_enabled),
        "number_verified": True,
    }
