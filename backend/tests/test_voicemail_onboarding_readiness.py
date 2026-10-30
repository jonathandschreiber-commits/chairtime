"""Guardrails for new shop voicemail onboarding status (offline)."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.routes.voicemail_contact_number import voicemail_onboarding_readiness


def shop():
    return SimpleNamespace(
        id="shop-3", slug="test-salon-3", ai_voice_enabled=True,
        highlevel_agent_id="agent-3", highlevel_location_id="test-location",
    )


def owner():
    return SimpleNamespace(shop_id="shop-3")


class FakeQuery:
    def filter(self, *args):
        return self
    def one_or_none(self):
        return shop()


class FakeDB:
    def __init__(self, settings):
        self.settings = settings
    def query(self, *_args):
        return FakeQuery()
    def get(self, *_args):
        return self.settings


class ReadinessTests(unittest.TestCase):
    def test_unconfigured_shop_not_ready(self):
        with patch("app.routes.voicemail_contact_number.require_owner_for_shop", return_value="test-salon-3"):
            with patch.dict(os.environ, {"HIGHLEVEL_LOCATION_ID": "test-location",
                                         "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true"}):
                result = voicemail_onboarding_readiness("test-salon-3", FakeDB(None), owner())
        self.assertFalse(result["ready_for_customer_calls"])
        self.assertFalse(result["voicemail_number_assigned"])
        self.assertTrue(result["requires_manual_provider_setup"])

    def test_sms_active_does_not_prove_forwarding(self):
        settings = SimpleNamespace(
            receiving_number="+12025550188", location_id="test-location",
            owner_phone="+12025550199", notifications_enabled=True
        )
        with patch("app.routes.voicemail_contact_number.require_owner_for_shop", return_value="test-salon-3"):
            with patch.dict(os.environ, {"HIGHLEVEL_LOCATION_ID": "test-location",
                                         "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true"}):
                result = voicemail_onboarding_readiness("test-salon-3", FakeDB(settings), owner())
        self.assertTrue(result["sms_activated"])
        self.assertFalse(result["ready_for_customer_calls"])
        self.assertFalse(result["forwarding_to_owner_verified"])


    def test_malformed_assigned_did_does_not_activate_sms(self):
        settings = SimpleNamespace(
            receiving_number="not-a-phone-number", location_id="test-location",
            owner_phone="+12025550199", notifications_enabled=True,
        )
        with patch("app.routes.voicemail_contact_number.require_owner_for_shop", return_value="test-salon-3"):
            with patch.dict(os.environ, {"HIGHLEVEL_LOCATION_ID": "test-location",
                                         "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true"}):
                result = voicemail_onboarding_readiness("test-salon-3", FakeDB(settings), owner())
        self.assertFalse(result["voicemail_number_assigned"])
        self.assertFalse(result["sms_activated"])
        self.assertFalse(result["ready_for_customer_calls"])

    def test_malformed_saved_owner_phone_does_not_activate_sms(self):
        settings = SimpleNamespace(
            receiving_number="+12025550188", location_id="test-location",
            owner_phone="202-555-0199", notifications_enabled=True,
        )
        with patch("app.routes.voicemail_contact_number.require_owner_for_shop", return_value="test-salon-3"):
            with patch.dict(os.environ, {"HIGHLEVEL_LOCATION_ID": "test-location",
                                         "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true"}):
                result = voicemail_onboarding_readiness("test-salon-3", FakeDB(settings), owner())
        self.assertTrue(result["voicemail_number_assigned"])
        self.assertFalse(result["owner_number_saved"])
        self.assertFalse(result["sms_activated"])
        self.assertFalse(result["ready_for_customer_calls"])

    def test_mismatched_location_never_reports_number_assigned(self):
        settings = SimpleNamespace(
            receiving_number="+12025550188", location_id="another-location",
            owner_phone="+12025550199", notifications_enabled=True,
        )
        with patch("app.routes.voicemail_contact_number.require_owner_for_shop", return_value="test-salon-3"):
            with patch.dict(os.environ, {"HIGHLEVEL_LOCATION_ID": "test-location",
                                         "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true"}):
                result = voicemail_onboarding_readiness("test-salon-3", FakeDB(settings), owner())
        self.assertFalse(result["voicemail_number_assigned"])
        self.assertFalse(result["sms_activated"])
        self.assertFalse(result["ready_for_customer_calls"])


if __name__ == "__main__":
    unittest.main()
