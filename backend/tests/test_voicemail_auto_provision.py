"""Offline reserved voicemail DID allocation safeguards."""
import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Shop
from app.voicemail_models import DayTelloVoicemailShopSettings
from app import voicemail_auto_provision as auto


class ReservedNumberTests(unittest.TestCase):
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
                     ai_voice_enabled=True, highlevel_location_id="loc-a"),
                Shop(id="shop-b", slug="shop-b", name="Shop B",
                     ai_voice_enabled=True, highlevel_location_id="loc-a"),
            ])
            db.commit()
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "HIGHLEVEL_LOCATION_ID": "loc-a",
            "DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP": "",
            "DAYTELLO_VOICEMAIL_TEST_NUMBER_POOL": '["+12025550121","+12025550122"]',
        })
        self.env.start()
        self.inventory = patch.object(auto, "get_location_phone_numbers", return_value=(
            {}, [{"phoneNumber": "+12025550121"}, {"phoneNumber": "+12025550122"}]
        ))
        self.inventory.start()

    def tearDown(self):
        self.inventory.stop()
        self.env.stop()
        self.engine.dispose()

    def test_explicit_label_recovers_second_shop_without_sms(self):
        with self.factory() as db:
            db.get(Shop, "shop-b").name = "Bob's Shop"
            db.commit()
        with patch.object(auto, "get_location_phone_numbers", return_value=(
            {}, [{"phoneNumber": "+12025550122",
                  "friendlyName": "Bob's Shop - Voicemail TEST"}]
        )):
            with self.factory() as db:
                bound = auto.bind_explicitly_labeled_test_voicemail(
                    "loc-a", "+12025550122", db)
                self.assertEqual(bound.shop_id, "shop-b")
                self.assertFalse(bound.notifications_enabled)
                self.assertIsNone(bound.owner_phone)
                self.assertIsNone(auto.bind_explicitly_labeled_test_voicemail(
                    "loc-a", "+12025550122", db))
                self.assertEqual(db.query(DayTelloVoicemailShopSettings).count(), 1)

    def test_unlabeled_number_cannot_be_claimed(self):
        with patch.object(auto, "get_location_phone_numbers", return_value=(
            {}, [{"phoneNumber": "+12025550122", "friendlyName": ""}]
        )):
            with self.factory() as db:
                self.assertIsNone(auto.bind_explicitly_labeled_test_voicemail(
                    "loc-a", "+12025550122", db))
                self.assertEqual(db.query(DayTelloVoicemailShopSettings).count(), 0)

    def test_labeled_number_must_not_reassign_legacy_or_other_location(self):
        os.environ["DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP"] = (
            '{"+12025550122":"shop-a"}'
        )
        with self.factory() as db:
            self.assertIsNone(auto.bind_explicitly_labeled_test_voicemail(
                "loc-a", "+12025550122", db))
            self.assertIsNone(auto.bind_explicitly_labeled_test_voicemail(
                "other-loc", "+12025550122", db))
            self.assertEqual(db.query(DayTelloVoicemailShopSettings).count(), 0)

    def test_idempotent_and_exclusive_allocation(self):
        with self.factory() as db:
            a = db.get(Shop, "shop-a")
            first = auto.ensure_test_voicemail_number(a, db)
            self.assertEqual(first.receiving_number, "+12025550121")
            again = auto.ensure_test_voicemail_number(a, db)
            self.assertEqual(again.receiving_number, first.receiving_number)
            b = auto.ensure_test_voicemail_number(db.get(Shop, "shop-b"), db)
            self.assertEqual(b.receiving_number, "+12025550122")
            self.assertEqual(db.query(DayTelloVoicemailShopSettings).count(), 2)
            self.assertFalse(b.notifications_enabled)

    def test_no_unreserved_number_is_taken(self):
        os.environ["DAYTELLO_VOICEMAIL_TEST_NUMBER_POOL"] = '["+12025550129"]'
        with self.factory() as db:
            with self.assertRaises(HTTPException) as error:
                auto.ensure_test_voicemail_number(db.get(Shop, "shop-a"), db)
            self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(db.query(DayTelloVoicemailShopSettings).count(), 0)

    def test_legacy_shop_mapping_stays_authoritative(self):
        os.environ["DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP"] = (
            '{"+12025550121":"shop-b"}'
        )
        with self.factory() as db:
            a = auto.ensure_test_voicemail_number(db.get(Shop, "shop-a"), db)
            self.assertEqual(a.receiving_number, "+12025550122")
            b = auto.ensure_test_voicemail_number(db.get(Shop, "shop-b"), db)
            self.assertEqual(b.receiving_number, "+12025550121")

    def test_allocation_rejects_ai_number(self):
        with self.factory() as db:
            a = db.get(Shop, "shop-a")
            a.highlevel_phone_number = "+12025550121"
            db.commit()
            result = auto.ensure_test_voicemail_number(a, db)
            self.assertEqual(result.receiving_number, "+12025550122")

    def test_disabled_test_mode_blocks_allocation(self):
        os.environ["DAYTELLO_VOICEMAIL_TEST_ONLY"] = "false"
        with self.factory() as db:
            with self.assertRaises(HTTPException) as error:
                auto.ensure_test_voicemail_number(db.get(Shop, "shop-a"), db)
            self.assertEqual(error.exception.status_code, 409)

    def test_duplicate_reservation_fails_closed(self):
        os.environ["DAYTELLO_VOICEMAIL_TEST_NUMBER_POOL"] = (
            '["+12025550121","+12025550121"]'
        )
        with self.factory() as db:
            with self.assertRaises(HTTPException) as error:
                auto.ensure_test_voicemail_number(db.get(Shop, "shop-a"), db)
            self.assertEqual(error.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
