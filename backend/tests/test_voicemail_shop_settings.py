"""Offline owner settings authorization tests; no external calls."""
import unittest
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Shop, User
from app.routes.auth import get_current_user
from app.routes.voicemail_shop_settings import router
from app.voicemail_models import DayTelloVoicemailShopSettings
from app.voicemail_owner_verification import DayTelloVoicemailOwnerVerification


class ShopVoicemailSettingsTests(unittest.TestCase):
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
                Shop(id="shop-c", slug="shop-c", name="Shop C", ai_voice_enabled=True),
                DayTelloVoicemailShopSettings(
                    shop_id="shop-a", location_id="location-1",
                    receiving_number="+12025550100", notifications_enabled=False,
                ),
                DayTelloVoicemailShopSettings(
                    shop_id="shop-b", location_id="location-1",
                    receiving_number="+12025550101", notifications_enabled=False,
                ),
            ])
            db.commit()
        self.user = User(
            id="owner-a", email="owner-a@example.test", shop_id="shop-a",
            shop_slug="shop-a", role="owner", is_active=True,
        )
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api")
        def db_override():
            with self.factory() as db:
                yield db
        self.app.dependency_overrides[get_db] = db_override
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def test_owner_reads_only_their_settings(self):
        response = self.client.get("/api/shops/shop-a/voicemail-settings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["receiving_number"], "+12025550100")
        self.assertEqual(
            self.client.get("/api/shops/shop-b/voicemail-settings").status_code,
            403,
        )

    def test_owner_can_save_phone_without_activating_notifications(self):
        response = self.client.patch(
            "/api/shops/shop-a/voicemail-settings",
            json={"notifications_enabled": False, "owner_phone": "+12025550199"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["notifications_enabled"])
        with self.factory() as db:
            a = db.get(DayTelloVoicemailShopSettings, "shop-a")
            b = db.get(DayTelloVoicemailShopSettings, "shop-b")
            self.assertEqual(a.owner_phone, "+12025550199")
            self.assertFalse(a.notifications_enabled)
            self.assertIsNone(b.owner_phone)

    def test_unverified_preference_cannot_activate_notifications(self):
        response = self.client.patch(
            "/api/shops/shop-a/voicemail-settings",
            json={"notifications_enabled": True, "owner_phone": "+12025550199"},
        )
        self.assertEqual(response.status_code, 409, response.text)
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "shop-a")
            self.assertIsNone(prefs.owner_phone)
            self.assertFalse(prefs.notifications_enabled)

    def test_active_recipient_cannot_be_swapped_without_reverification(self):
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "shop-a")
            prefs.owner_phone = "+12025550198"
            prefs.notifications_enabled = True
            db.commit()
        response = self.client.patch(
            "/api/shops/shop-a/voicemail-settings",
            json={"notifications_enabled": True, "owner_phone": "+12025550199"},
        )
        self.assertEqual(response.status_code, 409, response.text)
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "shop-a")
            self.assertEqual(prefs.owner_phone, "+12025550198")
            self.assertTrue(prefs.notifications_enabled)

    def test_owner_can_disable_existing_notifications(self):
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "shop-a")
            prefs.owner_phone = "+12025550198"
            prefs.notifications_enabled = True
            db.add(DayTelloVoicemailOwnerVerification(
                shop_id="shop-a", phone="+12025550198",
                verified_at=datetime.utcnow(), challenge_salt="stale-salt",
                challenge_digest="stale-digest", expires_at=datetime.utcnow(),
            ))
            db.commit()
        response = self.client.patch(
            "/api/shops/shop-a/voicemail-settings",
            json={"notifications_enabled": False, "owner_phone": "+12025550198"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["notifications_enabled"])
        with self.factory() as db:
            proof = db.get(DayTelloVoicemailOwnerVerification, "shop-a")
            self.assertIsNone(proof.verified_at)
            self.assertIsNone(proof.challenge_digest)
            self.assertIsNone(proof.challenge_salt)
            self.assertIsNone(proof.expires_at)

    def test_disabled_phone_change_revokes_only_own_verification(self):
        with self.factory() as db:
            for shop_id in ("shop-a", "shop-b"):
                db.add(DayTelloVoicemailOwnerVerification(
                    shop_id=shop_id, phone="+12025550198",
                    verified_at=datetime.utcnow(),
                ))
            db.commit()
        response = self.client.patch(
            "/api/shops/shop-a/voicemail-settings",
            json={"notifications_enabled": False, "owner_phone": "+12025550199"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        with self.factory() as db:
            a = db.get(DayTelloVoicemailOwnerVerification, "shop-a")
            b = db.get(DayTelloVoicemailOwnerVerification, "shop-b")
            self.assertIsNone(a.verified_at)
            self.assertIsNotNone(b.verified_at)
            self.assertEqual(
                db.get(DayTelloVoicemailShopSettings, "shop-a").owner_phone,
                "+12025550199",
            )

    def test_owner_cannot_change_routing_or_another_shop(self):
        response = self.client.patch(
            "/api/shops/shop-a/voicemail-settings",
            json={
                "notifications_enabled": True, "owner_phone": "+12025550199",
                "receiving_number": "+12025550177",
            },
        )
        self.assertEqual(response.status_code, 422)
        response = self.client.patch(
            "/api/shops/shop-b/voicemail-settings",
            json={"notifications_enabled": True, "owner_phone": "+12025550199"},
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_change_owner_settings(self):
        self.user.role = "staff"
        response = self.client.patch(
            "/api/shops/shop-a/voicemail-settings",
            json={"notifications_enabled": True, "owner_phone": "+12025550199"},
        )
        self.assertEqual(response.status_code, 403)

    def test_phone_required_and_valid(self):
        self.assertEqual(self.client.patch(
            "/api/shops/shop-a/voicemail-settings",
            json={"notifications_enabled": True, "owner_phone": None},
        ).status_code, 422)
        self.assertEqual(self.client.patch(
            "/api/shops/shop-a/voicemail-settings",
            json={"notifications_enabled": True, "owner_phone": "1234"},
        ).status_code, 422)

    def test_not_provisioned_fails_closed(self):
        self.user.shop_id = "shop-c"
        self.user.shop_slug = "shop-c"
        response = self.client.patch(
            "/api/shops/shop-c/voicemail-settings",
            json={"notifications_enabled": True, "owner_phone": "+12025550199"},
        )
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
