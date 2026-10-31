"""Offline tests for the programmable voice relay response builders."""
import unittest
from xml.etree import ElementTree as ET

from app.voice_relay_twiml import (
    forward_to_employee, voicemail_after_unanswered, completed_recording, after_employee_dial,
    screen_owner_call, owner_screen_result,
)


class RelayTwiMLTests(unittest.TestCase):
    def test_employee_dial_uses_provider_callback(self):
        root = ET.fromstring(forward_to_employee(
            "+12405550123", "https://example.test/voice/dial-complete",
        ))
        dial = root.find("Dial")
        self.assertEqual(dial.attrib["timeout"], "5")
        self.assertEqual(dial.attrib["method"], "POST")
        self.assertEqual(dial.findtext("Number"), "+12405550123")

    def test_owner_must_confirm_before_bridge(self):
        root = ET.fromstring(forward_to_employee(
            "+12405550123", "https://example.test/dial-finished",
            owner_screen_url="https://example.test/owner-screen?parent=CA" + "a" * 32,
        ))
        number = root.find("Dial/Number")
        self.assertIn("owner-screen", number.attrib["url"])
        self.assertEqual(number.attrib["method"], "POST")
        challenge = ET.fromstring(screen_owner_call(
            "https://example.test/owner-accept",
        ))
        self.assertEqual(challenge.find("Gather").attrib["numDigits"], "1")
        self.assertIn("Press 1", challenge.findtext("Gather/Say"))
        self.assertIsNotNone(challenge.find("Hangup"))
        accepted = ET.fromstring(owner_screen_result("1"))
        self.assertIsNotNone(accepted.find("Say"))
        self.assertIsNone(accepted.find("Hangup"))
        for digits in ("", "2", None):
            with self.subTest(digits=digits):
                declined = ET.fromstring(owner_screen_result(digits))
                self.assertIsNotNone(declined.find("Hangup"))

    def test_carrier_voicemail_answer_does_not_bypass_fallback(self):
        # A call leg can answer (carrier voicemail) but never bridge.
        unbridged = ET.fromstring(after_employee_dial(
            "completed", "https://example.test/record-finished",
            "https://example.test/record-ready", dial_bridged="false",
        ))
        self.assertIsNotNone(unbridged.find("Record"))
        human = ET.fromstring(after_employee_dial(
            "completed", "https://example.test/record-finished",
            "https://example.test/record-ready", dial_bridged="true",
        ))
        self.assertIsNone(human.find("Record"))

    def test_bad_number_or_callback_rejected(self):
        with self.assertRaises(ValueError):
            forward_to_employee("+1555", "https://example.test/callback")
        with self.assertRaises(ValueError):
            forward_to_employee("+12405550123", "http://example.test/callback")
        with self.assertRaises(ValueError):
            forward_to_employee("+12405550123", "https://example.test/callback", timeout=100)


    def test_invalid_provider_callback_urls_are_rejected(self):
        for url in (
            "https://example.test:bad/voice",
            "https://example.test:0/voice",
            "https://example.test:65536/voice",
            "https://example.test\\\\evil/voice",
            "https://example.test\\n/voice",
            "https://user@example.test/voice",
            "https://example.test/voice#fragment",
            "https://[bad-ipv6/voice",
        ):
            with self.subTest(url=repr(url)):
                with self.assertRaises(ValueError):
                    forward_to_employee("+12405550123", url)
                with self.assertRaises(ValueError):
                    voicemail_after_unanswered(url, "https://example.test/ready")

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
        for status in ("no-answer", "busy", "failed"):
            with self.subTest(status=status):
                result = ET.fromstring(after_employee_dial(
                    status, "https://example.test/record-finished",
                    "https://example.test/record-ready",
                ))
                self.assertIsNotNone(result.find("Record"))

    def test_canceled_transfer_does_not_record_voicemail(self):
        # Provider cancellation is not equivalent to an unanswered timeout.
        result = ET.fromstring(after_employee_dial(
            "canceled", "https://example.test/record-finished",
            "https://example.test/record-ready",
        ))
        self.assertIsNone(result.find("Record"))
        self.assertIsNotNone(result.find("Hangup"))

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
