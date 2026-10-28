"""Offline fail-closed tests for controlled voicemail number provisioning."""
import os
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.models import Shop, User
from app.routes.auth import get_current_user
from app.routes import voicemail_shop_provisioning as provisioning
from app.voicemail_models import DayTelloVoicemailShopSettings


class ProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            db.add_all([
                Shop(id="a", slug="shop-a", name="Shop A", ai_voice_enabled=True,
                     highlevel_location_id="test-location"),
                Shop(id="b", slug="shop-b", name="Shop B", ai_voice_enabled=True,
                     highlevel_location_id="test-location"),
            ])
            db.commit()
        self.user = User(id="admin", email="admin@example.test", role="owner",
                         shop_slug="shop-a", shop_id="a", is_active=True)
        self.env = patch.dict(os.environ, {
            "PLATFORM_ADMIN_EMAILS": "admin@example.test",
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "HIGHLEVEL_LOCATION_ID": "test-location",
            "DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP": "",
        })
        self.env.start()
        self.provider = patch.object(
            provisioning, "get_location_phone_numbers",
            return_value=({}, [{"phoneNumber": "+12025550123"}]),
        )
        self.provider.start()
        app = FastAPI()
        app.include_router(provisioning.router, prefix="/api")
        def override():
            with self.factory() as db:
                yield db
        app.dependency_overrides[get_db] = override
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.provider.stop()
        self.env.stop()
        self.engine.dispose()

    def provision(self, slug="shop-a", number="+12025550123"):
        return self.client.post(
            f"/api/daytello/admin/voicemail-shops/{slug}/provision",
            json={"receiving_number": number},
        )

    def test_admin_provisions_verified_number_once(self):
        self.assertEqual(self.provision().status_code, 200)
        self.assertEqual(self.provision().status_code, 200)
        with self.factory() as db:
            self.assertEqual(db.query(DayTelloVoicemailShopSettings).count(), 1)
            row = db.get(DayTelloVoicemailShopSettings, "a")
            self.assertFalse(row.notifications_enabled)
            self.assertIsNone(row.owner_phone)

    def test_other_shop_cannot_take_same_number(self):
        self.assertEqual(self.provision().status_code, 200)
        self.assertEqual(self.provision("shop-b").status_code, 409)

    def test_normal_shop_owner_is_not_platform_admin(self):
        self.user.email = "owner@example.test"
        self.assertEqual(self.provision().status_code, 403)

    def test_disabled_test_mode_fails_closed(self):
        os.environ["DAYTELLO_VOICEMAIL_TEST_ONLY"] = "false"
        self.assertEqual(self.provision().status_code, 404)

    def test_unverified_number_cannot_be_provisioned(self):
        self.assertEqual(self.provision(number="+12025550125").status_code, 409)
        with self.factory() as db:
            self.assertEqual(db.query(DayTelloVoicemailShopSettings).count(), 0)

    def test_wrong_shop_location_is_rejected(self):
        with self.factory() as db:
            shop = db.get(Shop, "a")
            shop.highlevel_location_id = "other-location"
            db.commit()
        self.assertEqual(self.provision().status_code, 409)

    def test_legacy_other_shop_route_is_respected(self):
        os.environ["DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP"] = (
            '{"+12025550123":"shop-b"}'
        )
        self.assertEqual(self.provision().status_code, 409)


if __name__ == "__main__":
    unittest.main()
