"""Offline fail-closed tests for the DayTello OAuth installation controls."""
import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.routes import daytello_voicemail_oauth as oauth


class OAuthConfigurationTests(unittest.TestCase):
    def valid_env(self):
        return {
            "DAYTELLO_VOICEMAIL_OAUTH_ENABLED": "true",
            "DAYTELLO_GHL_OAUTH_REDIRECT_URI": oauth.TEST_REDIRECT_URI,
            "DAYTELLO_GHL_CLIENT_ID": "test-client",
            "DAYTELLO_GHL_CLIENT_SECRET": "test-secret",
            "HIGHLEVEL_LOCATION_ID": "test-location",
            "DAYTELLO_OAUTH_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
        }

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {"DAYTELLO_VOICEMAIL_OAUTH_ENABLED": "false"}):
            with self.assertRaises(HTTPException) as e:
                oauth.config()
            self.assertEqual(e.exception.status_code, 503)

    def test_configured_test_only(self):
        with patch.dict(os.environ, self.valid_env()):
            client_id, secret, location, cipher = oauth.config()
            self.assertEqual((client_id, secret, location), ("test-client", "test-secret", "test-location"))
            self.assertEqual(cipher.decrypt(cipher.encrypt(b"sample")), b"sample")

    def test_rejects_wrong_callback(self):
        env = self.valid_env()
        env["DAYTELLO_GHL_OAUTH_REDIRECT_URI"] = "https://example.com/api/daytello/oauth/callback"
        with patch.dict(os.environ, env):
            with self.assertRaises(HTTPException):
                oauth.config()

    def test_rejects_missing_secret(self):
        env = self.valid_env()
        env["DAYTELLO_GHL_CLIENT_SECRET"] = ""
        with patch.dict(os.environ, env):
            with self.assertRaises(HTTPException):
                oauth.config()

    def test_rejects_bad_encryption_key(self):
        env = self.valid_env()
        env["DAYTELLO_OAUTH_ENCRYPTION_KEY"] = "not-a-valid-Fernet-key"
        with patch.dict(os.environ, env):
            with self.assertRaises(HTTPException):
                oauth.config()

    def test_non_admin_forbidden(self):
        class User:
            is_active = True
            email = "test@example.com"
        with patch.dict(os.environ, {"PLATFORM_ADMIN_EMAILS": "admin@example.com"}):
            with self.assertRaises(HTTPException) as e:
                oauth.ensure_test_admin(User())
            self.assertEqual(e.exception.status_code, 403)

    def test_error_page_does_not_echo_secrets(self):
        page = oauth.message_page("Authorization was not completed.", 400)
        self.assertNotIn("token", page.body.decode("utf-8"))
        self.assertEqual(page.status_code, 400)


if __name__ == "__main__":
    unittest.main()
