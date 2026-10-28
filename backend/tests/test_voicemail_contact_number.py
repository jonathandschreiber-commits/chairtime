"""Offline unified owner number API tests; no real calls or texts."""
import os
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Shop, User
from app.routes.auth import get_current_user
from app.routes import voicemail_contact_number as route
from app.voicemail_models import DayTelloVoicemailShopSettings


class UnifiedPhoneTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            db.add_all([
                Shop(id="s1", slug="shop-a", name="Shop A", ai_voice_enabled=True,
                     highlevel_location_id="loc-test"),
                Shop(id="s2", slug="shop-b", name="Shop B", ai_voice_enabled=True,
                     highlevel_location_id="loc-test"),
                DayTelloVoicemailShopSettings(
                    shop_id="s1", location_id="loc-test",
                    receiving_number="+12025550123",
                    notifications_enabled=False,
                ),
            ])
            db.commit()
        self.user = User(
            id="u1", role="owner", shop_slug="shop-a", shop_id="s1",
            is_active=True, email="owner@example.test",
        )
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true",
            "DAYTELLO_VOICEMAIL_TEST_RECIPIENT": "+12025550199",
            "DAYTELLO_VOICEMAIL_LINK_KEY": Fernet.generate_key().decode(),
            "DAYTELLO_VOICEMAIL_TEST_PUBLIC_ORIGIN": "https://daytello-voicemail-test.example.org",
            "HIGHLEVEL_SMS_FROM_NUMBER": "+12025550124",
            "HIGHLEVEL_LOCATION_ID": "loc-test",
        })
        self.env.start()
        app = FastAPI()
        app.include_router(route.router, prefix="/api")
        def db_override():
            with self.factory() as db:
                yield db
        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)
        self.url = "/api/shops/shop-a/call-voicemail-number"

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.engine.dispose()

    def test_one_number_saved_after_verified_transfer(self):
        with patch.object(route, "daytello_save_staff_transfer", return_value={
            "enabled": True, "phone_number": "+12025550199",
        }) as provider:
            response = self.client.put(self.url, json={"phone_number": "+12025550199"})
        self.assertEqual(response.status_code, 200, response.text)
        provider.assert_called_once()
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "s1")
            self.assertEqual(prefs.owner_phone, "+12025550199")
            self.assertTrue(prefs.notifications_enabled)

    def test_failed_transfer_leaves_notification_unchanged(self):
        with patch.object(
            route, "daytello_save_staff_transfer",
            side_effect=HTTPException(502, "Provider unavailable"),
        ):
            response = self.client.put(self.url, json={"phone_number": "+12025550199"})
        self.assertEqual(response.status_code, 502)
        with self.factory() as db:
            self.assertIsNone(db.get(DayTelloVoicemailShopSettings, "s1").owner_phone)

    def test_another_shop_denied(self):
        response = self.client.get("/api/shops/shop-b/call-voicemail-number")
        self.assertEqual(response.status_code, 403)

    def test_invalid_and_unapproved_numbers_rejected(self):
        self.assertEqual(
            self.client.put(self.url, json={"phone_number": "1234"}).status_code, 422
        )
        self.assertEqual(
            self.client.put(self.url, json={"phone_number": "+12025550198"}).status_code, 503
        )

    def test_no_provisioning_fails_closed(self):
        self.user.shop_slug = "shop-b"
        self.user.shop_id = "s2"
        self.assertEqual(self.client.put(
            "/api/shops/shop-b/call-voicemail-number",
            json={"phone_number": "+12025550199"},
        ).status_code, 409)


if __name__ == "__main__":
    unittest.main()
