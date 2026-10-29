"""Offline tests for the programmable voice relay response builders."""
import unittest
from xml.etree import ElementTree as ET

from app.voice_relay_twiml import (
    forward_to_employee, voicemail_after_unanswered, completed_recording, after_employee_dial,
)


class RelayTwiMLTests(unittest.TestCase):
    def test_employee_dial_uses_provider_callback(self):
        root = ET.fromstring(forward_to_employee(
            "+12405550123", "https://example.test/voice/dial-complete",
        ))
        dial = root.find("Dial")
        self.assertEqual(dial.attrib["timeout"], "15")
        self.assertEqual(dial.attrib["method"], "POST")
        self.assertEqual(dial.findtext("Number"), "+12405550123")

    def test_bad_number_or_callback_rejected(self):
        with self.assertRaises(ValueError):
            forward_to_employee("+1555", "https://example.test/callback")
        with self.assertRaises(ValueError):
            forward_to_employee("+12405550123", "http://example.test/callback")
        with self.assertRaises(ValueError):
            forward_to_employee("+12405550123", "https://example.test/callback", timeout=100)

    def test_voicemail_callback_is_recording_complete(self):
        root = ET.fromstring(voicemail_after_unanswered(
            "https://example.test/voice/record-finished",
            "https://example.test/voice/record-ready",
        ))
        record = root.find("Record")
        self.assertEqual(record.attrib["recordingStatusCallbackEvent"], "completed")
        self.assertEqual(record.attrib["maxLength"], "120")
        self.assertIsNotNone(root.find("Hangup"))

    def test_answered_employee_call_never_goes_to_voicemail(self):
        result = ET.fromstring(after_employee_dial(
            "completed", "https://example.test/record-finished",
            "https://example.test/record-ready",
        ))
        self.assertIsNone(result.find("Record"))
        self.assertIsNotNone(result.find("Hangup"))

    def test_unanswered_or_busy_goes_to_voicemail(self):
        for status in ("no-answer", "busy", "failed", "canceled"):
            with self.subTest(status=status):
                result = ET.fromstring(after_employee_dial(
                    status, "https://example.test/record-finished",
                    "https://example.test/record-ready",
                ))
                self.assertIsNotNone(result.find("Record"))

    def test_unexpected_status_fails_closed(self):
        with self.assertRaises(ValueError):
            after_employee_dial(
                "", "https://example.test/record-finished",
                "https://example.test/record-ready",
            )

    def test_finished_recording_hangs_up(self):
        self.assertIsNotNone(ET.fromstring(completed_recording()).find("Hangup"))


if __name__ == "__main__":
    unittest.main()
