"""Sandbox Shop #3 trial gate tests; never creates payments or provider calls."""
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
from app.routes.auth import get_current_user, router


class Shop3SandboxTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://",
            connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            db.add_all([
                Shop(id="shop3", slug="test-shop-3", name="Test Shop #3"),
                Shop(id="other", slug="other-shop", name="Other Shop"),
            ])
            db.commit()
        self.user = User(
            id="u3", shop_id="shop3", shop_slug="test-shop-3",
            role="owner", is_active=True, email="shop3@example.test",
        )
        app = FastAPI()
        app.include_router(router, prefix="/api/auth")
        def db_override():
            with self.factory() as db:
                yield db
        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)
        self.endpoint = "/api/auth/test-shop3-activate-ai"
        self.env = patch.dict(os.environ, {
            "DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED": "true",
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "DAYTELLO_VOICEMAIL_PROVIDER": "highlevel",
            "DAYTELLO_VOICE_RELAY_PURCHASE_ENABLED": "false",
        })
        self.env.start()

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.engine.dispose()

    def test_sandbox_owner_can_activate_non_billable_ai_setup(self):
        first = self.client.post(self.endpoint)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertTrue(first.json()["sandbox_only"])
        self.assertFalse(first.json()["billing_active"])
        self.assertFalse(first.json()["ready_for_customer_calls"])
        second = self.client.post(self.endpoint)
        self.assertEqual(second.status_code, 200, second.text)
        with self.factory() as db:
            shop = db.get(Shop, "shop3")
            self.assertTrue(shop.ai_voice_enabled)
            self.assertEqual(shop.subscription_status, "sandbox_test")
            self.assertIsNone(shop.stripe_subscription_id)
            self.assertIsNone(shop.stripe_customer_id)

    def test_route_missing_without_explicit_sandbox_permission(self):
        with patch.dict(os.environ, {"DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED": "false"}):
            response = self.client.post(self.endpoint)
        self.assertEqual(response.status_code, 404)
        with self.factory() as db:
            self.assertFalse(db.get(Shop, "shop3").ai_voice_enabled)

    def test_other_shop_and_staff_cannot_enable_trial(self):
        self.user.shop_id = "other"
        self.user.shop_slug = "other-shop"
        self.assertEqual(self.client.post(self.endpoint).status_code, 403)
        self.user.shop_id = "shop3"
        self.user.shop_slug = "test-shop-3"
        self.user.role = "staff"
        self.assertEqual(self.client.post(self.endpoint).status_code, 403)
        with self.factory() as db:
            self.assertFalse(db.get(Shop, "shop3").ai_voice_enabled)

    def test_never_bypasses_existing_stripe_customer(self):
        with self.factory() as db:
            shop = db.get(Shop, "shop3")
            shop.stripe_customer_id = "cus_existing"
            db.commit()
        self.assertEqual(self.client.post(self.endpoint).status_code, 409)
        with self.factory() as db:
            self.assertFalse(db.get(Shop, "shop3").ai_voice_enabled)

    def test_no_activation_if_purchase_guard_enabled(self):
        with patch.dict(os.environ, {"DAYTELLO_VOICE_RELAY_PURCHASE_ENABLED": "true"}):
            self.assertEqual(self.client.post(self.endpoint).status_code, 404)


if __name__ == "__main__":
    unittest.main()
