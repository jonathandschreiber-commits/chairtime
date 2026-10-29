"""Fail-closed relay integration checks. No real provider calls."""
import base64
import hashlib
import hmac
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.routes.voice_relay import router
from app.voice_relay_models import DayTelloVoiceRelayAssignment


DID = "+12405550123"
OWNER = "+12405550124"
CALL = "CA" + "a" * 32


class FakeQuery:
    def __init__(self, result, expected_did=None):
        self.result = result
        self.expected_did = expected_did
        self.conditions = []
    def filter(self, *args):
        self.conditions.extend(args)
        return self
    def one_or_none(self):
        if self.expected_did is not None and not any(str(c.right.value) == self.expected_did for c in self.conditions if hasattr(c, 'right') and hasattr(c.right, 'value')):
            return None
        return self.result


class FakeDB:
    def __init__(self, enabled=True):
        self.enabled = enabled
    def query(self, model):
        if model is DayTelloVoiceRelayAssignment:
            return FakeQuery(SimpleNamespace(
                shop_id="third-shop-id", relay_number=DID, enabled=self.enabled), DID)
        return FakeQuery(SimpleNamespace(
            id="third-shop-id", ai_voice_enabled=True))
    def get(self, model, shop_id):
        return SimpleNamespace(owner_phone=OWNER)


class RelayRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: FakeDB()
        self.client = TestClient(app)
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICE_RELAY_TEST_ONLY": "true",
            "DAYTELLO_VOICE_RELAY_AUTH_TOKEN": "test-only-secret",
            "DAYTELLO_VOICE_RELAY_PUBLIC_ORIGIN": "https://relay.example.test",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def request(self, path, fields, valid=True):
        from urllib.parse import urlencode
        body = urlencode(fields)
        signed = "https://relay.example.test" + path
        signed += "".join(k + fields[k] for k in sorted(fields))
        signature = base64.b64encode(hmac.new(
            b"test-only-secret", signed.encode(), hashlib.sha1,
        ).digest()).decode() if valid else "invalid-signature"
        return self.client.post(path, content=body, headers={
            "content-type": "application/x-www-form-urlencoded",
            "x-twilio-signature": signature,
        })

    def test_inbound_dials_one_shops_saved_number(self):
        response = self.request("/api/daytello/voice-relay/inbound",
                                {"CallSid": CALL, "To": DID})
        self.assertEqual(response.status_code, 200)
        self.assertIn(OWNER, response.text)
        self.assertIn("dial-finished", response.text)

    def test_rejects_tampering(self):
        result = self.request("/api/daytello/voice-relay/inbound",
                              {"CallSid": CALL, "To": DID}, valid=False)
        self.assertEqual(result.status_code, 401)

    def test_unknown_did_is_not_routed(self):
        result = self.request("/api/daytello/voice-relay/inbound",
                              {"CallSid": CALL, "To": "+12405550198"})
        self.assertEqual(result.status_code, 404)

    def test_answered_call_does_not_record(self):
        result = self.request("/api/daytello/voice-relay/dial-finished",
                              {"CallSid": CALL, "To": DID, "DialCallStatus": "completed"})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("<Record", result.text)

    def test_missed_call_prompts_voicemail(self):
        result = self.request("/api/daytello/voice-relay/dial-finished",
                              {"CallSid": CALL, "To": DID, "DialCallStatus": "no-answer"})
        self.assertEqual(result.status_code, 200)
        self.assertIn("<Record", result.text)

    def test_recording_does_not_send_sms_prematurely(self):
        result = self.request("/api/daytello/voice-relay/record-ready", {
            "CallSid": CALL, "To": DID,
            "RecordingStatus": "completed", "RecordingSid": "RE" + "b" * 32,
        })
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["notification_sent"])

    def test_feature_disabled_by_default(self):
        with patch.dict(os.environ, {"DAYTELLO_VOICE_RELAY_TEST_ONLY": "false"}):
            result = self.request("/api/daytello/voice-relay/inbound",
                                  {"CallSid": CALL, "To": DID})
            self.assertEqual(result.status_code, 404)


if __name__ == "__main__":
    unittest.main()
