"""New-shop AI-number -> pre-owned relay -> missed call -> SMS -> audio (offline).

All provider I/O is mocked. No numbers are purchased and no live routes change.
"""
import base64
import hashlib
import hmac
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit

import httpx
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Shop, User
from app.routes.auth import get_current_user
from app.routes import ai_setup, voicemail_contact_number, voice_relay
from app import voice_relay_delivery
from app.voice_relay_models import DayTelloVoiceRelayAssignment
from app.voicemail_models import DayTelloVoicemailShopSettings

ACCOUNT = "AC" + "a" * 32
RELAY = "+12405550123"
AI_NUMBER = "+12405550124"
OWNER = "+12405550125"
CALL = "CA" + "b" * 32
RECORDING = "RE" + "c" * 32


class NewShopIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.factory() as db:
            db.add_all([
                Shop(id="new-id", slug="new-shop", name="New Shop",
                     ai_voice_enabled=True, highlevel_location_id="loc-test",
                     highlevel_agent_id="agent-new"),
                Shop(id="stan-id", slug="stans-shop", name="Stan's Shop",
                     ai_voice_enabled=True, highlevel_location_id="loc-test",
                     highlevel_agent_id="agent-stan",
                     highlevel_phone_number="+12405550131"),
                DayTelloVoicemailShopSettings(
                    shop_id="stan-id", location_id="loc-test",
                    receiving_number="+12405550132",
                    owner_phone="+12405550133", notifications_enabled=True,
                ),
            ])
            db.commit()
        self.owner = User(
            id="owner-new", role="owner", shop_slug="new-shop",
            shop_id="new-id", is_active=True, email="new@example.test",
        )
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "DAYTELLO_VOICE_RELAY_TEST_ONLY": "true",
            "DAYTELLO_VOICE_RELAY_ALLOW_TEST_CALLS": "true",
            "DAYTELLO_VOICE_RELAY_AUTH_TOKEN": "offline-relay-secret",
            "DAYTELLO_VOICE_RELAY_ACCOUNT_SID": ACCOUNT,
            "DAYTELLO_VOICE_RELAY_API_KEY_SID": "SK" + "d" * 32,
            "DAYTELLO_VOICE_RELAY_API_KEY_SECRET": "offline-key-secret",
            "DAYTELLO_VOICE_RELAY_PUBLIC_ORIGIN": "https://relay.example.test",
            "DAYTELLO_VOICEMAIL_TEST_PUBLIC_ORIGIN": "https://relay.example.test",
            "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true",
            "DAYTELLO_VOICEMAIL_TEST_RECIPIENT_MAP":
                '{"new-shop":"'+OWNER+'","stans-shop":"+12405550133"}',
            "DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP":
                '{"+12405550132":"stans-shop"}',
            "DAYTELLO_VOICEMAIL_LINK_KEY": Fernet.generate_key().decode(),
            "HIGHLEVEL_LOCATION_ID": "loc-test",
            "HIGHLEVEL_SMS_FROM_NUMBER": "+12405550139",
        })
        self.env.start()
        app = FastAPI()
        app.include_router(ai_setup.router, prefix="/api/ai-setup")
        app.include_router(voicemail_contact_number.router, prefix="/api")
        app.include_router(voice_relay.router, prefix="/api")
        def db_override():
            with self.factory() as db:
                yield db
        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[get_current_user] = lambda: self.owner
        self.client = TestClient(app)
        self.sent = []
        self.provider = None
        self.agent_action = None

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.engine.dispose()

    def _provider(self, found=True):
        """Provider lookups are read-only; purchases must be unapproved."""
        verified = {"number": RELAY, "route_verified": True}
        provider = SimpleNamespace(
            find_existing=lambda shop_id, **kw: verified if found else None,
            purchase_approved_number=lambda shop_id, number, *, approved=False:
                self._no_purchase(shop_id, number, approved, verified),
        )
        self.provider = provider
        return provider

    def _no_purchase(self, shop_id, number, approved, verified):
        self.assertEqual(shop_id, "new-id")
        self.assertEqual(number, RELAY)
        self.assertFalse(approved, "The new-shop recovery path cannot purchase a DID")
        return verified

    def _get_agent(self, agent_id, location_id):
        self.assertEqual(agent_id, "agent-new")
        self.assertEqual(location_id, "loc-test")
        return {"agentName": "DayTello New Shop",
                "locationId": "loc-test",
                "actions": [self.agent_action] if self.agent_action else []}

    def _save_action(self, method, path, json_body=None, **kwargs):
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/voice-ai/actions")
        self.assertEqual(json_body["actionParameters"]["transferToValue"], RELAY)
        self.agent_action = {"_id": "new-action", **json_body}
        return SimpleNamespace(status_code=201)

    def _activate_customer_selected_ai_number(self):
        # The same endpoint used by onboarding, with a number already owned
        # by the isolated HighLevel location. No chargeable purchase occurs.
        response = self.client.post(
            "/api/ai-setup/phone-number/purchase",
            json={"phone_number": AI_NUMBER},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["already_owned"])
        self.assertEqual(response.json()["phone_number"], AI_NUMBER)

    def _signed_callback(self, path, fields):
        fields = {"AccountSid": ACCOUNT, "CallSid": CALL, **fields}
        signed = "https://relay.example.test" + path
        signed += "".join(k + fields[k] for k in sorted(fields))
        signature = base64.b64encode(hmac.new(
            b"offline-relay-secret", signed.encode(), hashlib.sha1,
        ).digest()).decode()
        return self.client.post(path, content=urlencode(fields), headers={
            "content-type": "application/x-www-form-urlencoded",
            "x-twilio-signature": signature,
        })

    def test_selected_ai_number_to_missed_call_sms_and_playable_link(self):
        with (
            patch.object(ai_setup, "get_location_phone_numbers",
                         return_value=(None, [{"phoneNumber": AI_NUMBER}])),
            patch.object(ai_setup, "route_phone_number_to_shop_agent",
                         return_value={"phoneNumber": AI_NUMBER}),
            patch.object(ai_setup, "get_agent_detail", side_effect=self._get_agent),
            patch.object(ai_setup, "highlevel_raw_request", side_effect=self._save_action),
            patch.object(ai_setup, "purchase_one_highlevel_phone_number",
                         side_effect=AssertionError("Unexpected HighLevel number purchase")),
            patch.object(voicemail_contact_number, "VoiceRelayNumberProvider",
                         return_value=self._provider()),
            patch.object(voice_relay_delivery, "SessionLocal", self.factory),
            patch.object(voice_relay_delivery, "send_highlevel_sms",
                         side_effect=self._capture_sms),
        ):
            self._activate_customer_selected_ai_number()
            saved = self.client.put(
                "/api/shops/new-shop/call-voicemail-number",
                json={"phone_number": OWNER},
            )
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertEqual(saved.json()["voicemail_number"], RELAY)
            self.assertTrue(saved.json()["test_relay_enabled_for_calls"])
            self.assertFalse(saved.json()["setup_complete"])
            self.assertEqual(
                self.agent_action["actionParameters"]["transferToValue"], RELAY,
            )
            with self.factory() as db:
                shop = db.get(Shop, "new-id")
                self.assertEqual(shop.highlevel_phone_number, AI_NUMBER)
                self.assertTrue(db.get(DayTelloVoiceRelayAssignment, "new-id").enabled)
                settings = db.get(DayTelloVoicemailShopSettings, "new-id")
                self.assertEqual(settings.owner_phone, OWNER)
                self.assertTrue(settings.notifications_enabled)
                stan = db.get(DayTelloVoicemailShopSettings, "stan-id")
                self.assertEqual(stan.receiving_number, "+12405550132")
                self.assertEqual(stan.owner_phone, "+12405550133")

            inbound = self._signed_callback(
                "/api/daytello/voice-relay/inbound", {"To": RELAY},
            )
            self.assertEqual(inbound.status_code, 200, inbound.text)
            self.assertIn("<Dial", inbound.text)
            self.assertIn(OWNER, inbound.text)
            self.assertIn("dial-finished", inbound.text)
            missed = self._signed_callback(
                "/api/daytello/voice-relay/dial-finished",
                {"DialCallStatus": "no-answer"},
            )
            self.assertEqual(missed.status_code, 200, missed.text)
            self.assertIn("<Record", missed.text)
            self.assertIn("record-ready", missed.text)
            ready = self._signed_callback(
                "/api/daytello/voice-relay/record-ready",
                {"RecordingStatus": "completed", "RecordingSid": RECORDING},
            )
            self.assertEqual(ready.status_code, 200, ready.text)
            self.assertEqual(ready.json()["action"], "queued")
            self.assertEqual(len(self.sent), 1)
            recipient, message, metadata = self.sent[0]
            self.assertEqual(recipient, OWNER)
            self.assertEqual(metadata["shop_id"], "new-id")
            self.assertEqual(metadata["source_id"], RECORDING)
            link = message.split("Listen: ", 1)[1]
            self.assertEqual(urlsplit(link).hostname, "relay.example.test")
            # A provider-authenticated MP3 proxy is used, not a public
            # recording URL embedded in the owner SMS.
            audio = b"\xff\xfb\x90\x64offline-audio"
            original_client = httpx.AsyncClient
            def audio_response(request):
                self.assertEqual(request.method, "GET")
                self.assertIn(RECORDING + ".mp3", str(request.url))
                self.assertTrue(request.headers.get("authorization", "").startswith("Basic "))
                return httpx.Response(200, headers={"content-type": "audio/mpeg"},
                                      content=audio)
            with patch.object(voice_relay_delivery.httpx, "AsyncClient",
                              side_effect=lambda **kw: original_client(
                                  transport=httpx.MockTransport(audio_response), **kw)):
                playback = self.client.get(urlsplit(link).path)
            self.assertEqual(playback.status_code, 200, playback.text)
            self.assertEqual(playback.content, audio)
            duplicate = self._signed_callback(
                "/api/daytello/voice-relay/record-ready",
                {"RecordingStatus": "completed", "RecordingSid": RECORDING},
            )
            self.assertEqual(duplicate.status_code, 200)
            self.assertEqual(duplicate.json()["action"], "duplicate")
            self.assertEqual(len(self.sent), 1)

    def _capture_sms(self, recipient, message, **kwargs):
        self.sent.append((recipient, message, kwargs))
        return {"success": True}

    def test_no_preowned_relay_never_purchases_or_changes_transfer(self):
        with (
            patch.object(voicemail_contact_number, "VoiceRelayNumberProvider",
                         return_value=self._provider(found=False)),
            patch.object(voicemail_contact_number, "daytello_save_staff_transfer") as transfer,
        ):
            response = self.client.put(
                "/api/shops/new-shop/call-voicemail-number",
                json={"phone_number": OWNER},
            )
        self.assertEqual(response.status_code, 409, response.text)
        transfer.assert_not_called()
        with self.factory() as db:
            self.assertIsNone(db.get(DayTelloVoiceRelayAssignment, "new-id"))
            self.assertIsNone(db.get(DayTelloVoicemailShopSettings, "new-id"))
            self.assertEqual(
                db.get(DayTelloVoicemailShopSettings, "stan-id").owner_phone,
                "+12405550133",
            )


if __name__ == "__main__":
    unittest.main()
