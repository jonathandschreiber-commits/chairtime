"""Regression: a disabled, pre-owned Twilio relay can save an SMS owner while HighLevel-only."""
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
from app.routes import voicemail_contact_number as route
from app.voicemail_models import DayTelloVoicemailShopSettings
from app.voice_relay_models import DayTelloVoiceRelayAssignment


class Shop3PendingOwnerSave(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            db.add_all([
                Shop(id="test-s3", slug="test-shop-3", name="Test Shop 3",
                     ai_voice_enabled=True, highlevel_location_id="loc-test",
                     highlevel_agent_id="agent-test", highlevel_phone_number="+12403875085"),
                DayTelloVoicemailShopSettings(
                    shop_id="test-s3", location_id="loc-test",
                    receiving_number="+15077135447", notifications_enabled=False),
                DayTelloVoiceRelayAssignment(
                    shop_id="test-s3", relay_number="+15077135447", enabled=False),
            ])
            db.commit()
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "DAYTELLO_VOICE_RELAY_TEST_ONLY": "true",
            "DAYTELLO_VOICEMAIL_PROVIDER": "highlevel",
            "HIGHLEVEL_LOCATION_ID": "loc-test",
        })
        self.env.start()
        self.owner = User(id="owner-s3", role="owner", shop_slug="test-shop-3",
                          shop_id="test-s3", is_active=True, email="owner@test.example")
        app = FastAPI()
        app.include_router(route.router, prefix="/api")
        def get_session():
            with self.factory() as db:
                yield db
        app.dependency_overrides[get_db] = get_session
        app.dependency_overrides[get_current_user] = lambda: self.owner
        self.client = TestClient(app)
        self.url = "/api/shops/test-shop-3/call-voicemail-number"

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.engine.dispose()

    def test_verified_number_saved_without_touching_highlevel_or_enabling_calls(self):
        with patch.object(route, "approved_owner_recipient", return_value="+12405619680"), \
             patch.object(route, "daytello_save_staff_transfer") as transfer:
            response = self.client.put(self.url, json={"phone_number": "+12405619680"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["pending_test_authorization"])
        self.assertFalse(response.json()["notifications_enabled"])
        self.assertFalse(response.json()["forwarding_verified"])
        self.assertFalse(response.json()["ready"])
        transfer.assert_not_called()
        with self.factory() as db:
            settings = db.get(DayTelloVoicemailShopSettings, "test-s3")
            relay = db.get(DayTelloVoiceRelayAssignment, "test-s3")
            self.assertEqual(settings.owner_phone, "+12405619680")
            self.assertFalse(settings.notifications_enabled)
            self.assertEqual(settings.receiving_number, "+15077135447")
            self.assertFalse(relay.enabled)

    def test_direct_call_only_activation_does_not_enable_sms_or_touch_highlevel(self):
        with self.factory() as db:
            db.get(DayTelloVoicemailShopSettings, "test-s3").owner_phone = "+12405619680"
            db.commit()
        with patch.dict(os.environ, {"DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED": "true",
                                     "DAYTELLO_VOICE_RELAY_ALLOW_TEST_CALLS": "true"}), \
             patch.object(route, "approved_owner_recipient", return_value="+12405619680"), \
             patch.object(route, "VoiceRelayNumberProvider") as provider, \
             patch.object(route, "daytello_save_staff_transfer") as transfer:
            provider.return_value.find_existing.return_value = {
                "number": "+15077135447", "route_verified": True}
            response = self.client.post(
                "/api/shops/test-shop-3/voice-relay/call-only-test",
                json={"confirm_test_calls": True})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["test_calls_enabled"])
        self.assertFalse(response.json()["sms_notifications_enabled"])
        self.assertFalse(response.json()["highlevel_routing_changed"])
        transfer.assert_not_called()
        with self.factory() as db:
            self.assertTrue(db.get(DayTelloVoiceRelayAssignment, "test-s3").enabled)
            self.assertFalse(db.get(DayTelloVoicemailShopSettings, "test-s3").notifications_enabled)
        with patch.dict(os.environ, {"DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED": "true"}):
            stopped = self.client.post(
                "/api/shops/test-shop-3/voice-relay/call-only-test",
                json={"confirm_test_calls": False})
        self.assertEqual(stopped.status_code, 200, stopped.text)
        self.assertFalse(stopped.json()["test_calls_enabled"])

    def test_direct_call_requires_independent_test_authorization(self):
        with self.factory() as db:
            db.get(DayTelloVoicemailShopSettings, "test-s3").owner_phone = "+12405619680"
            db.commit()
        with patch.dict(os.environ, {"DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED": "true",
                                     "DAYTELLO_VOICE_RELAY_ALLOW_TEST_CALLS": "false"}):
            response = self.client.post(
                "/api/shops/test-shop-3/voice-relay/call-only-test",
                json={"confirm_test_calls": True})
        self.assertEqual(response.status_code, 409)
        with self.factory() as db:
            self.assertFalse(db.get(DayTelloVoiceRelayAssignment, "test-s3").enabled)

    def test_active_relay_still_rejected(self):
        with self.factory() as db:
            db.get(DayTelloVoiceRelayAssignment, "test-s3").enabled = True
            db.commit()
        with patch.object(route, "approved_owner_recipient", return_value="+12405619680"):
            response = self.client.put(self.url, json={"phone_number": "+12405619680"})
        self.assertEqual(response.status_code, 409)
        with self.factory() as db:
            self.assertIsNone(db.get(DayTelloVoicemailShopSettings, "test-s3").owner_phone)


if __name__ == "__main__":
    unittest.main()
