"""Offline validation for the programmable relay recording boundary."""
import unittest
from fastapi import HTTPException
from app.voice_relay_recordings import (
    verified_recording_reference, verified_recording_url,
)

ACCOUNT = "AC" + "a" * 32
RECORDING = "RE" + "b" * 32


class VoiceRelayRecordingTests(unittest.TestCase):
    def test_accepts_matching_signed_callback_reference(self):
        self.assertEqual(
            verified_recording_reference(
                {"AccountSid": ACCOUNT, "RecordingSid": RECORDING}, ACCOUNT),
            (ACCOUNT, RECORDING),
        )

    def test_rejects_wrong_account_or_invalid_recording(self):
        for fields in (
            {"AccountSid": "AC" + "c" * 32, "RecordingSid": RECORDING},
            {"AccountSid": ACCOUNT, "RecordingSid": "not-a-recording"},
            {"AccountSid": ACCOUNT},
        ):
            with self.subTest(fields=fields), self.assertRaises(HTTPException):
                verified_recording_reference(fields, ACCOUNT)

    def test_requires_configured_account(self):
        with self.assertRaises(HTTPException) as error:
            verified_recording_reference(
                {"AccountSid": ACCOUNT, "RecordingSid": RECORDING}, "")
        self.assertEqual(error.exception.status_code, 503)

    def test_only_exact_twilio_recording_resource_is_allowed(self):
        path = f"/2010-04-01/Accounts/{ACCOUNT}/Recordings/{RECORDING}"
        good = f"https://api.twilio.com{path}.json"
        self.assertEqual(
            verified_recording_url(good, ACCOUNT, RECORDING), good)
        for url in (
            f"http://api.twilio.com{path}",
            f"https://evil.example{path}",
            f"https://api.twilio.com.evil.example{path}",
            f"https://api.twilio.com{path}?redirect=https://evil.example",
            f"https://user:password@api.twilio.com{path}",
            f"https://api.twilio.com{path}/extra",
            f"https://api.twilio.com:bad{path}",
            f"https://api.twilio.com:65536{path}",
            f"https://api.twilio.com{path}\n",
            f"https://api.twilio.com{path}\t",
            f"https://api.twilio.com{path}" + chr(92),
            f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT}/Recordings/RE{'c'*32}",
        ):
            with self.subTest(url=url), self.assertRaises(HTTPException):
                verified_recording_url(url, ACCOUNT, RECORDING)


if __name__ == "__main__":
    unittest.main()
