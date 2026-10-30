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
from app.voice_relay_delivery import DayTelloVoiceRelayCall
from app.voicemail_models import DayTelloVoicemailShopSettings


DID = "+12405550123"
OWNER = "+12405550124"
CALL = "CA" + "a" * 32
ACCOUNT = "AC" + "d" * 32


class FakeQuery:
    def __init__(self, result, expected_did=None, other_ai_number=None,
                 other_business_number=None, business_shop_id="other-shop-id"):
        self.result = result
        self.expected_did = expected_did
        self.other_ai_number = other_ai_number
        self.other_business_number = other_business_number
        self.business_shop_id = business_shop_id
        self.conditions = []
    def filter(self, *args):
        self.conditions.extend(args)
        return self
    def one_or_none(self):
        if self.expected_did is not None and not any(str(c.right.value) == self.expected_did for c in self.conditions if hasattr(c, 'right') and hasattr(c.right, 'value')):
            return None
        return self.result
    def first(self):
        if self.other_ai_number and any(
            getattr(getattr(c, "left", None), "key", None) == "highlevel_phone_number"
            and getattr(getattr(c, "right", None), "value", None) == self.other_ai_number
            for c in self.conditions
        ):
            return SimpleNamespace(id="other-shop-id")
        if self.other_business_number and any(
            getattr(getattr(c, "left", None), "key", None) == "phone"
            and getattr(getattr(c, "right", None), "value", None) == self.other_business_number
            for c in self.conditions
        ):
            # Model the old SQL filter excluding this same shop's own line.
            excluded = any(
                getattr(getattr(c, "left", None), "key", None) == "id"
                and getattr(getattr(c, "right", None), "value", None) == self.business_shop_id
                and getattr(getattr(c, "operator", None), "__name__", "") == "ne"
                for c in self.conditions
            )
            if not excluded:
                return SimpleNamespace(id=self.business_shop_id)
        return None


class FakeRelayQuery:
    def __init__(self, enabled, other_relay_number):
        self.bindings = {
            DID: SimpleNamespace(
                shop_id="third-shop-id", relay_number=DID, enabled=enabled),
        }
        if other_relay_number:
            self.bindings[other_relay_number] = SimpleNamespace(
                shop_id="other-shop-id", relay_number=other_relay_number,
                enabled=False,
            )
        self.number = None

    def filter(self, *args):
        self.number = next(
            (str(c.right.value) for c in args
             if hasattr(c, "right") and hasattr(c.right, "value")), None
        )
        return self

    def one_or_none(self):
        return self.bindings.get(self.number)


class FakeVoicemailQuery:
    def __init__(self, receiving_number):
        self.receiving_number = receiving_number
        self.lookup_number = None

    def filter(self, *args):
        self.lookup_number = next(
            (str(c.right.value) for c in args
             if hasattr(c, "right") and hasattr(c.right, "value")), None
        )
        return self

    def first(self):
        if self.receiving_number and self.lookup_number == self.receiving_number:
            return SimpleNamespace(shop_id="other-shop-id")
        return None


class FakeDB:
    def __init__(self, enabled=True, owner_phone=OWNER, other_relay_number=None,
                 other_voicemail_number=None, other_ai_number=None,
                 other_business_number=None, business_shop_id="other-shop-id"):
        self.enabled = enabled
        self.owner_phone = owner_phone
        self.other_relay_number = other_relay_number
        self.other_voicemail_number = other_voicemail_number
        self.other_ai_number = other_ai_number
        self.other_business_number = other_business_number
        self.business_shop_id = business_shop_id
        self.calls = {}

    def add(self, record):
        self.calls[record.call_sid] = record

    def commit(self):
        pass

    def rollback(self):
        pass

    def query(self, model):
        if model is DayTelloVoiceRelayAssignment:
            return FakeRelayQuery(self.enabled, self.other_relay_number)
        if model is DayTelloVoicemailShopSettings:
            return FakeVoicemailQuery(self.other_voicemail_number)
        return FakeQuery(SimpleNamespace(
            id="third-shop-id", ai_voice_enabled=True),
            other_ai_number=self.other_ai_number,
            other_business_number=self.other_business_number,
            business_shop_id=self.business_shop_id)

    def get(self, model, shop_id):
        if model is DayTelloVoiceRelayCall:
            return self.calls.get(shop_id)
        return SimpleNamespace(owner_phone=self.owner_phone)


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
            "DAYTELLO_VOICE_RELAY_ACCOUNT_SID": ACCOUNT,
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def request(self, path, fields, valid=True, content_type="application/x-www-form-urlencoded"):
        from urllib.parse import urlencode
        fields = dict(fields)
        fields.setdefault("AccountSid", ACCOUNT)
        body = urlencode(fields)
        signed = "https://relay.example.test" + path
        signed += "".join(k + fields[k] for k in sorted(fields))
        signature = base64.b64encode(hmac.new(
            b"test-only-secret", signed.encode(), hashlib.sha1,
        ).digest()).decode() if valid else "invalid-signature"
        return self.client.post(path, content=body, headers={
            "content-type": content_type,
            "x-twilio-signature": signature,
        })

    def seed_call(self):
        # Simulate the durable binding written by a prior signed inbound
        # callback, without granting trust to the later callback's To field.
        db = self.client.app.dependency_overrides[get_db]()
        db.calls[CALL] = SimpleNamespace(
            call_sid=CALL, account_sid=ACCOUNT,
            shop_id="third-shop-id", relay_number=DID,
        )
        self.client.app.dependency_overrides[get_db] = lambda: db

    def test_rejects_ambiguous_content_types_before_routing(self):
        fields = {"CallSid": CALL, "To": DID}
        for content_type in (
            "text/plain; application/x-www-form-urlencoded",
            "application/x-www-form-urlencoded-evil",
            "application/x-www-form-urlencoded; charset=iso-8859-1",
            "application/x-www-form-urlencoded; charset=utf-8; boundary=bad",
        ):
            with self.subTest(content_type=content_type):
                result = self.request(
                    "/api/daytello/voice-relay/inbound", fields,
                    content_type=content_type,
                )
                self.assertEqual(result.status_code, 415)
                self.assertNotIn("<Dial", result.text)

    def test_valid_utf8_form_content_type_still_routes(self):
        result = self.request(
            "/api/daytello/voice-relay/inbound",
            {"CallSid": CALL, "To": DID},
            content_type="application/x-www-form-urlencoded; charset=UTF-8",
        )
        self.assertEqual(result.status_code, 200)
        self.assertIn("<Dial", result.text)

    def test_invalid_percent_encoded_utf8_is_rejected(self):
        # parse_qsl's default errors='replace' would silently normalize %FF.
        result = self.client.post(
            "/api/daytello/voice-relay/inbound",
            content=f"CallSid={CALL}&To=%FF",
            headers={"content-type": "application/x-www-form-urlencoded",
                     "x-twilio-signature": "invalid"},
        )
        self.assertEqual(result.status_code, 400)
        self.assertNotIn("<Dial", result.text)

    def test_excessive_form_fields_are_rejected(self):
        result = self.client.post(
            "/api/daytello/voice-relay/inbound",
            content="&".join(f"field{i}=value" for i in range(65)),
            headers={"content-type": "application/x-www-form-urlencoded",
                     "x-twilio-signature": "invalid"},
        )
        self.assertEqual(result.status_code, 400)
        self.assertNotIn("<Dial", result.text)

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

    def test_rejects_self_forwarding_loop(self):
        self.client.app.dependency_overrides[get_db] = lambda: FakeDB(owner_phone=DID)
        result = self.request("/api/daytello/voice-relay/inbound",
                              {"CallSid": CALL, "To": DID})
        self.assertEqual(result.status_code, 409)
        self.assertNotIn("<Dial", result.text)

    def test_rejects_cross_shop_relay_even_if_disabled(self):
        self.client.app.dependency_overrides[get_db] = lambda: FakeDB(
            owner_phone=OWNER, other_relay_number=OWNER)
        result = self.request("/api/daytello/voice-relay/inbound",
                              {"CallSid": CALL, "To": DID})
        self.assertEqual(result.status_code, 409)
        self.assertNotIn("<Dial", result.text)

    def test_rejects_owner_phone_that_is_another_shops_voicemail_did(self):
        # A HighLevel voicemail DID need not exist in the programmable
        # relay table. It must still never be used as an owner's phone.
        self.client.app.dependency_overrides[get_db] = lambda: FakeDB(
            owner_phone=OWNER, other_voicemail_number=OWNER)
        result = self.request("/api/daytello/voice-relay/inbound",
                              {"CallSid": CALL, "To": DID})
        self.assertEqual(result.status_code, 409)
        self.assertNotIn("<Dial", result.text)

    def test_rejects_forwarding_to_another_shops_ai_receptionist(self):
        # The AI's inbound DID is distinct from its voicemail/relay DID.
        # Forwarding to it can recurse through a second tenant's AI agent.
        self.client.app.dependency_overrides[get_db] = lambda: FakeDB(
            owner_phone=OWNER, other_ai_number=OWNER)
        result = self.request("/api/daytello/voice-relay/inbound",
                              {"CallSid": CALL, "To": DID})
        self.assertEqual(result.status_code, 409)
        self.assertNotIn("<Dial", result.text)

    def test_rejects_another_shops_public_business_phone(self):
        # A shop's public line may route to its AI even without an explicit
        # highlevel_phone_number assignment in the database.
        self.client.app.dependency_overrides[get_db] = lambda: FakeDB(
            owner_phone=OWNER, other_business_number=OWNER)
        result = self.request("/api/daytello/voice-relay/inbound",
                              {"CallSid": CALL, "To": DID})
        self.assertEqual(result.status_code, 409)
        self.assertNotIn("<Dial", result.text)

    def test_same_shop_business_phone_blocks_inbound_relay(self):
        # A published line can loop back into this shop's AI receptionist.
        self.client.app.dependency_overrides[get_db] = lambda: FakeDB(
            owner_phone=OWNER, other_business_number=OWNER,
            business_shop_id="third-shop-id")
        result = self.request("/api/daytello/voice-relay/inbound",
                              {"CallSid": CALL, "To": DID})
        self.assertEqual(result.status_code, 409)
        self.assertNotIn("<Dial", result.text)

    def test_cross_shop_business_phone_blocks_dial_callback(self):
        self.client.app.dependency_overrides[get_db] = lambda: FakeDB(
            owner_phone=OWNER, other_business_number=OWNER)
        self.seed_call()
        result = self.request("/api/daytello/voice-relay/dial-finished",
                              {"CallSid": CALL, "To": DID,
                               "DialCallStatus": "no-answer"})
        self.assertEqual(result.status_code, 409)
        self.assertNotIn("<Record", result.text)

    def test_ai_receptionist_loop_is_rejected_on_dial_callback(self):
        self.client.app.dependency_overrides[get_db] = lambda: FakeDB(
            owner_phone=OWNER, other_ai_number=OWNER)
        self.seed_call()
        result = self.request("/api/daytello/voice-relay/dial-finished",
                              {"CallSid": CALL, "To": DID,
                               "DialCallStatus": "no-answer"})
        self.assertEqual(result.status_code, 409)
        self.assertNotIn("<Record", result.text)

    def test_voicemail_did_loop_is_rejected_on_dial_callback(self):
        self.client.app.dependency_overrides[get_db] = lambda: FakeDB(
            owner_phone=OWNER, other_voicemail_number=OWNER)
        self.seed_call()
        result = self.request("/api/daytello/voice-relay/dial-finished",
                              {"CallSid": CALL, "To": DID,
                               "DialCallStatus": "no-answer"})
        self.assertEqual(result.status_code, 409)
        self.assertNotIn("<Record", result.text)

    def test_disabled_relay_does_not_route(self):
        self.client.app.dependency_overrides[get_db] = lambda: FakeDB(enabled=False)
        result = self.request("/api/daytello/voice-relay/inbound",
                              {"CallSid": CALL, "To": DID})
        self.assertEqual(result.status_code, 404)

    def test_answered_call_does_not_record(self):
        self.seed_call()
        result = self.request("/api/daytello/voice-relay/dial-finished",
                              {"CallSid": CALL, "To": DID, "DialCallStatus": "completed"})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("<Record", result.text)

    def test_missed_call_prompts_voicemail(self):
        self.seed_call()
        result = self.request("/api/daytello/voice-relay/dial-finished",
                              {"CallSid": CALL, "To": DID, "DialCallStatus": "no-answer"})
        self.assertEqual(result.status_code, 200)
        self.assertIn("<Record", result.text)

    def test_canceled_transfer_hangs_up_without_voicemail(self):
        self.seed_call()
        result = self.request("/api/daytello/voice-relay/dial-finished",
                              {"CallSid": CALL, "To": DID, "DialCallStatus": "canceled"})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("<Record", result.text)
        self.assertIn("<Hangup", result.text)

    def test_unknown_dial_callback_cannot_start_voicemail_even_with_to(self):
        result = self.request("/api/daytello/voice-relay/dial-finished", {
            "CallSid": CALL, "To": DID, "DialCallStatus": "no-answer",
        })
        self.assertEqual(result.status_code, 404)
        self.assertNotIn("<Record", result.text)

    def test_dial_callback_to_must_match_saved_inbound_call(self):
        self.seed_call()
        result = self.request("/api/daytello/voice-relay/dial-finished", {
            "CallSid": CALL, "To": OWNER, "DialCallStatus": "no-answer",
        })
        self.assertEqual(result.status_code, 409)
        self.assertNotIn("<Record", result.text)

    def test_record_finished_requires_saved_inbound_call(self):
        result = self.request("/api/daytello/voice-relay/record-finished", {
            "CallSid": CALL, "To": DID,
        })
        self.assertEqual(result.status_code, 404)

    def test_record_finished_accepts_matching_saved_call(self):
        self.seed_call()
        result = self.request("/api/daytello/voice-relay/record-finished", {
            "CallSid": CALL, "To": DID,
        })
        self.assertEqual(result.status_code, 200)
        self.assertIn("<Hangup", result.text)

    def test_recording_callback_without_known_inbound_call_fails_closed(self):
        result = self.request("/api/daytello/voice-relay/record-ready", {
            "CallSid": CALL, "To": DID,
            "RecordingStatus": "completed", "RecordingSid": "RE" + "b" * 32,
        })
        self.assertEqual(result.status_code, 404)
        self.assertNotIn("notification_sent", result.text)

    def test_feature_disabled_by_default(self):
        with patch.dict(os.environ, {"DAYTELLO_VOICE_RELAY_TEST_ONLY": "false"}):
            result = self.request("/api/daytello/voice-relay/inbound",
                                  {"CallSid": CALL, "To": DID})
            self.assertEqual(result.status_code, 404)


    def test_public_origin_rejects_credentials_and_malformed_urls(self):
        # The origin determines the exact URL used for signature verification.
        for origin in (
            "http://relay.example.test",
            "https://user:secret@relay.example.test",
            "https://relay.example.test:invalid",
            "https://relay.example.test:0",
            "https://relay.example.test/path",
            "https://relay.example.test?query=1",
            "https://relay.example.test#fragment",
            "https://relay.example.test\\n",
        ):
            with self.subTest(origin=repr(origin)):
                with patch.dict(os.environ, {
                    "DAYTELLO_VOICE_RELAY_PUBLIC_ORIGIN": origin,
                }):
                    result = self.request("/api/daytello/voice-relay/inbound",
                                          {"CallSid": CALL, "To": DID})
                    self.assertEqual(result.status_code, 503)

    def test_duplicate_form_fields_rejected_before_signature_check(self):
        result = self.client.post("/api/daytello/voice-relay/inbound",
                                  content=f"CallSid={CALL}&To={DID}&To={OWNER}",
                                  headers={
                                      "content-type": "application/x-www-form-urlencoded",
                                      "x-twilio-signature": "invalid",
                                  })
        self.assertEqual(result.status_code, 400)

    def test_missing_call_identifier_and_unknown_dial_status_fail_closed(self):
        missing = self.request("/api/daytello/voice-relay/inbound", {"To": DID})
        self.assertEqual(missing.status_code, 422)
        self.seed_call()
        unexpected = self.request("/api/daytello/voice-relay/dial-finished", {
            "CallSid": CALL, "To": DID, "DialCallStatus": "mystery",
        })
        self.assertEqual(unexpected.status_code, 422)
        self.assertNotIn("<Record", unexpected.text)

    def test_disabled_relay_blocks_recording_callback_too(self):
        self.client.app.dependency_overrides[get_db] = lambda: FakeDB(enabled=False)
        result = self.request("/api/daytello/voice-relay/record-ready", {
            "CallSid": CALL, "To": DID,
            "RecordingStatus": "completed", "RecordingSid": "RE" + "b" * 32,
        })
        self.assertEqual(result.status_code, 404)
        self.assertNotIn("notification_sent", result.text)


if __name__ == "__main__":
    unittest.main()
