"""Test-only owner-scoped adoption of an already purchased Twilio reserve DID."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.routes.voicemail_contact_number import claim_test_shop3_preowned_relay

NUMBER = "+15077135447"


class TestShop3ReserveClaim(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICE_RELAY_TEST_ONLY": "true",
            "DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED": "true",
        })
        self.env.start()
        self.db = object()
        self.user = object()

    def tearDown(self):
        self.env.stop()

    def test_claim_only_preowned_number_without_purchase_or_call_activation(self):
        expected = {
            "shop_slug": "test-shop-3", "relay_number": NUMBER,
            "enabled_for_calls": False, "provider_route_verified": True,
        }
        shop = SimpleNamespace(slug="test-shop-3")
        with patch("app.routes.voicemail_contact_number.owner_shop", return_value=shop), \
             patch("app.routes.voicemail_contact_number.reserve_or_purchase_relay_for_shop", return_value=expected) as claim:
            result = claim_test_shop3_preowned_relay(
                "test-shop-3", db=self.db, current_user=self.user)
        self.assertEqual(result["relay_number"], NUMBER)
        self.assertFalse(result["ready_for_customer_calls"])
        claim.assert_called_once_with(shop, self.db, NUMBER, approved=False)

    def test_other_shops_blocked_before_provider_operations(self):
        with patch("app.routes.voicemail_contact_number.owner_shop", return_value=SimpleNamespace(slug="shop-b")), \
             patch("app.routes.voicemail_contact_number.reserve_or_purchase_relay_for_shop") as claim:
            with self.assertRaises(HTTPException) as error:
                claim_test_shop3_preowned_relay("shop-b", db=self.db, current_user=self.user)
            self.assertEqual(error.exception.status_code, 404)
            claim.assert_not_called()

    def test_test_mode_required(self):
        with patch.dict(os.environ, {"DAYTELLO_VOICE_RELAY_TEST_ONLY": "false"}), \
             patch("app.routes.voicemail_contact_number.owner_shop", return_value=SimpleNamespace(slug="test-shop-3")), \
             patch("app.routes.voicemail_contact_number.reserve_or_purchase_relay_for_shop") as claim:
            with self.assertRaises(HTTPException) as error:
                claim_test_shop3_preowned_relay("test-shop-3", db=self.db, current_user=self.user)
            self.assertEqual(error.exception.status_code, 404)
            claim.assert_not_called()


if __name__ == "__main__":
    unittest.main()
