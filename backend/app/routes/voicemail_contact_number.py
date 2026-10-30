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
from app.voice_relay_models import DayTelloVoiceRelayAssignment
from app.voicemail_auto_provision import ensure_test_voicemail_number
from app.voice_relay_provisioning import reserve_relay_for_area_code
from app.voicemail_owner_links import (
    approved_test_recipient,
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


def reject_internal_owner_destination(db: Session, number: str, shop_id: str) -> None:
    """Never save a platform routing DID as the owner's external phone.

    This validation precedes AI transfer changes and SMS activation. It also
    rejects disabled relay assignments, which could be enabled later.
    """
    if db.query(DayTelloVoicemailShopSettings).filter(
        DayTelloVoicemailShopSettings.receiving_number == number
    ).first() is not None:
        raise HTTPException(409, "Owner phone cannot be a voicemail routing number")
    if db.query(DayTelloVoiceRelayAssignment).filter(
        DayTelloVoiceRelayAssignment.relay_number == number
    ).first() is not None:
        raise HTTPException(409, "Owner phone cannot be a voice relay number")
    if db.query(Shop).filter(
        Shop.highlevel_phone_number == number
    ).first() is not None:
        raise HTTPException(409, "Owner phone cannot be an AI Receptionist number")
    # Even this shop's published business line may forward into its AI agent.
    # Reject all published business numbers to prevent same-shop recursion
    # as well as cross-tenant call disclosure.
    if db.query(Shop).filter(Shop.phone == number).first() is not None:
        raise HTTPException(409, "Owner phone cannot be a business routing number")


def _sms_configuration_complete(shop: Shop, settings: DayTelloVoicemailShopSettings | None) -> bool:
    """Report SMS as configured only when all local delivery guards pass.

    This is a read-only configuration check, NOT proof that a live voicemail
    was received, a text was delivered, or external forwarding works.
    """
    expected_location = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    if not (
        settings
        and settings.notifications_enabled
        and PHONE.fullmatch(settings.owner_phone or "")
        and PHONE.fullmatch(settings.receiving_number or "")
        and shop.highlevel_agent_id
        and expected_location
        and shop.highlevel_location_id == expected_location
        and settings.location_id == expected_location
        and os.getenv("DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED") == "true"
        and PHONE.fullmatch(os.getenv("HIGHLEVEL_SMS_FROM_NUMBER", "").strip())
    ):
        return False
    try:
        approved_test_recipient(shop.slug, settings.owner_phone)
        link_cipher()
        test_link_origin()
    except HTTPException:
        return False
    return True


def public_status(shop: Shop, settings: DayTelloVoicemailShopSettings | None):
    return {
        "shop_slug": shop.slug,
        # A saved settings row only proves a partial setup. Forwarding and
        # unanswered-call fallback are not provider-verified, so never expose
        # this as a ready-to-use customer phone system.
        "ready": False,
        "settings_saved": bool(settings),
        "phone_number": settings.owner_phone if settings else None,
        "notifications_enabled": bool(settings.notifications_enabled) if settings else False,
        "voicemail_number": settings.receiving_number if settings else None,
        "sms_ready": _sms_configuration_complete(shop, settings),
        # A relay DID being allocated does not prove its external forwarding
        # destination or voicemail timeout. Never infer this from SMS readiness.
        "forwarding_verified": False,
        "setup_complete": False,
    }


@router.get("/shops/{shop_slug}/voicemail-onboarding/readiness")
def voicemail_onboarding_readiness(
    shop_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read-only tenant-scoped gate. Never claim full setup from SMS readiness.

    Provider forwarding to owner and unanswered-call backup cannot yet be
    automatically verified by this integration, so this reports the exact
    outstanding dependencies rather than declaring a new shop ready.
    """
    shop = owner_shop(db, shop_slug, current_user)
    settings = db.get(DayTelloVoicemailShopSettings, shop.id)
    expected = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    connected = bool(shop.highlevel_agent_id and
                     shop.highlevel_location_id and
                     shop.highlevel_location_id == expected)
    # Persisted strings are not proof that the assigned DID or owner
    # recipient is dialable. A malformed value must never be described as
    # an assigned number or an activated SMS destination.
    number_assigned = bool(
        settings and PHONE.fullmatch(settings.receiving_number or "") and
        settings.location_id == expected and connected
    )
    recipient_saved = bool(
        settings and PHONE.fullmatch(settings.owner_phone or "")
    )
    sms_active = bool(
        number_assigned and recipient_saved and
        _sms_configuration_complete(shop, settings)
    )
    return {
        "shop_slug": shop.slug,
        "ai_agent_connected": connected,
        "voicemail_number_assigned": number_assigned,
        "owner_number_saved": recipient_saved,
        "sms_activated": sms_active,
        "forwarding_to_owner_verified": False,
        "voicemail_fallback_verified": False,
        "ready_for_customer_calls": False,
        "requires_manual_provider_setup": True,
        "reason": "Automated provider forwarding and voicemail fallback verification are not implemented.",
    }


class PrepareTestVoiceRelay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    area_code: str
    authorize_number_purchase: bool = False

    @field_validator("area_code")
    @classmethod
    def validate_area_code(cls, value):
        if not isinstance(value, str) or not re.fullmatch(r"[2-9][0-9]{2}", value):
            raise ValueError("Enter a valid three-digit US area code")
        return value


@router.post("/shops/{shop_slug}/voice-relay/prepare-test")
def prepare_test_voice_relay(
    shop_slug: str,
    payload: PrepareTestVoiceRelay,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Owner-approved test DID purchase and disabled exclusive assignment.

    No purchase without an explicit owner confirmation and platform gate.
    This does not enable call routing, send SMS or declare customer readiness.
    """
    shop = owner_shop(db, shop_slug, current_user)
    if payload.authorize_number_purchase is not True:
        raise HTTPException(409, "Approve the relay number purchase before setup")
    if (os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true" or
            os.getenv("DAYTELLO_VOICE_RELAY_PURCHASE_ENABLED") != "true"):
        raise HTTPException(409, "Automatic relay number purchasing is not enabled")
    result = reserve_relay_for_area_code(
        shop, db, payload.area_code, approved=True,
    )
    return {**result, "ready_for_customer_calls": False,
            "next_step": "Save the approved owner transfer number"}


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
    reject_internal_owner_destination(db, number, shop.id)
    approved_test_recipient(shop.slug, number)

    # An isolated shop may already have a verified voicemail DID but no
    # AI agent ID in DayTello yet. Save the approved owner's phone as
    # PENDING without enabling SMS or modifying the HighLevel agent.
    # This makes onboarding actionable instead of disabling Save.
    if not str(shop.highlevel_agent_id or "").strip():
        settings.owner_phone = number
        settings.notifications_enabled = False
        try:
            db.commit()
            db.refresh(settings)
        except Exception:
            db.rollback()
            raise HTTPException(502, "Could not save the approved phone number")
        return {
            **public_status(shop, settings),
            "pending_provisioning": True,
            "live_call_test_required": True,
            "message": (
                "Phone number saved. Voicemail notifications remain off "
                "until AI Receptionist provisioning and transfer verification finish."
            ),
        }

    if os.getenv("DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED") != "true":
        raise HTTPException(409, "Voicemail notification setup is not yet ready")

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

    # SMS routing is independent of forwarding configuration. Allow this
    # authenticated shop owner to activate notifications ONLY after the
    # strict test recipient allowlist, message link, SMS sender and AI-to-relay
    # transfer checks above pass. Do NOT claim the relay forwards to the
    # owner: the public HighLevel number API cannot verify that leg.
    # There is no global "verified" switch that could accidentally authorize
    # every tenant or bypass its individual phone configuration.
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
        "message": ("Voicemail SMS notifications are configured for the approved "
                    "test recipient. External call forwarding and HighLevel "
                    "voicemail fallback still require verification."),
    }


class ConfirmTestVoicemailActivation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed_live_call_test: bool


@router.post("/shops/{shop_slug}/voicemail-notifications/activate-test")
def activate_shop_voicemail_notifications(
    shop_slug: str,
    payload: ConfirmTestVoicemailActivation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Activate a verified test shop's owner SMS; never touch call routing.

    Requires an authenticated owner, explicit real-call confirmation,
    existing AI agent, verified voicemail number, and test allowlists.
    This is a temporary test-only recovery action, not general onboarding.
    """
    if os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true":
        raise HTTPException(404, "Test-only activation unavailable")
    if os.getenv("DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED") != "true":
        raise HTTPException(409, "Voicemail SMS delivery is disabled")
    if payload.confirmed_live_call_test is not True:
        raise HTTPException(409, "Confirm the completed live forwarding and voicemail test")

    shop = owner_shop(db, shop_slug, current_user)
    if not str(shop.highlevel_agent_id or "").strip():
        raise HTTPException(409, "Existing AI agent is not connected")
    settings = db.get(DayTelloVoicemailShopSettings, shop.id)
    if not settings or not settings.receiving_number or not settings.owner_phone:
        raise HTTPException(409, "Voicemail destination and owner number must be saved")
    expected_location = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    if not expected_location or shop.highlevel_location_id != expected_location:
        raise HTTPException(409, "Shop HighLevel location is not verified")
    if settings.location_id != expected_location:
        raise HTTPException(409, "Voicemail location mismatch")

    # A legacy or separately saved phone may not have passed the owner-number
    # safety checks in the unified setup route. Re-check before activation.
    reject_internal_owner_destination(db, settings.owner_phone, shop.id)
    # Keep tenant separation and the original approved recipient mandatory.
    approved_test_recipient(shop.slug, settings.owner_phone)
    link_cipher()
    test_link_origin()
    sender = os.getenv("HIGHLEVEL_SMS_FROM_NUMBER", "").strip()
    if not PHONE.fullmatch(sender):
        raise HTTPException(503, "SMS sender is not configured")

    if not settings.notifications_enabled:
        settings.notifications_enabled = True
        try:
            db.commit()
            db.refresh(settings)
        except Exception:
            db.rollback()
            raise HTTPException(502, "Could not activate voicemail notifications")
    return {
        **public_status(shop, settings),
        "call_routing_changed": False,
        "recording_delivery_test_required": True,
        "message": "Test voicemail SMS activated; call routing was not modified.",
    }
