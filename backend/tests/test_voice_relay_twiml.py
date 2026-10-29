"""Offline tests for the programmable voice relay response builders."""
import unittest
from xml.etree import ElementTree as ET

from app.voice_relay_twiml import (
    forward_to_employee, voicemail_after_unanswered, completed_recording,
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

    def test_finished_recording_hangs_up(self):
        self.assertIsNotNone(ET.fromstring(completed_recording()).find("Hangup"))


if __name__ == "__main__":
    unittest.main()
