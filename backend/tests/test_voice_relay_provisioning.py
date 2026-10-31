"""Offline exclusive DID claim tests; all provider operations are mocked."""
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Shop
from app.voice_relay_models import DayTelloVoiceRelayAssignment
from app.voice_relay_provisioning import (
    reserve_or_purchase_relay_for_shop, reserve_relay_for_area_code,
)
from app.voicemail_models import DayTelloVoicemailShopSettings

NUMBER = "+12405550123"
OTHER = "+12405550124"


class FakeProvider:
    def __init__(self, *, error=None):
        self.calls = []
        self.selections = []
        self.error = error

    def find_available_voice_number(self, area_code):
        self.selections.append(area_code)
        return NUMBER

    def purchase_approved_number(self, shop_id, number, *, approved=False):
        self.calls.append((shop_id, number, approved))
        if self.error:
            raise self.error
        return {"number": number, "provider_sid": "PN" + "c" * 32,
                "route_verified": True}


class ClaimTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            db.add_all([
                Shop(id="shop-a", slug="shop-a", name="Shop A",
                     ai_voice_enabled=True, highlevel_location_id="loc-a",
                     highlevel_agent_id="agent-a"),
                Shop(id="shop-b", slug="shop-b", name="Shop B",
                     ai_voice_enabled=True, highlevel_location_id="loc-a",
                     highlevel_agent_id="agent-b"),
            ])
            db.commit()
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICE_RELAY_TEST_ONLY": "true",
            "HIGHLEVEL_LOCATION_ID": "loc-a",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.engine.dispose()

    def reserve(self, db, shop_id="shop-a", number=NUMBER, **kwargs):
        return reserve_or_purchase_relay_for_shop(
            db.get(Shop, shop_id), db, number, **kwargs)

    def test_area_code_flow_requires_purchase_approval(self):
        provider = FakeProvider()
        with self.factory() as db:
            with self.assertRaises(HTTPException) as error:
                reserve_relay_for_area_code(
                    db.get(Shop, "shop-a"), db, "240", provider=provider)
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(provider.selections)
        self.assertFalse(provider.calls)

    def test_area_code_flow_selects_number_after_approval(self):
        provider = FakeProvider()
        with patch("app.voice_relay_provisioning._require_purchase_lock"):
            with self.factory() as db:
                result = reserve_relay_for_area_code(
                    db.get(Shop, "shop-a"), db, "240",
                    approved=True, provider=provider)
        self.assertEqual(result["relay_number"], NUMBER)
        self.assertEqual(provider.selections, ["240"])
        self.assertEqual(provider.calls, [("shop-a", NUMBER, True)])

    def test_area_code_retry_reuses_saved_did_without_new_selection(self):
        provider = FakeProvider()
        with self.factory() as db:
            self.reserve(db, provider=provider)
            result = reserve_relay_for_area_code(
                db.get(Shop, "shop-a"), db, "301", provider=provider)
        self.assertEqual(result["relay_number"], NUMBER)
        self.assertFalse(provider.selections)
        self.assertEqual(provider.calls[-1], ("shop-a", NUMBER, False))

    def test_creates_exclusive_disabled_claim_and_owner_settings(self):
        provider = FakeProvider()
        with self.factory() as db:
            result = self.reserve(db, provider=provider)
            self.assertEqual(result["relay_number"], NUMBER)
            self.assertFalse(result["enabled_for_calls"])
            self.assertTrue(result["live_call_test_required"])
            claim = db.get(DayTelloVoiceRelayAssignment, "shop-a")
            settings = db.get(DayTelloVoicemailShopSettings, "shop-a")
            self.assertEqual(claim.relay_number, NUMBER)
            self.assertFalse(claim.enabled)
            self.assertEqual(settings.receiving_number, NUMBER)
            self.assertFalse(settings.notifications_enabled)
            self.assertIsNone(settings.owner_phone)
        self.assertEqual(provider.calls, [("shop-a", NUMBER, False)])

    def test_repeated_claim_does_not_create_duplicate_rows(self):
        provider = FakeProvider()
        with self.factory() as db:
            self.reserve(db, provider=provider)
            self.reserve(db, provider=provider)
            self.assertEqual(db.query(DayTelloVoiceRelayAssignment).count(), 1)
            self.assertEqual(db.query(DayTelloVoicemailShopSettings).count(), 1)

    def test_other_shop_cannot_claim_same_number(self):
        provider = FakeProvider()
        with self.factory() as db:
            self.reserve(db, provider=provider)
            with self.assertRaises(HTTPException) as error:
                self.reserve(db, "shop-b", provider=provider)
            self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(len(provider.calls), 1)

    def test_cannot_claim_published_business_or_ai_number(self):
        provider = FakeProvider()
        with self.factory() as db:
            db.get(Shop, "shop-b").phone = NUMBER
            db.commit()
            with self.assertRaises(HTTPException):
                self.reserve(db, provider=provider)
            self.assertFalse(provider.calls)

    def test_cannot_claim_existing_legacy_voicemail_did(self):
        provider = FakeProvider()
        with self.factory() as db:
            db.add(DayTelloVoicemailShopSettings(
                shop_id="shop-b", location_id="loc-a",
                receiving_number=NUMBER, notifications_enabled=False,
            ))
            db.commit()
            with self.assertRaises(HTTPException):
                self.reserve(db, provider=provider)
            self.assertFalse(provider.calls)

    def test_same_shop_legacy_voicemail_did_is_not_adopted_as_relay(self):
        # Existing HighLevel voicemail routes must remain untouched even
        # when the legacy DID belongs to the requesting shop.
        provider = FakeProvider()
        with self.factory() as db:
            db.add(DayTelloVoicemailShopSettings(
                shop_id="shop-a", location_id="loc-a",
                receiving_number=NUMBER, notifications_enabled=True,
            ))
            db.commit()
            with self.assertRaises(HTTPException) as error:
                self.reserve(db, provider=provider)
            self.assertEqual(error.exception.status_code, 409)
            self.assertIsNone(db.get(DayTelloVoiceRelayAssignment, "shop-a"))
            self.assertTrue(db.get(DayTelloVoicemailShopSettings, "shop-a").notifications_enabled)
        self.assertFalse(provider.calls)

    def test_legacy_highlevel_route_is_not_adopted_as_relay(self):
        # The legacy map may be authoritative even without a database row.
        for slug in ("shop-a", "shop-b"):
            with self.subTest(legacy_shop=slug):
                provider = FakeProvider()
                with patch.dict(os.environ, {
                    "DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP":
                        '{"' + NUMBER + '":"' + slug + '"}',
                    "DAYTELLO_VOICEMAIL_TEST_NUMBER_POOL": "",
                }):
                    with self.factory() as db:
                        with self.assertRaises(HTTPException) as error:
                            self.reserve(db, provider=provider)
                        self.assertEqual(error.exception.status_code, 409)
                        self.assertIsNone(db.get(DayTelloVoiceRelayAssignment, "shop-a"))
                self.assertFalse(provider.calls)

    def test_reserved_highlevel_test_pool_is_not_relay_inventory(self):
        provider = FakeProvider()
        with patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP": "",
            "DAYTELLO_VOICEMAIL_TEST_NUMBER_POOL": '["' + NUMBER + '"]',
        }):
            with self.factory() as db:
                with self.assertRaises(HTTPException) as error:
                    self.reserve(db, provider=provider)
                self.assertEqual(error.exception.status_code, 409)
                self.assertIsNone(db.get(DayTelloVoiceRelayAssignment, "shop-a"))
        self.assertFalse(provider.calls)

    def test_malformed_legacy_reservations_fail_before_provider_calls(self):
        for key, invalid in (
            ("DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP", "{invalid"),
            ("DAYTELLO_VOICEMAIL_TEST_NUMBER_POOL", "{invalid"),
            ("DAYTELLO_VOICEMAIL_TEST_NUMBER_POOL", '["' + NUMBER + '","' + NUMBER + '"]'),
        ):
            with self.subTest(setting=key, value=invalid):
                provider = FakeProvider()
                with patch.dict(os.environ, {
                    "DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP": "",
                    "DAYTELLO_VOICEMAIL_TEST_NUMBER_POOL": "",
                    key: invalid,
                }):
                    with self.factory() as db:
                        with self.assertRaises(HTTPException) as error:
                            self.reserve(db, provider=provider)
                        self.assertEqual(error.exception.status_code, 503)
                self.assertFalse(provider.calls)

    def test_existing_relay_rejects_mismatched_voicemail_location(self):
        # A stale cross-location settings row is not proof of a safe relay.
        provider = FakeProvider()
        with self.factory() as db:
            db.add(DayTelloVoiceRelayAssignment(
                shop_id="shop-a", relay_number=NUMBER, enabled=False,
            ))
            db.add(DayTelloVoicemailShopSettings(
                shop_id="shop-a", location_id="other-location",
                receiving_number=NUMBER, notifications_enabled=False,
            ))
            db.commit()
            with self.assertRaises(HTTPException) as error:
                self.reserve(db, provider=provider)
            self.assertEqual(error.exception.status_code, 409)
            self.assertFalse(db.get(DayTelloVoiceRelayAssignment, "shop-a").enabled)
        self.assertFalse(provider.calls)

    def test_cannot_replace_existing_shops_relay(self):
        provider = FakeProvider()
        with self.factory() as db:
            self.reserve(db, provider=provider)
            with self.assertRaises(HTTPException):
                self.reserve(db, number=OTHER, provider=provider)
            self.assertEqual(len(provider.calls), 1)

    def test_provider_failure_never_claims_number(self):
        provider = FakeProvider(error=HTTPException(409, "Not available"))
        with self.factory() as db:
            with self.assertRaises(HTTPException):
                self.reserve(db, provider=provider)
            self.assertIsNone(db.get(DayTelloVoiceRelayAssignment, "shop-a"))
            self.assertIsNone(db.get(DayTelloVoicemailShopSettings, "shop-a"))

    def test_paid_purchase_requires_postgres_lock(self):
        provider = FakeProvider()
        with self.factory() as db:
            with self.assertRaises(HTTPException) as error:
                self.reserve(db, approved=True, provider=provider)
            self.assertEqual(error.exception.status_code, 503)
            self.assertFalse(provider.calls)

    def test_approved_purchase_calls_provider_after_lock_check(self):
        # Unit simulation only; SQLite does not provide row-level locking.
        provider = FakeProvider()
        with patch("app.voice_relay_provisioning._require_purchase_lock"):
            with self.factory() as db:
                self.reserve(db, approved=True, provider=provider)
        self.assertEqual(provider.calls, [("shop-a", NUMBER, True)])

    def test_unconnected_ai_shop_never_calls_provider(self):
        provider = FakeProvider()
        with self.factory() as db:
            db.get(Shop, "shop-a").highlevel_agent_id = None
            db.commit()
            with self.assertRaises(HTTPException):
                self.reserve(db, provider=provider)
        self.assertFalse(provider.calls)

    def test_feature_disabled_does_not_claim_number(self):
        provider = FakeProvider()
        with patch.dict(os.environ, {"DAYTELLO_VOICE_RELAY_TEST_ONLY": "false"}):
            with self.factory() as db:
                with self.assertRaises(HTTPException) as error:
                    self.reserve(db, provider=provider)
                self.assertEqual(error.exception.status_code, 404)
        self.assertFalse(provider.calls)


if __name__ == "__main__":
    unittest.main()
