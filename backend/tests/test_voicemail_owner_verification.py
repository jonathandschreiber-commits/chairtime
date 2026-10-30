"""Offline tests only: no live SMS, provider access, or call routing."""
import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Shop
from app.voicemail_owner_verification import (
    DayTelloVoicemailOwnerVerification, start_owner_verification,
    confirm_owner_verification, verified_owner_recipient,
)

PHONE = "+12025550199"
OTHER = "+12025550198"
SENDER = "+12025550124"


class OwnerVerificationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            db.add_all([
                Shop(id="shop-a", slug="shop-a", name="Shop A", ai_voice_enabled=True),
                Shop(id="shop-b", slug="shop-b", name="Shop B", ai_voice_enabled=True),
            ])
            db.commit()
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true",
            "DAYTELLO_VOICEMAIL_OWNER_VERIFICATION_ENABLED": "true",
            "DAYTELLO_VOICEMAIL_LINK_KEY": "x" * 48,
        })
        self.env.start()
        self.sent = []
        self.sms = patch(
            "app.routes.reminders.send_highlevel_sms",
            side_effect=self.fake_sms,
        )
        self.sms.start()

    def tearDown(self):
        self.sms.stop()
        self.env.stop()
        self.engine.dispose()

    def fake_sms(self, phone, message, **kwargs):
        self.sent.append((phone, message, kwargs))
        return {"success": True}

    def start(self, db, shop="shop-a", phone=PHONE, consent=True):
        return start_owner_verification(
            db, shop, phone, consent=consent, sender=SENDER,
        )

    def code(self):
        return self.sent[-1][1].split("code is ")[1].split(".")[0]

    def test_verification_requires_explicit_consent(self):
        with self.factory() as db:
            with self.assertRaises(HTTPException) as error:
                self.start(db, consent=False)
            self.assertEqual(error.exception.status_code, 409)
            self.assertFalse(self.sent)

    def test_verified_phone_is_exactly_shop_scoped(self):
        with self.factory() as db:
            result = self.start(db)
            self.assertFalse(result["notifications_enabled"])
            code = self.code()
            with self.assertRaises(HTTPException):
                verified_owner_recipient(db, "shop-a", PHONE)
            self.assertTrue(confirm_owner_verification(
                db, "shop-a", PHONE, code)["owner_number_verified"])
            self.assertEqual(verified_owner_recipient(db, "shop-a", PHONE), PHONE)
            with self.assertRaises(HTTPException):
                verified_owner_recipient(db, "shop-b", PHONE)
            with self.assertRaises(HTTPException):
                verified_owner_recipient(db, "shop-a", OTHER)
            with self.assertRaises(HTTPException):
                confirm_owner_verification(db, "shop-a", PHONE, code)

    def test_wrong_codes_lock_after_five_attempts(self):
        with self.factory() as db:
            self.start(db)
            code = self.code()
            wrong = "000000" if code != "000000" else "111111"
            for _ in range(5):
                with self.assertRaises(HTTPException):
                    confirm_owner_verification(db, "shop-a", PHONE, wrong)
            with self.assertRaises(HTTPException):
                confirm_owner_verification(db, "shop-a", PHONE, code)
            proof = db.get(DayTelloVoicemailOwnerVerification, "shop-a")
            self.assertIsNone(proof.challenge_digest)

    def test_cooldown_blocks_sms_spam(self):
        with self.factory() as db:
            self.start(db)
            with self.assertRaises(HTTPException) as error:
                self.start(db)
            self.assertEqual(error.exception.status_code, 429)
            self.assertEqual(len(self.sent), 1)

    def test_sms_failure_revokes_challenge(self):
        with patch(
            "app.routes.reminders.send_highlevel_sms",
            return_value={"success": False},
        ):
            with self.factory() as db:
                with self.assertRaises(HTTPException) as error:
                    self.start(db)
                self.assertEqual(error.exception.status_code, 502)
                proof = db.get(DayTelloVoicemailOwnerVerification, "shop-a")
                self.assertIsNone(proof.challenge_digest)

    def test_feature_flag_off_fails_closed(self):
        with patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_OWNER_VERIFICATION_ENABLED": "false",
        }):
            with self.factory() as db:
                with self.assertRaises(HTTPException) as error:
                    self.start(db)
                self.assertEqual(error.exception.status_code, 404)
        self.assertFalse(self.sent)

    def test_rejects_invalid_sender_and_recipient(self):
        with self.factory() as db:
            with self.assertRaises(HTTPException):
                self.start(db, phone="123")
            with self.assertRaises(HTTPException):
                start_owner_verification(
                    db, "shop-a", PHONE, consent=True, sender="123")
        self.assertFalse(self.sent)


if __name__ == "__main__":
    unittest.main()
