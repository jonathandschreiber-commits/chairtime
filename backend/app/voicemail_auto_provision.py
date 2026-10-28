"""Conservative test-only auto-allocation of a dedicated voicemail number.

A shop owner never chooses or configures a HighLevel voicemail DID.
DayTello selects exclusively from numbers the platform has *already reserved*
and verifies ownership against live HighLevel inventory. This code does not
purchase a number or change upstream call forwarding.
"""
import json
import os

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import Shop
from app.routes.ai_setup import get_location_phone_numbers, get_phone_inbound_service
from app.routes.voicemail_webhook import configured_routing_map, valid_phone
from app.voicemail_models import DayTelloVoicemailShopSettings


def reserved_numbers_for_shop(shop_slug: str) -> list[str]:
    """Prefer the previously proven legacy mapping; else use reserved pool.

    No implicit choice from all numbers in a HighLevel subaccount: those may
    belong to other shops or already handle live calls.
    """
    legacy_raw = os.getenv("DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP", "").strip()
    legacy = configured_routing_map() if legacy_raw else {}
    legacy_for_shop = [n for n, slug in legacy.items() if slug == shop_slug]

    pool_raw = os.getenv("DAYTELLO_VOICEMAIL_TEST_NUMBER_POOL", "").strip()
    try:
        pool = json.loads(pool_raw) if pool_raw else []
    except (TypeError, ValueError):
        raise HTTPException(503, "Reserved voicemail number pool is invalid")
    if (not isinstance(pool, list)
            or any(not valid_phone(n) for n in pool)
            or len(set(pool)) != len(pool)):
        raise HTTPException(503, "Reserved voicemail number pool is invalid")
    return legacy_for_shop + [
        n for n in pool if n not in legacy and n not in legacy_for_shop
    ]


def ensure_test_voicemail_number(shop: Shop, db):
    """Idempotently bind an exclusively reserved and provider-verified DID.

    A binding is created with SMS disabled. Caller-transfer configuration and
    the owner's phone number are separate subsequent steps.
    """
    if os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true":
        raise HTTPException(409, "Automatic voicemail setup is not enabled")

    expected_location = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    location_id = str(shop.highlevel_location_id or "").strip()
    if not location_id or location_id != expected_location:
        raise HTTPException(409, "Business phone connection is not verified")
    if not shop.ai_voice_enabled:
        raise HTTPException(409, "AI Receptionist is not enabled")

    existing = db.get(DayTelloVoicemailShopSettings, shop.id)
    if existing:
        if existing.location_id != location_id or not valid_phone(existing.receiving_number):
            raise HTTPException(409, "Existing voicemail route needs review")
        return existing

    candidates = reserved_numbers_for_shop(shop.slug)
    if not candidates:
        raise HTTPException(409, "DayTello has not assigned a voicemail number for this business")

    # Compare every HighLevel number to both current and previous shop claims.
    # Never use another tenant's business or AI number as voicemail.
    all_shops = db.query(Shop).all()
    other_shop_numbers = {
        number
        for other in all_shops if other.id != shop.id
        for number in (other.highlevel_phone_number, other.phone)
        if number
    }
    _, inventory = get_location_phone_numbers(location_id)
    inventory_by_number = {}
    for item in inventory:
        if isinstance(item, dict) and valid_phone(item.get("phoneNumber")):
            inventory_by_number.setdefault(item["phoneNumber"], []).append(item)

    for number in candidates:
        if number in other_shop_numbers:
            continue
        if number in (shop.highlevel_phone_number, shop.phone):
            continue
        if db.query(DayTelloVoicemailShopSettings).filter(
            DayTelloVoicemailShopSettings.location_id == location_id,
            DayTelloVoicemailShopSettings.receiving_number == number,
        ).first():
            continue
        records = inventory_by_number.get(number, [])
        if len(records) != 1:
            continue
        if get_phone_inbound_service(records[0]).get("type") == "voice_ai":
            continue

        binding = DayTelloVoicemailShopSettings(
            shop_id=shop.id, location_id=location_id,
            receiving_number=number, owner_phone=None,
            notifications_enabled=False,
        )
        db.add(binding)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Voicemail number was assigned concurrently")
        db.refresh(binding)
        return binding

    raise HTTPException(409, "No safe, available voicemail number for this business")
