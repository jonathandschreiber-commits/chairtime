"""Offline owner settings authorization tests; no external calls."""
import unittest
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

    def test_owner_can_set_notification_preference(self):
        response = self.client.patch(
            "/api/shops/shop-a/voicemail-settings",
            json={"notifications_enabled": True, "owner_phone": "+12025550199"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["notifications_enabled"])
        with self.factory() as db:
            a = db.get(DayTelloVoicemailShopSettings, "shop-a")
            b = db.get(DayTelloVoicemailShopSettings, "shop-b")
            self.assertEqual(a.owner_phone, "+12025550199")
            self.assertIsNone(b.owner_phone)

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
