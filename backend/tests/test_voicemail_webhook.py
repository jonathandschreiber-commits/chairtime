"""Offline tests for the draft DayTello voicemail receiver.

Run from backend/: python -m unittest discover -s tests -p test_voicemail_webhook.py
These tests do not contact HighLevel, send SMS, or connect to Railway.
"""

import base64
import json
import os
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from app.routes import voicemail_webhook as voicemail


class SignatureTests(unittest.TestCase):
    def setUp(self):
        key = Ed25519PrivateKey.generate()
        self.key = key
        self.public_key_pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    def sign(self, body):
        return base64.b64encode(self.key.sign(body)).decode("ascii")

    def test_valid_signature(self):
        body = b'{"type":"InboundMessage","status":"voicemail"}'
        with patch.object(voicemail, "GHL_WEBHOOK_ED25519_PUBLIC_KEY", self.public_key_pem):
            self.assertTrue(voicemail.verify_ghl_signature(body, self.sign(body)))

    def test_tampering_rejected(self):
        body = b'{"to":"+12029725238"}'
        tampered = b'{"to":"+12029725239"}'
        with patch.object(voicemail, "GHL_WEBHOOK_ED25519_PUBLIC_KEY", self.public_key_pem):
            self.assertFalse(voicemail.verify_ghl_signature(tampered, self.sign(body)))

    def test_unsigned_rejected(self):
        self.assertFalse(voicemail.verify_ghl_signature(b"{}", None))
        self.assertFalse(voicemail.verify_ghl_signature(b"{}", "N/A"))

    def test_malformed_signature_rejected(self):
        with patch.object(voicemail, "GHL_WEBHOOK_ED25519_PUBLIC_KEY", self.public_key_pem):
            self.assertFalse(voicemail.verify_ghl_signature(b"{}", "not_base64!"))
            self.assertFalse(
                voicemail.verify_ghl_signature(
                    b"{}", base64.b64encode(b"too short").decode("ascii")
                )
            )


class RoutingTests(unittest.TestCase):
    def check_bad_map(self, raw):
        with patch.dict(os.environ, {"DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP": raw}):
            with self.assertRaises(HTTPException) as error:
                voicemail.configured_routing_map()
            self.assertEqual(error.exception.status_code, 503)

    def test_one_number_one_shop(self):
        mapping = {"+12029725238": "stan-s-shop"}
        with patch.dict(
            os.environ, {"DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP": json.dumps(mapping)}
        ):
            self.assertEqual(voicemail.configured_routing_map(), mapping)

    def test_duplicate_shop_mapping_rejected(self):
        self.check_bad_map(
            json.dumps({
                "+12029725238": "stan-s-shop",
                "+12029725239": "stan-s-shop",
            })
        )

    def test_missing_mapping_rejected(self):
        self.check_bad_map("")

    def test_invalid_json_rejected(self):
        self.check_bad_map("{")

    def test_non_e164_number_rejected(self):
        self.check_bad_map('{"2403875085": "stan-s-shop"}')

    def test_invalid_slug_rejected(self):
        self.check_bad_map('{"+12029725238": "../stan-s-shop"}')


class EventClassificationTests(unittest.TestCase):
    def setUp(self):
        self.voicemail_event = {
            "type": "InboundMessage",
            "direction": "inbound",
            "messageType": "CALL",
            "status": "voicemail",
            "messageTypeString": "TYPE_CALL",
        }

    def test_accepts_documented_voicemail(self):
        self.assertTrue(voicemail.is_voicemail_event(self.voicemail_event))

    def test_accepts_legacy_voicemail_string(self):
        event = dict(self.voicemail_event, messageTypeString="TYPE_VOICEMAIL")
        self.assertTrue(voicemail.is_voicemail_event(event))

    def test_ignores_no_answer_without_voicemail_status(self):
        event = dict(self.voicemail_event, status="no-answer", callStatus="no-answer")
        self.assertFalse(voicemail.is_voicemail_event(event))

    def test_ignores_completed_calls(self):
        event = dict(self.voicemail_event, status="completed")
        self.assertFalse(voicemail.is_voicemail_event(event))

    def test_ignores_sms(self):
        event = dict(self.voicemail_event, messageTypeString="TYPE_SMS")
        self.assertFalse(voicemail.is_voicemail_event(event))

    def test_ignores_outbound(self):
        event = dict(self.voicemail_event, direction="outbound")
        self.assertFalse(voicemail.is_voicemail_event(event))

    def test_ignores_other_types(self):
        event = dict(self.voicemail_event, type="ContactUpdate")
        self.assertFalse(voicemail.is_voicemail_event(event))


if __name__ == "__main__":
    unittest.main()
