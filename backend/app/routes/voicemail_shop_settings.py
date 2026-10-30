"""Owner-only voicemail notification preferences; routing is provisioned separately.

This API never permits owners to assign phone numbers or HighLevel locations.
Notifications default off, and the test-only recipient allowlist still applies.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.routes.auth import get_current_user
from app.routes.shops import require_owner_for_shop
from app.voicemail_models import DayTelloVoicemailShopSettings

router = APIRouter()
PHONE = re.compile(r"^\+[1-9][0-9]{7,14}$")


class VoicemailOwnerPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notifications_enabled: bool
    owner_phone: str | None = None

    @field_validator("owner_phone")
    @classmethod
    def validate_phone(cls, value):
        if value is not None and not PHONE.fullmatch(value):
            raise ValueError("Enter a phone number in +countrycode format")
        return value


def configured_shop(db: Session, shop_slug: str, current_user: User):
    slug = require_owner_for_shop(shop_slug, current_user)
    shop = db.query(Shop).filter(Shop.slug == slug).one_or_none()
    if shop is None:
        raise HTTPException(404, "Business not found")
    if not shop.ai_voice_enabled:
        raise HTTPException(409, "AI Receptionist is not enabled")
    return shop


def pref_response(shop, prefs):
    return {
        "shop_slug": shop.slug,
        "configured": prefs is not None,
        "receiving_number": prefs.receiving_number if prefs else None,
        "owner_phone": prefs.owner_phone if prefs else None,
        "notifications_enabled": bool(prefs.notifications_enabled) if prefs else False,
    }


@router.get("/shops/{shop_slug}/voicemail-settings")
def get_voicemail_settings(
    shop_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shop = configured_shop(db, shop_slug, current_user)
    prefs = db.get(DayTelloVoicemailShopSettings, shop.id)
    return pref_response(shop, prefs)


@router.patch("/shops/{shop_slug}/voicemail-settings")
def update_voicemail_settings(
    shop_slug: str,
    payload: VoicemailOwnerPreferences,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shop = configured_shop(db, shop_slug, current_user)
    prefs = db.get(DayTelloVoicemailShopSettings, shop.id)
    if prefs is None:
        raise HTTPException(409, "Voicemail number must be provisioned first")
    if payload.notifications_enabled and payload.owner_phone is None:
        raise HTTPException(422, "A notification phone is required")
    # This preferences endpoint may save a phone or disable alerts, but must
    # never bypass the separate, test-only verified activation flow. An
    # already-active recipient cannot be silently swapped either.
    if payload.notifications_enabled and not prefs.notifications_enabled:
        raise HTTPException(409, "Voicemail notifications require verified activation")
    if payload.notifications_enabled and payload.owner_phone != prefs.owner_phone:
        raise HTTPException(409, "Disable and re-verify the new notification recipient")
    prefs.owner_phone = payload.owner_phone
    prefs.notifications_enabled = payload.notifications_enabled
    db.commit()
    db.refresh(prefs)
    return pref_response(shop, prefs)
