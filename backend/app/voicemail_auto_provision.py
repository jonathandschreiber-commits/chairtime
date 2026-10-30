"""Conservative test-only auto-allocation of a dedicated voicemail number.

A shop owner never chooses or configures a HighLevel voicemail DID.
DayTello selects exclusively from numbers the platform has *already reserved*
and verifies ownership against live HighLevel inventory. This code does not
purchase a number or change upstream call forwarding.
"""
import json
import logging
import os

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import Shop
from app.voice_relay_models import DayTelloVoiceRelayAssignment
from app.routes.ai_setup import get_location_phone_numbers, get_phone_inbound_service
from app.routes.voicemail_webhook import configured_routing_map, valid_phone
from app.voicemail_models import DayTelloVoicemailShopSettings

logger = logging.getLogger(__name__)


def verified_phone_inventory(location_id: str):
    """Read inventory, recording only non-sensitive upstream error metadata.

    HighLevel API errors are mapped to HTTP 502 by ai_setup. Logging its
    upstream status clarifies expired tokens vs missing phonenumbers.read
    without disclosing bearer tokens, phone numbers or response bodies.
    """
    try:
        return get_location_phone_numbers(location_id)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        upstream = detail.get("highlevel_status")
        logger.warning(
            "DayTello voicemail number inventory verification failed: "
            "upstream_status=%s gateway_status=%s",
            upstream if isinstance(upstream, int) else "unavailable",
            exc.status_code,
        )
        raise


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
        # A saved DID is not automatically safe forever. A cross-tenant
        # business line, relay (even disabled), or cross-location claim must
        # stop setup rather than being accepted as an idempotent success.
        number = existing.receiving_number
        if (
            number in (shop.highlevel_phone_number, shop.phone)
            or db.query(Shop).filter(
                Shop.id != shop.id,
                (Shop.highlevel_phone_number == number) | (Shop.phone == number),
            ).first() is not None
            or db.query(DayTelloVoiceRelayAssignment).filter(
                DayTelloVoiceRelayAssignment.relay_number == number,
            ).first() is not None
            or db.query(DayTelloVoicemailShopSettings).filter(
                DayTelloVoicemailShopSettings.shop_id != shop.id,
                DayTelloVoicemailShopSettings.receiving_number == number,
            ).first() is not None
        ):
            raise HTTPException(409, "Existing voicemail number conflicts with another route")
        legacy_raw = os.getenv("DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP", "").strip()
        if legacy_raw and configured_routing_map().get(number) not in (None, shop.slug):
            raise HTTPException(409, "Existing voicemail number conflicts with legacy mapping")
        # A previously saved database claim is not proof that the DID is
        # still assigned to this HighLevel location or remains a non-AI line.
        # Revalidate before treating a repeat setup request as successful.
        _, inventory = verified_phone_inventory(location_id)
        matches = [
            item for item in inventory
            if isinstance(item, dict) and item.get("phoneNumber") == number
        ]
        if len(matches) != 1 or get_phone_inbound_service(matches[0]).get("type") == "voice_ai":
            raise HTTPException(409, "Existing voicemail number needs provider verification")
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
    _, inventory = verified_phone_inventory(location_id)
    inventory_by_number = {}
    for item in inventory:
        if isinstance(item, dict) and valid_phone(item.get("phoneNumber")):
            inventory_by_number.setdefault(item["phoneNumber"], []).append(item)

    for number in candidates:
        if number in other_shop_numbers:
            continue
        # Programmable voice relay assignments are independent of HighLevel
        # voicemail settings. Never claim the same DID in both systems, even
        # when the relay is currently disabled and could be enabled later.
        if db.query(DayTelloVoiceRelayAssignment).filter(
            DayTelloVoiceRelayAssignment.relay_number == number,
        ).first() is not None:
            continue
        if number in (shop.highlevel_phone_number, shop.phone):
            continue
        if db.query(DayTelloVoicemailShopSettings).filter(
            # A physical DID is exclusive across all HighLevel locations.
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


def bind_explicitly_labeled_test_voicemail(location_id: str, number: str, db):
    """Recover a test DID named "<Shop name> - Voicemail TEST" in HighLevel.

    Only called for a signed voicemail event after confirming the location.
    Read-only provider verification precedes an exclusive database binding.
    This does *not* enable owner SMS, purchase a number, or change call routes.
    A missing/ambiguous match is ignored, never guessed by arrival order.
    The usual authenticated owner-onboarding path is preferred for new shops.
    """
    if os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true":
        return None
    if not valid_phone(number):
        return None
    expected_location = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    if not expected_location or location_id != expected_location:
        return None

    # Legacy assignments remain authoritative and cannot be re-claimed.
    legacy_raw = os.getenv("DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP", "").strip()
    legacy = configured_routing_map() if legacy_raw else {}
    if number in legacy:
        return None

    # Never take over an AI line, a business number, or an existing tenant route.
    shops = db.query(Shop).all()
    if any(
        number in (shop.highlevel_phone_number, shop.phone)
        for shop in shops
    ):
        return None
    if db.query(DayTelloVoicemailShopSettings).filter(
        # A DID claimed in another location is still unavailable.
        DayTelloVoicemailShopSettings.receiving_number == number,
    ).first():
        return None
    # A previously claimed programmable relay DID must not be silently
    # reassigned by the signed-event recovery path either.
    if db.query(DayTelloVoiceRelayAssignment).filter(
        DayTelloVoiceRelayAssignment.relay_number == number,
    ).first() is not None:
        return None

    _, inventory = verified_phone_inventory(location_id)
    matched = [
        record for record in inventory
        if isinstance(record, dict) and record.get("phoneNumber") == number
    ]
    if len(matched) != 1:
        return None
    record = matched[0]
    if get_phone_inbound_service(record).get("type") == "voice_ai":
        return None

    # Require an exact human-verified test label, not a fuzzy name or a
    # guessed match based solely on caller-controlled webhook data.
    label = str(record.get("friendlyName") or "").strip()
    candidates = [
        shop for shop in shops
        if (
            shop.ai_voice_enabled
            and shop.highlevel_location_id == location_id
            and label == f"{shop.name} - Voicemail TEST"
            and db.get(DayTelloVoicemailShopSettings, shop.id) is None
        )
    ]
    if len(candidates) != 1:
        return None

    binding = DayTelloVoicemailShopSettings(
        shop_id=candidates[0].id,
        location_id=location_id,
        receiving_number=number,
        owner_phone=None,
        notifications_enabled=False,
    )
    db.add(binding)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Concurrent voicemail assignment requires review")
    db.refresh(binding)
    return binding
