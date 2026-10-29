"""Offline owner-bound recovery of an existing AI agent, no HighLevel writes."""
import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Shop, User
from app.routes.auth import get_current_user
from app.routes import test_existing_agent_link as route
from app.voicemail_models import DayTelloVoicemailShopSettings


AGENT_ID = "bob-existing-agent"
PHONE = "+12406242072"


class ExistingAgentRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            db.add_all([
                Shop(id="bob", slug="bobs-shop", name="Bob's Shop",
                     ai_voice_enabled=True, highlevel_location_id="test-location"),
                Shop(id="stan", slug="stans-shop", name="Stan's Shop",
                     ai_voice_enabled=True, highlevel_location_id="test-location"),
                DayTelloVoicemailShopSettings(
                    shop_id="bob", location_id="test-location",
                    receiving_number="+12406935034",
                    owner_phone="+12405619680", notifications_enabled=False,
                ),
            ])
            db.commit()
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "RAILWAY_ENVIRONMENT_NAME": "daytello-voicemail-test",
            "HIGHLEVEL_LOCATION_ID": "test-location",
        })
        self.env.start()
        self.user = User(id="owner-bob", shop_id="bob", shop_slug="bobs-shop", role="owner")
        app = FastAPI()
        app.include_router(route.router, prefix="/api/ai-setup")

        def db_override():
            with self.factory() as db:
                yield db

        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)
        self.uri = "/api/ai-setup/test-link-existing-agent"
        self.responses = patch.multiple(
            route,
            highlevel_request=lambda **kw: object(),
            response_json=lambda x: {
                "agents": [{
                    "id": AGENT_ID, "agentName": "ChairTime AI - bobs-shop",
                    "locationId": "test-location",
                }]
            },
            get_agent_detail=lambda agent_id, location_id: {
                "id": AGENT_ID, "agentName": "ChairTime AI - bobs-shop",
                "locationId": "test-location",
            },
            get_location_phone_numbers=lambda location_id: ({}, [{
                "phoneNumber": PHONE, "capabilities": {"voice": True},
                "inboundCallService": {"type": "voice_ai", "value": AGENT_ID},
            }]),
        )
        self.mocks = self.responses.start()

    def tearDown(self):
        self.responses.stop()
        self.client.close()
        self.env.stop()
        self.engine.dispose()

    def test_links_existing_agent_without_sending_or_editing_highlevel(self):
        response = self.client.post(self.uri)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["linked"])
        self.assertFalse(response.json()["sms_enabled"])
        self.assertFalse(response.json()["forwarding_verified"])
        with self.factory() as db:
            bob = db.get(Shop, "bob")
            self.assertEqual(bob.highlevel_agent_id, AGENT_ID)
            self.assertEqual(bob.highlevel_phone_number, PHONE)
            prefs = db.get(DayTelloVoicemailShopSettings, "bob")
            self.assertFalse(prefs.notifications_enabled)
            self.assertEqual(prefs.owner_phone, "+12405619680")
            self.assertEqual(prefs.receiving_number, "+12406935034")
            self.assertEqual(db.query(Shop).count(), 2)
        self.assertEqual(self.client.post(self.uri).status_code, 409)

    def test_disabled_outside_isolated_railway(self):
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = "production"
        self.assertEqual(self.client.post(self.uri).status_code, 404)
        with self.factory() as db:
            self.assertIsNone(db.get(Shop, "bob").highlevel_agent_id)

    def test_only_bob_owner_can_claim(self):
        self.user = User(id="owner-stan", shop_id="stan", shop_slug="stans-shop", role="owner")
        self.assertEqual(self.client.post(self.uri).status_code, 403)

    def test_conflicting_agent_cannot_be_claimed(self):
        with self.factory() as db:
            db.get(Shop, "stan").highlevel_agent_id = AGENT_ID
            db.commit()
        self.assertEqual(self.client.post(self.uri).status_code, 409)
        with self.factory() as db:
            self.assertIsNone(db.get(Shop, "bob").highlevel_agent_id)

    def test_routing_must_be_verified_not_guessed(self):
        with patch.object(route, "get_location_phone_numbers", return_value=({}, [])):
            response = self.client.post(self.uri)
        self.assertEqual(response.status_code, 409)
        with self.factory() as db:
            self.assertIsNone(db.get(Shop, "bob").highlevel_agent_id)

    def test_voice_agent_scope_denial_is_actionable_and_does_not_link(self):
        with patch.object(route, "highlevel_request", side_effect=HTTPException(
            502, {"message": "HighLevel rejected the Voice AI request.",
                  "highlevel_status": 401, "highlevel_error": "secret-diagnostic"}
        )):
            response = self.client.post(self.uri)
        self.assertEqual(response.status_code, 502, response.text)
        self.assertIn("voice-ai-agents.readonly", response.json()["detail"])
        self.assertNotIn("secret-diagnostic", response.text)
        with self.factory() as db:
            self.assertIsNone(db.get(Shop, "bob").highlevel_agent_id)

    def test_phone_number_scope_denial_is_actionable_and_does_not_link(self):
        with patch.object(route, "get_location_phone_numbers", side_effect=HTTPException(
            502, {"highlevel_status": 403, "highlevel_error": "internal provider details"}
        )):
            response = self.client.post(self.uri)
        self.assertEqual(response.status_code, 502, response.text)
        self.assertIn("phonenumbers.read", response.json()["detail"])
        self.assertNotIn("internal provider details", response.text)
        with self.factory() as db:
            self.assertIsNone(db.get(Shop, "bob").highlevel_agent_id)

    def test_wrong_location_is_rejected(self):
        os.environ["HIGHLEVEL_LOCATION_ID"] = "another-location"
        self.assertEqual(self.client.post(self.uri).status_code, 409)

    def test_notifications_must_remain_disabled_before_link(self):
        with self.factory() as db:
            db.get(DayTelloVoicemailShopSettings, "bob").notifications_enabled = True
            db.commit()
        self.assertEqual(self.client.post(self.uri).status_code, 409)


if __name__ == "__main__":
    unittest.main()
