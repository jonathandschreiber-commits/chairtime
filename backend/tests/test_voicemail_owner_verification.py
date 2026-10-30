"""Offline tests only: no live SMS, provider access, or call routing."""
import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.database import get_db
from app.models import User
from app.routes.auth import get_current_user
from app.routes import voicemail_contact_number as contact_route
from app.voicemail_owner_links import approved_owner_recipient, owner_phone_for_test_shop
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Shop
from app.voicemail_models import DayTelloVoicemailShopSettings
from app.voicemail_owner_verification import (
    DayTelloVoicemailOwnerVerification, start_owner_verification,
    confirm_owner_verification, verified_owner_recipient,
    disable_owner_voicemail_notifications,
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
                Shop(id="shop-a", slug="shop-a", name="Shop A", ai_voice_enabled=True,
                     highlevel_location_id="loc-test", highlevel_agent_id="agent-a"),
                Shop(id="shop-b", slug="shop-b", name="Shop B", ai_voice_enabled=True),
            ])
            db.commit()
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true",
            "DAYTELLO_VOICEMAIL_OWNER_VERIFICATION_ENABLED": "true",
            "DAYTELLO_VOICEMAIL_LINK_KEY": "x" * 48,
            "HIGHLEVEL_LOCATION_ID": "loc-test",
            "HIGHLEVEL_SMS_FROM_NUMBER": SENDER,
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

    def test_verified_recipient_is_used_by_delivery_guard(self):
        with self.factory() as db:
            self.start(db)
            code = self.code()
            confirm_owner_verification(db, "shop-a", PHONE, code)
            self.assertEqual(
                approved_owner_recipient("shop-a", PHONE, db=db, shop_id="shop-a"),
                PHONE,
            )
            with self.assertRaises(HTTPException):
                owner_phone_for_test_shop(
                    "shop-b",
                    type("Settings", (), {
                        "notifications_enabled": True,
                        "owner_phone": PHONE,
                        "shop_id": "shop-b",
                    })(),
                    db=db, shop_id="shop-b",
                )

    def test_authenticated_owner_verification_routes(self):
        app = FastAPI()
        app.include_router(contact_route.router, prefix="/api")
        user = User(id="owner-a", role="owner", shop_id="shop-a",
                    shop_slug="shop-a", email="owner@example.test",
                    is_active=True)
        app.dependency_overrides[get_current_user] = lambda: user

        def db_override():
            with self.factory() as db:
                yield db

        app.dependency_overrides[get_db] = db_override
        with TestClient(app) as client:
            base = "/api/shops/shop-a/voicemail-owner/verification"
            denied = client.post(base + "/start", json={
                "phone_number": PHONE, "consent_to_verification_sms": False,
            })
            self.assertEqual(denied.status_code, 409)
            started = client.post(base + "/start", json={
                "phone_number": PHONE, "consent_to_verification_sms": True,
            })
            self.assertEqual(started.status_code, 200, started.text)
            self.assertFalse(started.json()["notifications_enabled"])
            confirmed = client.post(base + "/confirm", json={
                "phone_number": PHONE, "code": self.code(),
            })
            self.assertEqual(confirmed.status_code, 200, confirmed.text)
            self.assertTrue(confirmed.json()["owner_number_verified"])
            # An authenticated owner of another shop cannot use this URL.
            other = client.post("/api/shops/shop-b/voicemail-owner/verification/confirm",
                                json={"phone_number": PHONE, "code": "000000"})
            self.assertEqual(other.status_code, 403)

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


    def test_opt_out_revokes_proof_and_disables_alerts_without_routing(self):
        with self.factory() as db:
            self.start(db)
            confirm_owner_verification(db, "shop-a", PHONE, self.code())
            db.add(DayTelloVoicemailShopSettings(
                shop_id="shop-a", location_id="loc-test",
                receiving_number="+12025550131", owner_phone=PHONE,
                notifications_enabled=True,
            ))
            db.commit()
            result = disable_owner_voicemail_notifications(db, "shop-a")
            self.assertFalse(result["notifications_enabled"])
            self.assertFalse(result["call_routing_changed"])
            settings = db.get(DayTelloVoicemailShopSettings, "shop-a")
            self.assertEqual(settings.receiving_number, "+12025550131")
            self.assertEqual(settings.owner_phone, PHONE)
            self.assertFalse(settings.notifications_enabled)
            with self.assertRaises(HTTPException):
                verified_owner_recipient(db, "shop-a", PHONE)
            self.assertFalse(db.get(
                DayTelloVoicemailOwnerVerification, "shop-a"
            ).challenge_digest)
            # Repeating opt-out is safe and does not send SMS.
            self.assertFalse(disable_owner_voicemail_notifications(
                db, "shop-a")["notifications_enabled"])
            self.assertEqual(len(self.sent), 1)

    def test_opt_out_route_rejects_other_shop_and_revokes_otp(self):
        app = FastAPI()
        app.include_router(contact_route.router, prefix="/api")
        user = User(id="owner-a", role="owner", shop_id="shop-a",
                    shop_slug="shop-a", email="owner@example.test",
                    is_active=True)
        app.dependency_overrides[get_current_user] = lambda: user

        def db_override():
            with self.factory() as db:
                yield db

        app.dependency_overrides[get_db] = db_override
        with self.factory() as db:
            self.start(db)
            code = self.code()
        with TestClient(app) as client:
            wrong_shop = client.post(
                "/api/shops/shop-b/voicemail-owner/notifications/disable")
            self.assertEqual(wrong_shop.status_code, 403)
            response = client.post(
                "/api/shops/shop-a/voicemail-owner/notifications/disable")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertFalse(response.json()["notifications_enabled"])
            replay = client.post(
                "/api/shops/shop-a/voicemail-owner/verification/confirm",
                json={"phone_number": PHONE, "code": code})
            self.assertEqual(replay.status_code, 409)


if __name__ == "__main__":
    unittest.main()
