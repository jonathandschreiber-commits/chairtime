"""Read-only Twilio connectivity probe: no number purchases or route changes."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.routes import voicemail_contact_number as mod


class TwilioConnectivityCheckTests(unittest.TestCase):
    def setUp(self):
        self.shop = SimpleNamespace(slug="test-shop-3")
        self.owner = SimpleNamespace()
        self.db = object()

    def call(self):
        return mod.voice_relay_provider_connectivity(
            "test-shop-3", db=self.db, current_user=self.owner
        )

    def test_authorized_trial_with_empty_inventory_is_connected_not_ready(self):
        with patch.object(mod, "owner_shop", return_value=self.shop), \
             patch.dict("os.environ", {
                 "DAYTELLO_VOICE_RELAY_TEST_ONLY": "true",
                 "DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED": "true",
             }), \
             patch.object(mod, "VoiceRelayNumberProvider") as provider:
            provider.return_value._list.return_value = []
            result = self.call()
            self.assertEqual(result["assigned_number_count"], 0)
            self.assertTrue(result["connected"])
            self.assertFalse(result["live_relay_verified"])
            self.assertFalse(result["ready_for_customer_calls"])
            provider.return_value._list.assert_called_once_with()

    def test_disabled_test_gate_never_contacts_twilio(self):
        with patch.object(mod, "owner_shop", return_value=self.shop), \
             patch.dict("os.environ", {
                 "DAYTELLO_VOICE_RELAY_TEST_ONLY": "false",
                 "DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED": "true",
             }), \
             patch.object(mod, "VoiceRelayNumberProvider") as provider:
            with self.assertRaises(HTTPException) as exc:
                self.call()
            self.assertEqual(exc.exception.status_code, 404)
            provider.assert_not_called()

    def test_owner_check_precedes_provider_access(self):
        with patch.object(mod, "owner_shop", side_effect=HTTPException(403, "Denied")), \
             patch.object(mod, "VoiceRelayNumberProvider") as provider:
            with self.assertRaises(HTTPException) as exc:
                self.call()
            self.assertEqual(exc.exception.status_code, 403)
            provider.assert_not_called()

    def test_provider_failure_never_leaks_details(self):
        with patch.object(mod, "owner_shop", return_value=self.shop), \
             patch.dict("os.environ", {
                 "DAYTELLO_VOICE_RELAY_TEST_ONLY": "true",
                 "DAYTELLO_SHOP3_SANDBOX_TRIAL_ENABLED": "true",
             }), \
             patch.object(mod, "VoiceRelayNumberProvider") as provider:
            provider.return_value._list.side_effect = HTTPException(
                401, "Credential-containing provider error"
            )
            with self.assertRaises(HTTPException) as exc:
                self.call()
            self.assertEqual(exc.exception.status_code, 502)
            self.assertNotIn("Credential-containing", exc.exception.detail)


if __name__ == "__main__":
    unittest.main()
