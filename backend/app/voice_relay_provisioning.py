"""Idempotent test-shop relay DID claim, disabled until a real call is verified.

Never called automatically on production requests. Purchases require explicit
approval and a PostgreSQL row lock for the duration of provider operations.
The adapter is intentionally independent of HighLevel's legacy DID pool.
"""
import os

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.models import Shop
from app.voice_relay_models import DayTelloVoiceRelayAssignment
from app.voice_relay_provider import VoiceRelayNumberProvider, US_NUMBER
from app.voicemail_models import DayTelloVoicemailShopSettings


def _require_purchase_lock(db, approved):
    # SQLite ignores SELECT FOR UPDATE, so never allow chargeable purchases
    # on an unprotected database. The shop row lock serializes all callers
    # of this service for the same shop on PostgreSQL.
    if approved and db.get_bind().dialect.name != "postgresql":
        raise HTTPException(503, "Relay purchase requires a locking database")


def _check_number_conflicts(db, shop_id, number):
    if db.query(Shop).filter(or_(
        Shop.highlevel_phone_number == number, Shop.phone == number,
    )).first() is not None:
        raise HTTPException(409, "Relay number conflicts with a business line")
    voicemail = db.query(DayTelloVoicemailShopSettings).filter(
        DayTelloVoicemailShopSettings.receiving_number == number,
    ).first()
    if voicemail is not None and voicemail.shop_id != shop_id:
        raise HTTPException(409, "Relay number belongs to another voicemail shop")
    assigned = db.query(DayTelloVoiceRelayAssignment).filter(
        DayTelloVoiceRelayAssignment.relay_number == number,
    ).first()
    if assigned is not None and assigned.shop_id != shop_id:
        raise HTTPException(409, "Relay number belongs to another shop")
    return voicemail, assigned


def reserve_or_purchase_relay_for_shop(shop: Shop, db, number: str, *,
                                       approved=False, provider=None):
    """Prepare a DID with no active routing; repeat calls are idempotent.

    The caller must already have authenticated this shop's owner. This service
    must not be invoked for another tenant or as a background auto-purchase.
    It does not change HighLevel agent actions, call forwarding or SMS opt-in.
    """
    if os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true":
        raise HTTPException(404, "Voice relay provisioning is disabled")
    if not isinstance(number, str) or not US_NUMBER.fullmatch(number):
        raise HTTPException(422, "Invalid relay phone number")
    expected_location = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    if (not shop.ai_voice_enabled or not shop.highlevel_agent_id
            or not expected_location or shop.highlevel_location_id != expected_location):
        raise HTTPException(409, "Shop AI Receptionist connection is incomplete")
    _require_purchase_lock(db, approved)
    # Keep this transaction open across provider calls. A concurrent setup
    # for the same shop cannot purchase a second DID in PostgreSQL.
    locked = db.query(Shop).filter(Shop.id == shop.id).with_for_update().one_or_none()
    if locked is None or locked.id != shop.id:
        raise HTTPException(404, "Shop not found")
    settings, existing = _check_number_conflicts(db, shop.id, number)
    if existing and existing.relay_number != number:
        raise HTTPException(409, "Shop has a different relay number")
    if settings and settings.receiving_number != number:
        raise HTTPException(409, "Shop has a different voicemail number")
    other_shop_relay = db.get(DayTelloVoiceRelayAssignment, shop.id)
    if other_shop_relay and other_shop_relay.relay_number != number:
        raise HTTPException(409, "Shop has a different relay number")
    other_shop_settings = db.get(DayTelloVoicemailShopSettings, shop.id)
    if other_shop_settings and other_shop_settings.receiving_number != number:
        raise HTTPException(409, "Shop has a different voicemail number")

    provider = provider or VoiceRelayNumberProvider()
    # Even a saved DID must be rechecked against live provider inventory.
    verified = provider.purchase_approved_number(
        str(shop.id), number, approved=approved)
    if not verified.get("route_verified") or verified.get("number") != number:
        raise HTTPException(409, "Provider DID route was not verified")
    # Recheck local conflicts after the remote operation, before DB commit.
    _check_number_conflicts(db, shop.id, number)
    if not other_shop_relay:
        db.add(DayTelloVoiceRelayAssignment(
            shop_id=shop.id, relay_number=number, enabled=False))
    if not other_shop_settings:
        db.add(DayTelloVoicemailShopSettings(
            shop_id=shop.id, location_id=expected_location,
            receiving_number=number, owner_phone=None,
            notifications_enabled=False,
        ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # A purchased DID is not released here: the provider label allows
        # safe recovery without another charge on the next attempt.
        raise HTTPException(409, "Relay number claim was assigned concurrently")
    return {
        "shop_slug": shop.slug, "relay_number": number,
        "provider_route_verified": True,
        "enabled_for_calls": bool(other_shop_relay and other_shop_relay.enabled),
        "live_call_test_required": True,
    }


def reserve_relay_for_area_code(shop: Shop, db, area_code: str, *,
                                approved=False, provider=None):
    """Zero-touch number selection after a shop-level purchase approval.

    Existing assignments are always recovered first; a retry never chooses
    a second number merely because availability inventory has changed.
    """
    provider = provider or VoiceRelayNumberProvider()
    existing = db.get(DayTelloVoiceRelayAssignment, shop.id)
    if existing:
        return reserve_or_purchase_relay_for_shop(
            shop, db, existing.relay_number,
            approved=False, provider=provider,
        )
    if approved is not True:
        raise HTTPException(409, "Voice relay purchase is not authorized")
    # Do not select a number before verifying the platform is in test mode.
    if os.getenv("DAYTELLO_VOICE_RELAY_TEST_ONLY") != "true":
        raise HTTPException(404, "Voice relay provisioning is disabled")
    number = provider.find_available_voice_number(area_code)
    return reserve_or_purchase_relay_for_shop(
        shop, db, number, approved=True, provider=provider,
    )
