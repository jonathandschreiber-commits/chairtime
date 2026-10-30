"""Offline provider-backed DID provisioning tests. Never purchases real numbers."""
import os
import unittest

import httpx
from fastapi import HTTPException
from unittest.mock import patch

from app.voice_relay_provider import VoiceRelayNumberProvider, relay_shop_label

ACCOUNT = "AC" + "a" * 32
KEY = "SK" + "b" * 32
NUMBER = "+12405550123"
OTHER = "+12405550124"
PN = "PN" + "c" * 32
URL = "https://relay.example.test/api/daytello/voice-relay/inbound"
SHOP = "test-shop-3"


def record(shop=SHOP, number=NUMBER, **overrides):
    data = {
        "sid": PN, "account_sid": ACCOUNT,
        "phone_number": number, "friendly_name": relay_shop_label(shop),
        "voice_url": URL, "voice_method": "POST",
        "voice_application_sid": None, "trunk_sid": None,
        "capabilities": {"voice": True}, "status": "in-use",
    }
    data.update(overrides)
    return data


class FakeTwilio:
    def __init__(self, owned=None, *, fail_after_purchase=False, fail_before_purchase=False,
                 available=None):
        self.owned = list(owned or [])
        self.available = list(available or [])
        self.requests = []
        self.fail_after_purchase = fail_after_purchase
        self.fail_before_purchase = fail_before_purchase

    def handle(self, request):
        self.requests.append(request)
        assert request.url.host == "api.twilio.com"
        assert request.headers.get("authorization", "").startswith("Basic ")
        if request.method == "GET" and "/AvailablePhoneNumbers/" in request.url.path:
            assert request.url.params.get("VoiceEnabled") == "true"
            return httpx.Response(200, json={"available_phone_numbers": self.available})
        if request.method == "GET":
            if "FriendlyName" in request.url.params:
                label = request.url.params["FriendlyName"]
                matches = [r for r in self.owned if r["friendly_name"] == label]
            else:
                number = request.url.params.get("PhoneNumber")
                matches = [r for r in self.owned if r["phone_number"] == number]
            return httpx.Response(200, json={
                "incoming_phone_numbers": matches, "next_page_uri": None,
            })
        if request.method == "POST":
            if self.fail_before_purchase:
                raise httpx.ConnectError("connection lost", request=request)
            from urllib.parse import parse_qs
            fields = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            assert fields["VoiceUrl"] == URL
            assert fields["VoiceMethod"] == "POST"
            assert fields["PhoneNumber"] == NUMBER
            self.owned.append(record())
            if self.fail_after_purchase:
                raise httpx.ReadError("response lost", request=request)
            return httpx.Response(201, json=self.owned[-1])
        raise AssertionError("Unexpected provider operation")


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICE_RELAY_ACCOUNT_SID": ACCOUNT,
            "DAYTELLO_VOICE_RELAY_API_KEY_SID": KEY,
            "DAYTELLO_VOICE_RELAY_API_KEY_SECRET": "offline-secret",
            "DAYTELLO_VOICE_RELAY_AUTH_TOKEN": "offline-auth-token",
            "DAYTELLO_VOICE_RELAY_PUBLIC_ORIGIN": "https://relay.example.test",
            "DAYTELLO_VOICE_RELAY_TEST_ONLY": "true",
            "DAYTELLO_VOICE_RELAY_PURCHASE_ENABLED": "true",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def provider(self, fake):
        client = httpx.Client(transport=httpx.MockTransport(fake.handle))
        self.addCleanup(client.close)
        return VoiceRelayNumberProvider(client=client)

    def test_selects_only_valid_voice_number_from_requested_area_code(self):
        fake = FakeTwilio(available=[
            {"phone_number": OTHER, "capabilities": {"voice": True},
             "address_requirements": "none"},
            {"phone_number": "+13015550123", "capabilities": {"voice": True},
             "address_requirements": "none"},
            {"phone_number": NUMBER, "capabilities": {"voice": True},
             "address_requirements": "none"},
            {"phone_number": "+12405550125", "capabilities": {"voice": False},
             "address_requirements": "none"},
            {"phone_number": "+12405550126", "capabilities": {"voice": True},
             "address_requirements": "local"},
        ])
        chosen = self.provider(fake).find_available_voice_number("240")
        self.assertEqual(chosen, NUMBER)
        self.assertTrue(all(r.method == "GET" for r in fake.requests))

    def test_no_eligible_number_fails_without_purchase(self):
        fake = FakeTwilio(available=[
            {"phone_number": NUMBER, "capabilities": {"voice": True},
             "address_requirements": "local"},
        ])
        with self.assertRaises(HTTPException) as error:
            self.provider(fake).find_available_voice_number("240")
        self.assertEqual(error.exception.status_code, 409)
        self.assertTrue(all(r.method == "GET" for r in fake.requests))

    def test_invalid_area_code_fails_before_provider(self):
        fake = FakeTwilio()
        with self.assertRaises(HTTPException) as error:
            self.provider(fake).find_available_voice_number("000")
        self.assertEqual(error.exception.status_code, 422)
        self.assertFalse(fake.requests)

    def test_no_approval_never_purchases(self):
        fake = FakeTwilio()
        with self.assertRaises(HTTPException) as error:
            self.provider(fake).purchase_approved_number(SHOP, NUMBER)
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(any(r.method == "POST" for r in fake.requests))

    def test_disabled_platform_gate_never_purchases(self):
        fake = FakeTwilio()
        with patch.dict(os.environ, {"DAYTELLO_VOICE_RELAY_PURCHASE_ENABLED": "false"}):
            with self.assertRaises(HTTPException):
                self.provider(fake).purchase_approved_number(SHOP, NUMBER, approved=True)
        self.assertFalse(any(r.method == "POST" for r in fake.requests))

    def test_reuses_exact_existing_number_without_purchase(self):
        fake = FakeTwilio([record()])
        result = self.provider(fake).purchase_approved_number(SHOP, NUMBER)
        self.assertEqual(result["number"], NUMBER)
        self.assertTrue(result["route_verified"])
        self.assertFalse(any(r.method == "POST" for r in fake.requests))

    def test_existing_different_number_cannot_be_replaced(self):
        fake = FakeTwilio([record(number=OTHER)])
        with self.assertRaises(HTTPException) as error:
            self.provider(fake).purchase_approved_number(SHOP, NUMBER, approved=True)
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(any(r.method == "POST" for r in fake.requests))

    def test_wrong_webhook_is_not_claimed_as_ready(self):
        fake = FakeTwilio([record(voice_url="https://different.example.test/voice")])
        with self.assertRaises(HTTPException) as error:
            self.provider(fake).find_existing(SHOP)
        self.assertEqual(error.exception.status_code, 409)

    def test_voice_app_override_is_not_claimed_as_ready(self):
        fake = FakeTwilio([record(voice_application_sid="AP" + "f" * 32)])
        with self.assertRaises(HTTPException):
            self.provider(fake).find_existing(SHOP)

    def test_different_account_cannot_be_claimed(self):
        fake = FakeTwilio([record(account_sid="AC" + "f" * 32)])
        with self.assertRaises(HTTPException):
            self.provider(fake).find_existing(SHOP)

    def test_approved_purchase_read_after_write(self):
        fake = FakeTwilio()
        result = self.provider(fake).purchase_approved_number(
            SHOP, NUMBER, approved=True)
        self.assertEqual(result["number"], NUMBER)
        self.assertTrue(result["route_verified"])
        self.assertEqual(len([r for r in fake.requests if r.method == "POST"]), 1)
        self.assertEqual(len([r for r in fake.requests if r.method == "GET"]), 4)

    def test_lost_purchase_response_recovers_without_second_charge(self):
        fake = FakeTwilio(fail_after_purchase=True)
        result = self.provider(fake).purchase_approved_number(
            SHOP, NUMBER, approved=True)
        self.assertEqual(result["number"], NUMBER)
        self.assertEqual(len([r for r in fake.requests if r.method == "POST"]), 1)

    def test_lost_request_without_inventory_confirmation_stops(self):
        fake = FakeTwilio(fail_before_purchase=True)
        with self.assertRaises(HTTPException) as error:
            self.provider(fake).purchase_approved_number(
                SHOP, NUMBER, approved=True)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(len([r for r in fake.requests if r.method == "POST"]), 1)

    def test_foreign_owned_number_is_not_repurposed(self):
        fake = FakeTwilio([record(shop="another-shop")])
        with self.assertRaises(HTTPException) as error:
            self.provider(fake).purchase_approved_number(
                SHOP, NUMBER, approved=True)
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(any(r.method == "POST" for r in fake.requests))

    def test_ambiguous_shop_label_stops(self):
        fake = FakeTwilio([record(), record(number=OTHER)])
        with self.assertRaises(HTTPException) as error:
            self.provider(fake).find_existing(SHOP)
        self.assertEqual(error.exception.status_code, 409)

    def test_invalid_phone_rejected_before_provider_calls(self):
        fake = FakeTwilio()
        with self.assertRaises(HTTPException) as error:
            self.provider(fake).purchase_approved_number(
                SHOP, "240-555-0123", approved=True)
        self.assertEqual(error.exception.status_code, 422)
        self.assertFalse(fake.requests)

    def test_missing_credentials_fail_closed(self):
        with patch.dict(os.environ, {"DAYTELLO_VOICE_RELAY_API_KEY_SECRET": ""}):
            with self.assertRaises(HTTPException) as error:
                VoiceRelayNumberProvider()
        self.assertEqual(error.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
