"""Offline, isolated test owner claim: never touches HighLevel or real SMS."""
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
from app.routes import auth
from app.voicemail_models import (
    DayTelloVoicemailEvent,
    DayTelloVoicemailShopSettings,
)


class TestOwnerClaimTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            db.add(Shop(
                id="s-bob", slug="bobs-shop", name="Bob's Shop",
                ai_voice_enabled=True, highlevel_location_id="loc-bob",
            ))
            db.add(Shop(
                id="s-stan", slug="stans-shop", name="Stan's Shop",
                ai_voice_enabled=True, highlevel_location_id="loc-bob",
            ))
            db.add(DayTelloVoicemailShopSettings(
                shop_id="s-bob", location_id="loc-bob",
                receiving_number="+12406935034",
                owner_phone=None, notifications_enabled=False,
            ))
            db.add(DayTelloVoicemailEvent(
                location_id="loc-bob", message_id="existing-recording",
                shop_id="s-bob", receiving_number="+12406935034",
                notification_status="disabled",
            ))
            db.commit()
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "DAYTELLO_TEST_OWNER_INVITE_CODE": "abcdefghijklmnopqrstuvwxyz0123456789A",
            "HIGHLEVEL_LOCATION_ID": "loc-bob",
            "JWT_SECRET": "test-only-strong-jwt-secret-for-offline-tests",
        })
        self.env.start()
        app = FastAPI()
        app.include_router(auth.router, prefix="/api/auth")

        def db_override():
            with self.factory() as db:
                yield db

        app.dependency_overrides[get_db] = db_override
        self.client = TestClient(app)
        self.url = "/api/auth/test-claim-existing-shop"
        self.payload = {
            "owner_name": "Bob Test Owner",
            "email": "bob-test-owner@example.test",
            "password": "test-password-1234",
            "invite_code": os.environ["DAYTELLO_TEST_OWNER_INVITE_CODE"],
        }

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.engine.dispose()

    def test_one_use_claim_preserves_existing_shop_and_voicemail_history(self):
        response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user"]["shop_slug"], "bobs-shop")
        self.assertEqual(response.json()["user"]["role"], "owner")
        self.assertFalse(response.json()["user"]["platform_admin"])
        token = response.json()["access_token"]
        me = self.client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["shop_id"], "s-bob")
        with self.factory() as db:
            self.assertEqual(db.query(Shop).count(), 2)
            self.assertEqual(db.query(User).count(), 1)
            self.assertEqual(db.query(User).first().shop_id, "s-bob")
            preferences = db.get(DayTelloVoicemailShopSettings, "s-bob")
            self.assertEqual(preferences.receiving_number, "+12406935034")
            self.assertIsNone(preferences.owner_phone)
            self.assertFalse(preferences.notifications_enabled)
            self.assertIsNotNone(
                db.get(DayTelloVoicemailEvent, ("loc-bob", "existing-recording"))
            )
        retry = self.client.post(self.url, json={
            **self.payload, "email": "second@example.test",
        })
        self.assertEqual(retry.status_code, 409)
        with self.factory() as db:
            self.assertEqual(db.query(User).count(), 1)

    def test_production_never_exposes_claim(self):
        os.environ["DAYTELLO_VOICEMAIL_TEST_ONLY"] = "false"
        response = self.client.post(self.url, json=self.payload)
        self.assertEqual(response.status_code, 404)
        with self.factory() as db:
            self.assertEqual(db.query(User).count(), 0)

    def test_invitation_unconfigured_fails_closed(self):
        os.environ.pop("DAYTELLO_TEST_OWNER_INVITE_CODE")
        self.assertEqual(self.client.post(self.url, json=self.payload).status_code, 404)

    def test_invalid_invitation_does_not_create_owner(self):
        result = self.client.post(
            self.url, json={**self.payload, "invite_code": "wrong"}
        )
        self.assertEqual(result.status_code, 403)
        with self.factory() as db:
            self.assertEqual(db.query(User).count(), 0)

    def test_missing_jwt_secret_does_not_create_owner(self):
        os.environ.pop("JWT_SECRET")
        self.assertEqual(self.client.post(self.url, json=self.payload).status_code, 503)
        with self.factory() as db:
            self.assertEqual(db.query(User).count(), 0)

    def test_unverified_location_fails_closed(self):
        os.environ["HIGHLEVEL_LOCATION_ID"] = "another-location"
        self.assertEqual(self.client.post(self.url, json=self.payload).status_code, 409)
        with self.factory() as db:
            self.assertEqual(db.query(User).count(), 0)

    def test_unverified_shop_fails_closed(self):
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "s-bob")
            db.delete(prefs)
            db.commit()
        self.assertEqual(self.client.post(self.url, json=self.payload).status_code, 409)
        with self.factory() as db:
            self.assertEqual(db.query(User).count(), 0)

    def test_existing_owner_not_overwritten(self):
        with self.factory() as db:
            db.add(User(
                id="u-bob", shop_id="s-bob", shop_slug="bobs-shop",
                name="Previous Owner", email="previous@example.test",
                role="owner", password_hash=auth.hash_password("previous-password-123"),
                is_active=True,
            ))
            db.commit()
        self.assertEqual(self.client.post(self.url, json=self.payload).status_code, 409)
        with self.factory() as db:
            self.assertEqual(db.query(User).count(), 1)

    def test_bad_name_or_password_is_rejected(self):
        bad = {**self.payload, "owner_name": "    "}
        self.assertEqual(self.client.post(self.url, json=bad).status_code, 422)
        bad = {**self.payload, "password": "short"}
        self.assertEqual(self.client.post(self.url, json=bad).status_code, 422)


if __name__ == "__main__":
    unittest.main()
