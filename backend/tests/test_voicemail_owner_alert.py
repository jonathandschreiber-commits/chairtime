"""Offline tests for test-only voicemail owner configuration and signed links.

Run in backend/: python -m unittest discover -s tests -p test_voicemail_owner_alert.py -v
"""
import json
import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.voicemail_owner_links import (
    decode_recording_link, make_recording_link, owner_phone_for_test_shop,
)


class OwnerVoicemailSafetyTests(unittest.TestCase):
    def setUp(self):
        self.key = Fernet.generate_key().decode("ascii")
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true",
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "DAYTELLO_VOICEMAIL_OWNER_PHONE_MAP": json.dumps({
                "stan-s-shop": "+12025550125",
            }),
            "DAYTELLO_VOICEMAIL_TEST_RECIPIENT": "+12025550125",
            "DAYTELLO_VOICEMAIL_LINK_KEY": self.key,
            "DAYTELLO_VOICEMAIL_TEST_PUBLIC_ORIGIN": "https://daytello-voicemail-test.example.org",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_only_explicit_test_recipient_receives_sms(self):
        self.assertEqual(
            owner_phone_for_test_shop("stan-s-shop"), "+12025550125"
        )
        with self.assertRaises(HTTPException):
            owner_phone_for_test_shop("daves-shop")

    def test_feature_defaults_off(self):
        os.environ["DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED"] = "false"
        self.assertIsNone(owner_phone_for_test_shop("stan-s-shop"))

    def test_denies_recipient_not_on_allowlist(self):
        os.environ["DAYTELLO_VOICEMAIL_TEST_RECIPIENT"] = "+12025550126"
        with self.assertRaises(HTTPException):
            owner_phone_for_test_shop("stan-s-shop")

    def test_denies_live_mode(self):
        os.environ["DAYTELLO_VOICEMAIL_TEST_ONLY"] = "false"
        with self.assertRaises(HTTPException):
            owner_phone_for_test_shop("stan-s-shop")

    def test_listening_link_roundtrip_and_tamper_rejection(self):
        link = make_recording_link("location-demo", "message-demo", "shop-demo")
        token = link.rsplit("/", 1)[-1]
        payload = decode_recording_link(token)
        self.assertEqual(payload["location"], "location-demo")
        self.assertEqual(payload["message"], "message-demo")
        self.assertEqual(payload["shop"], "shop-demo")
        with self.assertRaises(HTTPException):
            decode_recording_link(token + "tampered")

    def test_invalid_key_denied(self):
        os.environ["DAYTELLO_VOICEMAIL_LINK_KEY"] = ""
        with self.assertRaises(HTTPException):
            make_recording_link("loc", "msg", "shop")


if __name__ == "__main__":
    unittest.main()
