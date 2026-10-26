"""Offline unit tests for the token refresh response guard."""
import unittest
from app.daytello_oauth_tokens import valid_refresh_payload

class TokenRefreshResponseTests(unittest.TestCase):
    def valid(self):
        return {
            "locationId": "stan-test-location",
            "userType": "Location",
            "scope": "conversations/message.readonly",
            "access_token": "new-access",
            "refresh_token": "rotated-refresh",
            "expires_in": 3600,
        }

    def test_valid_refresh_response(self):
        self.assertTrue(valid_refresh_payload(self.valid(), "stan-test-location"))

    def test_missing_scope_accepted_when_unmodified(self):
        result = self.valid()
        result.pop("scope")
        self.assertTrue(valid_refresh_payload(result, "stan-test-location"))

    def test_wrong_location_rejected(self):
        self.assertFalse(valid_refresh_payload(self.valid(), "other-location"))

    def test_company_token_rejected(self):
        result = self.valid()
        result["userType"] = "Company"
        self.assertFalse(valid_refresh_payload(result, "stan-test-location"))

    def test_missing_refresh_token_rejected(self):
        result = self.valid()
        result["refresh_token"] = ""
        self.assertFalse(valid_refresh_payload(result, "stan-test-location"))

    def test_missing_permission_rejected(self):
        result = self.valid()
        result["scope"] = "contacts.readonly"
        self.assertFalse(valid_refresh_payload(result, "stan-test-location"))

    def test_invalid_expiry_rejected(self):
        result = self.valid()
        result["expires_in"] = True
        self.assertFalse(valid_refresh_payload(result, "stan-test-location"))

if __name__ == "__main__":
    unittest.main()
