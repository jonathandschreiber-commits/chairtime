"""Offline voice callback signature validation checks."""
import base64
import hashlib
import hmac
import unittest

from app.voice_relay_security import verify_voice_provider_signature


def signature(url, fields, token):
    message = url + "".join(k + fields[k] for k in sorted(fields))
    return base64.b64encode(hmac.new(
        token.encode(), message.encode(), hashlib.sha1
    ).digest()).decode()


class RelaySignatureTests(unittest.TestCase):
    def test_valid_signature(self):
        url = "https://daytello.example/api/voice/transfer?shop=ignored"
        fields = {"CallSid": "CA123", "DialCallStatus": "no-answer"}
        sig = signature(url, fields, "private-test-token")
        self.assertTrue(verify_voice_provider_signature(
            url, fields, sig, "private-test-token"))

    def test_tampering_or_wrong_token(self):
        url = "https://daytello.example/api/voice/transfer"
        fields = {"CallSid": "CA123"}
        sig = signature(url, fields, "private-test-token")
        self.assertFalse(verify_voice_provider_signature(
            url, {"CallSid": "CA124"}, sig, "private-test-token"))
        self.assertFalse(verify_voice_provider_signature(
            url, fields, sig, "different-token"))
        self.assertFalse(verify_voice_provider_signature(
            url, fields, "", "private-test-token"))


    def test_malformed_callback_urls_fail_closed_without_raising(self):
        fields = {"CallSid": "CA123"}
        token = "private-test-token"
        for url in (
            "https://example.test:invalid/voice",
            "https://example.test:0/voice",
            "https://example.test:65536/voice",
            "https://example.test\\\\evil/voice",
            "https://example.test\\n/voice",
            "https://user:password@example.test/voice",
            "https://example.test/voice#fragment",
            "https://[bad-ipv6/voice",
        ):
            with self.subTest(url=repr(url)):
                self.assertFalse(verify_voice_provider_signature(
                    url, fields, signature(url, fields, token), token))
        self.assertFalse(verify_voice_provider_signature(
            "https://example.test/voice", fields, 123, token))
        self.assertFalse(verify_voice_provider_signature(
            "https://example.test/voice", fields, "sig", 123))

    def test_http_or_non_form_values_fail_closed(self):
        self.assertFalse(verify_voice_provider_signature(
            "http://daytello.example/voice", {}, "abc", "token"))
        self.assertFalse(verify_voice_provider_signature(
            "https://daytello.example/voice",
            {"CallSid": ["CA123"]}, "abc", "token"))


if __name__ == "__main__":
    unittest.main()
