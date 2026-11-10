"""Single-number owner setup for call transfer and voicemail alerts.

Test-environment integration: owners provide one number; provisioning,
HighLevel configuration, and SMS safeguards remain server-controlled.
"""
import os

from app.voice_relay_mode import production_relay_enabled
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
from app.voicemail_owner_verification import (
    start_owner_verification, confirm_owner_verification,
    disable_owner_voicemail_notifications,
)
from app.voice_relay_models import DayTelloVoiceRelayAssignment
from app.voicemail_auto_provision import ensure_test_voicemail_number
from app.voice_relay_provisioning import (
    reserve_relay_for_area_code, reserve_or_purchase_relay_for_shop,
    allocate_preowned_relay_for_shop,
)
from app.voice_relay_provider import VoiceRelayNumberProvider
from app.voicemail_owner_links import (
    approved_owner_recipient,
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


def _recording_link_origin_for_shop(shop: Shop, settings, db=None) -> str:
    """Validate the playback host actually used by this shop's recording path.

    Legacy HighLevel voicemail still uses the original test link host. A new
    programmable relay serves playback on its own callback host, so it must
    not require a second, unrelated legacy Railway URL to activate SMS.
    """
    relay = db.get(DayTelloVoiceRelayAssignment, shop.id) if db is not None else None
    if relay is not None and settings and relay.relay_number == settings.receiving_number:
        from urllib.parse import urlsplit
        from app.routes.voice_relay import _origin
        from app.voicemail_owner_links import PRODUCTION_HOST

        origin = _origin()
        if urlsplit(origin).hostname == PRODUCTION_HOST:
            raise HTTPException(503, "Relay playback must use the isolated test host")
        return origin
    return test_link_origin()


def _sms_configuration_complete(shop: Shop, settings: DayTelloVoicemailShopSettings | None, db=None) -> bool:
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
        approved_owner_recipient(shop.slug, settings.owner_phone, db=db, shop_id=shop.id)
        link_cipher()
        _recording_link_origin_for_shop(shop, settings, db)
    except HTTPException:
        return False
    return True


def public_status(shop: Shop, settings: DayTelloVoicemailShopSettings | None, db=None):
    # This is a local onboarding checkpoint, not evidence of a completed
    # provider-backed call. Only an enabled, shop-bound relay with an
    # approved SMS recipient may let the owner proceed to review.
    relay = db.get(DayTelloVoiceRelayAssignment, shop.id) if db is not None else None
    configuration_complete = bool(
        relay and relay.enabled and settings
        and relay.relay_number == settings.receiving_number
        and os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") == "true"
        and os.getenv("DAYTELLO_VOICE_RELAY_ALLOW_TEST_CALLS") == "true"
        and _sms_configuration_complete(shop, settings, db)
    )
    return {
        "configuration_complete": configuration_complete,
        "live_call_test_required": True,
        "shop_slug": shop.slug,
        # A saved settings row only proves a partial setup. Forwarding and
        # unanswered-call fallback are not provider-verified, so never expose
        # this as a ready-to-use customer phone system.
        "ready": False,
        "settings_saved": bool(settings),
        "phone_number": settings.owner_phone if settings else None,
        "notifications_enabled": bool(settings.notifications_enabled) if settings else False,
        "voicemail_number": settings.receiving_number if settings else None,
        "sms_ready": _sms_configuration_complete(shop, settings, db),
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
        _sms_configuration_complete(shop, settings, db)
    )
    # A saved voicemail DID is not proof that the Voice AI agent actually
    # transfers to it. Read back HighLevel's deployed CALL_TRANSFER action.
    # Never claim it is verified after an API failure or a mismatched target.
    ai_transfer_verified = False
    if number_assigned:
        try:
            from app.routes.ai_setup import daytello_get_staff_transfer
            transfer = daytello_get_staff_transfer(
                current_user=current_user, db=db,
            )
            ai_transfer_verified = bool(
                transfer.get("enabled")
                and not transfer.get("other_transfer_actions_detected")
                and transfer.get("phone_number") == settings.receiving_number
            )
        except Exception:
            # A token error, location mismatch, or other provider failure
            # must never turn a saved local row into a verification claim.
            ai_transfer_verified = False
    return {
        "shop_slug": shop.slug,
        "ai_to_voicemail_transfer_verified": ai_transfer_verified,
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


@router.get("/shops/{shop_slug}/voice-relay/provider-connectivity")
def voice_relay_provider_connectivity(
    shop_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Owner-only, test-only read of Twilio number inventory.

    No call, number purchase, routing update, or credential values are returned.
    A successful empty inventory is normal for a trial account.
    """
    shop = owner_shop(db, shop_slug, current_user)
    if (os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true"
            or os.getenv("DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED") != "true"
            or shop.slug != "test-shop-3"):
        raise HTTPException(404, "Unavailable")
    try:
        provider = VoiceRelayNumberProvider()
        numbers = provider._list()
    except HTTPException:
        raise HTTPException(502, "Twilio read-only connectivity check failed") from None
    except Exception:
        raise HTTPException(502, "Twilio read-only connectivity check failed") from None
    return {
        "connected": True,
        "assigned_number_count": len(numbers),
        "live_relay_verified": False,
        "ready_for_customer_calls": False,
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


@router.post("/shops/{shop_slug}/voice-relay/claim-test-reserve")
def claim_test_shop3_preowned_relay(
    shop_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Owner-scoped claim of the one pre-purchased test DID; no provider writes.

    Verifies exact Twilio ownership and inbound URL, then creates only a
    disabled, exclusive local assignment. Never purchases a DID, sends SMS,
    enables calls, or changes HighLevel transfer actions.
    """
    shop = owner_shop(db, shop_slug, current_user)
    if (shop.slug != "test-shop-3"
            or os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true"
            or os.getenv("DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED") != "true"):
        raise HTTPException(404, "Unavailable")
    number = "+15077135447"
    result = reserve_or_purchase_relay_for_shop(
        shop, db, number, approved=False,
    )
    return {
        **result,
        "ready_for_customer_calls": False,
        "message": "Pre-owned relay registered, but calls and SMS remain disabled pending verification.",
    }


class IsolatedShop3RelayCallTest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm_test_calls: bool


@router.post("/shops/{shop_slug}/voice-relay/call-only-test")
def set_shop3_relay_call_test(
    shop_slug: str,
    payload: IsolatedShop3RelayCallTest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enable or stop the isolated Test Shop #3 relay and optional test SMS.

    This deliberately does not touch HighLevel's AI agent/transfer, trigger a
    provider call or change the Twilio phone configuration.
    Only an explicitly authorized, owner-scoped and verified relay can ring.
    """
    shop = owner_shop(db, shop_slug, current_user)
    if (shop.slug != "test-shop-3"
            or os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true"
            or os.getenv("DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED") != "true"):
        raise HTTPException(404, "Unavailable")
    relay = db.get(DayTelloVoiceRelayAssignment, shop.id)
    settings = db.get(DayTelloVoicemailShopSettings, shop.id)
    if (not relay or not settings or
            relay.relay_number != "+15077135447" or
            settings.receiving_number != relay.relay_number):
        raise HTTPException(409, "Test relay assignment mismatch")
    if payload.confirm_test_calls is True:
        if os.getenv("DAYTELLO_VOICE_RELAY_ALLOW_TEST_CALLS") != "true":
            raise HTTPException(409, "Isolated test-call authorization is disabled")
        location = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
        if (not location or not shop.ai_voice_enabled or
                shop.highlevel_location_id != location or
                settings.location_id != location or
                not shop.highlevel_phone_number):
            raise HTTPException(409, "Test Shop #3 voice setup is incomplete")
        if not settings.owner_phone or not PHONE.fullmatch(settings.owner_phone):
            raise HTTPException(409, "Verified owner destination is not saved")
        reject_internal_owner_destination(db, settings.owner_phone, shop.id)
        approved_owner_recipient(shop.slug, settings.owner_phone, db=db, shop_id=shop.id)
        sms_test = os.getenv("DAYTELLO_SHOP3_DIRECT_TEST_SMS_ENABLED") == "true"
        if sms_test:
            if (os.getenv("DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED") != "true"
                    or os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true"):
                raise HTTPException(409, "Test voicemail SMS delivery is disabled")
            recipient_settings = type("RequestedNotification", (), {
                "notifications_enabled": True, "owner_phone": settings.owner_phone,
            })()
            if not owner_phone_for_test_shop(shop.slug, recipient_settings, db=db, shop_id=shop.id):
                raise HTTPException(409, "Owner is not eligible for test voicemail SMS")
            link_cipher()
            _recording_link_origin_for_shop(shop, settings, db)
            if not PHONE.fullmatch(os.getenv("HIGHLEVEL_SMS_FROM_NUMBER", "").strip()):
                raise HTTPException(503, "SMS sender is not configured")
        elif settings.notifications_enabled:
            raise HTTPException(409, "Call-only test requires SMS notifications disabled")
        # Fresh readback of the existing Twilio number and webhook. Never buy,
        # reconfigure, transfer, or provision any number in this endpoint.
        verified = VoiceRelayNumberProvider().find_existing(
            str(shop.id), expected_number=relay.relay_number)
        if not verified or not verified.get("route_verified"):
            raise HTTPException(409, "Twilio relay route could not be verified")
        relay.enabled = True
        settings.notifications_enabled = sms_test
    else:
        relay.enabled = False
        settings.notifications_enabled = False
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(502, "Could not update isolated relay test")
    return {
        "shop_slug": shop.slug,
        "relay_number": relay.relay_number,
        "test_calls_enabled": bool(relay.enabled),
        "sms_notifications_enabled": bool(settings.notifications_enabled),
        "highlevel_routing_changed": False,
        "ready_for_customer_calls": False,
        "message": ("Test relay accepts direct calls and will text the verified owner after a new voicemail."
                    if relay.enabled and settings.notifications_enabled else
                    "Test relay accepts direct calls. SMS is off; do not redirect the AI number."
                    if relay.enabled else "Isolated relay calls and test SMS disabled."),
    }


@router.get("/shops/{shop_slug}/call-voicemail-number")
def get_owner_call_voicemail_number(
    shop_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shop = owner_shop(db, shop_slug, current_user)
    settings = db.get(DayTelloVoicemailShopSettings, shop.id)
    return public_status(shop, settings, db)




def _use_highlevel_voicemail(shop: Shop) -> bool:
    if shop.slug == "test-shop-4" and (
        os.getenv("DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED") == "true"
        and os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") == "true"
        and os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") == "true"
        and os.getenv("DAYTELLO_VOICE_RELAY_PURCHASE_ENABLED") == "false"
    ):
        return False
    return os.getenv("DAYTELLO_VOICEMAIL_PROVIDER") == "highlevel"


def attach_preowned_relay_after_ai_number(shop: Shop, db: Session) -> bool:
    """Bind a previously approved relay as part of AI-number onboarding.

    This performs provider inventory reads and an exclusive local DB claim
    only. It never purchases a DID, enables calls, sends SMS, or changes
    HighLevel transfer actions. Legacy Stan/Bob voicemail routes are untouched.
    The owner still must approve the forwarding/SMS destination separately.
    """
    if production_relay_enabled():
        if not shop.ai_voice_enabled or not shop.highlevel_phone_number:
            return False
        return bool(allocate_preowned_relay_for_shop(shop, db))
    if os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true":
        return False
    # HighLevel-only shops never enter the Twilio provider adapter.
    # Reservation is restricted to previously allocated, provider-verified
    # HighLevel DIDs; no DID is bought or upstream forwarding altered here.
    if _use_highlevel_voicemail(shop):
        if db.get(DayTelloVoicemailShopSettings, shop.id) is not None:
            return False
        if db.get(DayTelloVoiceRelayAssignment, shop.id) is not None:
            raise HTTPException(409, "A Twilio relay is already assigned to this shop")
        ensure_test_voicemail_number(shop, db)
        return True
    if os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true":
        return False
    if (db.get(DayTelloVoicemailShopSettings, shop.id) is not None
            or db.get(DayTelloVoiceRelayAssignment, shop.id) is not None):
        return False
    provider = VoiceRelayNumberProvider()
    owned = provider.find_existing(str(shop.id))
    if owned:
        reserve_or_purchase_relay_for_shop(
            shop, db, owned["number"], approved=False, provider=provider,
        )
        return True
    return bool(allocate_preowned_relay_for_shop(shop, db, provider=provider))


def ensure_existing_shop_voicemail_route(shop: Shop, db: Session):
    """Connect a pre-owned relay to a new shop without buying or rerouting a DID.

    Existing HighLevel voicemail numbers retain their established path.
    A relay can be recovered only by its provider-verified, shop-specific
    ownership label; the provider adapter is called with approved=False,
    so this path cannot purchase a number.
    """
    relay = db.get(DayTelloVoiceRelayAssignment, shop.id)
    if relay:
        provider = VoiceRelayNumberProvider()
        reserve_or_purchase_relay_for_shop(
            shop, db, relay.relay_number, approved=False, provider=provider,
        )
        settings = db.get(DayTelloVoicemailShopSettings, shop.id)
        if settings is None:
            raise HTTPException(502, "Existing relay was not bound to voicemail settings")
        return settings

    # Keep previously assigned HighLevel routes (including Stan/Bob) and
    # explicit legacy shop mappings on their original provider path.
    existing = db.get(DayTelloVoicemailShopSettings, shop.id)
    if existing is not None:
        return ensure_test_voicemail_number(shop, db)
    from app.routes.voicemail_webhook import configured_routing_map
    legacy = (configured_routing_map()
              if os.getenv("DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP", "").strip()
              else {})
    if shop.slug in legacy.values():
        return ensure_test_voicemail_number(shop, db)

    # HighLevel-only deployments must not silently fall through into a
    # Twilio relay. This verifies a pre-reserved HighLevel voicemail DID and
    # binds it exclusively to this shop. HighLevel number forwarding and
    # unanswered-call fallback remain unverified and are never reported ready.
    if _use_highlevel_voicemail(shop):
        return ensure_test_voicemail_number(shop, db)

    # New AI shops need a programmable relay, not an unused legacy
    # HighLevel voicemail pool number: the latter has no verified owner-ring
    # and unanswered-call fallback. The owner can save their destination
    # before choosing the HighLevel AI number, without a second Save.
    if (os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") == "true"
            and os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") == "true"
            and shop.highlevel_agent_id):
        provider = VoiceRelayNumberProvider()
        owned = provider.find_existing(str(shop.id))
        if owned:
            reserve_or_purchase_relay_for_shop(
                shop, db, owned["number"], approved=False, provider=provider,
            )
        elif not allocate_preowned_relay_for_shop(shop, db, provider=provider):
            raise HTTPException(409, "No approved voicemail relay number exists for this shop")
        settings = db.get(DayTelloVoicemailShopSettings, shop.id)
        if settings is None:
            raise HTTPException(502, "Verified relay was not bound to voicemail settings")
        return settings

    # Legacy-only test environments retain their original reserved-number
    # behavior; no existing number, agent, or routing configuration is changed.
    return ensure_test_voicemail_number(shop, db)


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
        settings = ensure_existing_shop_voicemail_route(shop, db)
    location = str(shop.highlevel_location_id or "").strip()
    if (
        not location
        or location != settings.location_id
        or location != os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    ):
        raise HTTPException(409, "Voicemail connection needs verification")

    number = payload.phone_number
    reject_internal_owner_destination(db, number, shop.id)
    approved_owner_recipient(shop.slug, number, db=db, shop_id=shop.id)

    # The isolated Test Shop #3 can have a provider-verified, already owned
    # Twilio relay while this sandbox remains in HighLevel-only mode.
    # Saving its verified recipient must not turn on the relay, change
    # HighLevel call transfers, or send messages. No other shop is affected.
    if shop.slug == "test-shop-3" and os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") == "true":
        test_relay = db.get(DayTelloVoiceRelayAssignment, shop.id)
        if (test_relay is not None):
            if (test_relay.enabled or settings.notifications_enabled
                    or test_relay.relay_number != settings.receiving_number):
                raise HTTPException(409, "Existing relay requires a verified routing update")
            settings.owner_phone = number
            settings.notifications_enabled = False
            try:
                db.commit()
                db.refresh(settings)
            except Exception:
                db.rollback()
                raise HTTPException(502, "Could not save the approved phone number")
            return {
                **public_status(shop, settings, db),
                "pending_test_authorization": True,
                "live_call_test_required": True,
                "message": (
                    "Verified owner phone saved. Twilio relay calls and SMS "
                    "remain disabled until separately tested and authorized."
                ),
            }

    # HighLevel-only onboarding cannot safely write Phone System forwarding,
    # timeout, Call Connect or backup routing using a documented API.
    # Accept the verified owner's choice once, but leave all call/SMS
    # activation OFF until the provider route has been independently verified.
    # This avoids crossing into the unrelated Twilio relay activation path.
    if _use_highlevel_voicemail(shop):
        if db.get(DayTelloVoiceRelayAssignment, shop.id) is not None:
            raise HTTPException(409, "Conflicting voice relay assignment")
        if settings.notifications_enabled:
            raise HTTPException(
                409, "Existing active voicemail settings require a verified routing update"
            )
        settings.owner_phone = number
        settings.notifications_enabled = False
        try:
            db.commit()
            db.refresh(settings)
        except Exception:
            db.rollback()
            raise HTTPException(502, "Could not save the approved phone number")
        return {
            **public_status(shop, settings, db),
            "pending_provider_configuration": True,
            "live_call_test_required": True,
            "message": (
                "Owner phone saved. HighLevel forwarding, timeout, and voicemail "
                "backup must be verified before calls and alerts can be activated."
            ),
        }

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
            **public_status(shop, settings, db),
            "pending_provisioning": True,
            "live_call_test_required": True,
            "message": (
                "Phone number saved. Voicemail notifications remain off "
                "until AI Receptionist provisioning and transfer verification finish."
            ),
        }

    # A new shop may approve its owner destination before an operator has
    # authorized real test calls. Save that approval as pending without
    # touching HighLevel transfers or enabling the Twilio relay. The normal
    # onboarding resume POST will finish it after test-call authorization.
    # Never take this path for an already-active relay: changing its saved
    # destination would immediately change live forwarding.
    relay = db.get(DayTelloVoiceRelayAssignment, shop.id)
    if (relay and not relay.enabled and not settings.notifications_enabled
            and (os.getenv("DAYTELLO_VOICE_RELAY_ALLOW_TEST_CALLS") != "true"
                 or not str(shop.highlevel_phone_number or "").strip())):
        # Even with test-call permission, do not turn on a relay before the
        # customer-selected HighLevel AI number has been activated. The
        # number-selection endpoint will resume this saved owner destination.
        pending_ai_number = not str(shop.highlevel_phone_number or "").strip()
        settings.owner_phone = number
        settings.notifications_enabled = False
        try:
            db.commit()
            db.refresh(settings)
        except Exception:
            db.rollback()
            raise HTTPException(502, "Could not save the approved phone number")
        return {
            **public_status(shop, settings, db),
            "pending_test_authorization": (
                os.getenv("DAYTELLO_VOICE_RELAY_ALLOW_TEST_CALLS") != "true"
            ),
            "pending_ai_number": pending_ai_number,
            "live_call_test_required": True,
            "message": (
                "Owner phone saved. Activate the AI Receptionist number to "
                "finish forwarding and voicemail SMS."
                if pending_ai_number
                else "Owner phone saved. Call forwarding and voicemail SMS "
                     "remain off until isolated test calls are authorized."
            ),
        }

    if os.getenv("DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED") != "true":
        raise HTTPException(409, "Voicemail notification setup is not yet ready")

    # This temporary test allowlist prevents any new number receiving
    # voicemail SMS until it has been explicitly approved.
    settings_proxy = type("RequestedNotification", (), {
        "notifications_enabled": True, "owner_phone": number,
    })()
    owner_phone_for_test_shop(shop.slug, settings_proxy, db=db, shop_id=shop.id)
    link_cipher()
    _recording_link_origin_for_shop(shop, settings, db)
    sender = os.getenv("HIGHLEVEL_SMS_FROM_NUMBER", "").strip()
    if not PHONE.fullmatch(sender):
        raise HTTPException(503, "SMS sender is not configured")

    # For a programmable relay DID, verify the Twilio inbound webhook
    # before changing the HighLevel AI transfer. Activation remains test-only
    # and requires a separate platform permission for live test calls.
    relay = db.get(DayTelloVoiceRelayAssignment, shop.id)
    if relay:
        if relay.relay_number != settings.receiving_number:
            raise HTTPException(409, "Relay number and voicemail settings disagree")
        if os.getenv("DAYTELLO_VOICE_RELAY_ALLOW_TEST_CALLS") != "true":
            raise HTTPException(409, "Voice relay live testing is not enabled")
        verified_relay = VoiceRelayNumberProvider().find_existing(
            str(shop.id), expected_number=relay.relay_number)
        if not verified_relay or not verified_relay.get("route_verified"):
            raise HTTPException(409, "Relay provider routing could not be verified")

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
    if relay:
        # Enabled only after authenticated owner approval, provider read-back,
        # safe destination validation and verified HighLevel transfer.
        relay.enabled = True
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
        **public_status(shop, settings, db),
        "call_transfer_enabled": True,
        "test_relay_enabled_for_calls": bool(relay),
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
    approved_owner_recipient(shop.slug, settings.owner_phone, db=db, shop_id=shop.id)
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
        **public_status(shop, settings, db),
        "call_routing_changed": False,
        "recording_delivery_test_required": True,
        "message": "Test voicemail SMS activated; call routing was not modified.",
    }


class OwnerSMSVerificationStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone_number: str
    consent_to_verification_sms: bool = False

    @field_validator("phone_number")
    @classmethod
    def valid_number(cls, value):
        if not PHONE.fullmatch(value):
            raise ValueError("Enter a US phone number including +1")
        return value


class OwnerSMSVerificationConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone_number: str
    code: str

    @field_validator("phone_number")
    @classmethod
    def valid_number(cls, value):
        if not PHONE.fullmatch(value):
            raise ValueError("Enter a US phone number including +1")
        return value


@router.post("/shops/{shop_slug}/voicemail-owner/verification/start")
def begin_owner_sms_verification(
    shop_slug: str,
    payload: OwnerSMSVerificationStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verify an owner's number without per-shop Railway allowlist edits.

    This sends a verification text only with explicit consent and does not
    enable voicemail alerts or alter live phone routing.
    """
    shop = owner_shop(db, shop_slug, current_user)
    if (not shop.highlevel_agent_id
            or not shop.highlevel_location_id
            or shop.highlevel_location_id != os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()):
        raise HTTPException(409, "Shop SMS connection is not verified")
    reject_internal_owner_destination(db, payload.phone_number, shop.id)
    sender = os.getenv("HIGHLEVEL_SMS_FROM_NUMBER", "").strip()
    return start_owner_verification(
        db, shop.id, payload.phone_number,
        consent=payload.consent_to_verification_sms, sender=sender,
    )


@router.post("/shops/{shop_slug}/voicemail-owner/verification/confirm")
def complete_owner_sms_verification(
    shop_slug: str,
    payload: OwnerSMSVerificationConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Possession check only; subsequent setup must still verify routing."""
    shop = owner_shop(db, shop_slug, current_user)
    reject_internal_owner_destination(db, payload.phone_number, shop.id)
    return confirm_owner_verification(
        db, shop.id, payload.phone_number, payload.code,
    )


@router.post("/shops/{shop_slug}/voicemail-owner/notifications/disable")
def disable_owner_sms_notifications(
    shop_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Owner-initiated SMS opt-out; no external provider or routing changes."""
    shop = owner_shop(db, shop_slug, current_user)
    return disable_owner_voicemail_notifications(db, shop.id)
