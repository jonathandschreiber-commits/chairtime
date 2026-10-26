"""Offline OAuth callback integration tests. No real HighLevel request is sent."""
import asyncio
import hashlib
import os
import unittest
from datetime import timedelta
from unittest.mock import patch

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.routes import daytello_voicemail_oauth as oauth
from app.voicemail_oauth_models import DayTelloOAuthState, DayTelloOAuthInstallation


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, response, recorder):
        self.response = response
        self.recorder = recorder
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    async def post(self, url, headers, data):
        self.recorder.append((url, data))
        return self.response


class CallbackTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine)
        self.key = Fernet.generate_key().decode("ascii")
        self.environ = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_OAUTH_ENABLED": "true",
            "DAYTELLO_GHL_OAUTH_REDIRECT_URI": oauth.TEST_REDIRECT_URI,
            "DAYTELLO_GHL_CLIENT_ID": "mock-test-client",
            "DAYTELLO_GHL_CLIENT_SECRET": "mock-secret",
            "HIGHLEVEL_LOCATION_ID": "only-approved-test-location",
            "DAYTELLO_OAUTH_ENCRYPTION_KEY": self.key,
        })
        self.environ.start()
        self.state = "an-opaque-one-time-nonce"
        self.digest = hashlib.sha256(self.state.encode("utf-8")).hexdigest()
        with self.sessions() as db:
            db.add(DayTelloOAuthState(
                state_digest=self.digest,
                initiated_by_user_id="test-admin",
                expires_at=oauth.utc_now_naive() + timedelta(minutes=5),
            ))
            db.commit()

    def tearDown(self):
        self.environ.stop()
        self.engine.dispose()

    def response_payload(self, **changes):
        data = {
            "access_token": "synthetic-access",
            "refresh_token": "synthetic-refresh",
            "expires_in": 3600,
            "scope": oauth.REQUIRED_SCOPE,
            "userType": "Location",
            "locationId": "only-approved-test-location",
        }
        data.update(changes)
        return data

    def call_with(self, payload):
        posts = []
        def fake_client_factory(**kwargs):
            return FakeClient(FakeResponse(200, payload), posts)
        with patch.object(oauth.httpx, "AsyncClient", fake_client_factory):
            with self.sessions() as db:
                page = asyncio.run(oauth.oauth_callback(
                    code="mock-highlevel-code", state=self.state, error=None, db=db
                ))
        return page, posts

    def test_correct_location_stores_encrypted_tokens(self):
        page, posts = self.call_with(self.response_payload())
        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][0], oauth.TOKEN_URL)
        self.assertEqual(posts[0][1]["redirect_uri"], oauth.TEST_REDIRECT_URI)
        with self.sessions() as db:
            installation = db.get(
                DayTelloOAuthInstallation, "only-approved-test-location"
            )
            self.assertIsNotNone(installation)
            self.assertNotIn("synthetic-access", installation.encrypted_access_token)
            self.assertNotIn("synthetic-refresh", installation.encrypted_refresh_token)
            cipher = Fernet(self.key.encode("ascii"))
            self.assertEqual(
                cipher.decrypt(installation.encrypted_access_token.encode("ascii")),
                b"synthetic-access",
            )

    def test_other_location_refused_without_storage(self):
        page, posts = self.call_with(
            self.response_payload(locationId="another-customer-location")
        )
        self.assertEqual(page.status_code, 403)
        with self.sessions() as db:
            self.assertEqual(db.query(DayTelloOAuthInstallation).count(), 0)

    def test_company_token_refused_without_storage(self):
        page, posts = self.call_with(
            self.response_payload(userType="Company")
        )
        self.assertEqual(page.status_code, 403)
        with self.sessions() as db:
            self.assertEqual(db.query(DayTelloOAuthInstallation).count(), 0)

    def test_missing_scope_refused_without_storage(self):
        page, posts = self.call_with(
            self.response_payload(scope="contacts.readonly")
        )
        self.assertEqual(page.status_code, 403)
        with self.sessions() as db:
            self.assertEqual(db.query(DayTelloOAuthInstallation).count(), 0)

    def test_reused_state_refused_without_new_exchange(self):
        self.assertEqual(self.call_with(self.response_payload())[0].status_code, 200)
        page, posts = self.call_with(self.response_payload())
        self.assertEqual(page.status_code, 400)
        self.assertEqual(posts, [])

    def test_expired_state_refused(self):
        with self.sessions() as db:
            state = db.get(DayTelloOAuthState, self.digest)
            state.expires_at = oauth.utc_now_naive() - timedelta(seconds=1)
            db.commit()
        page, posts = self.call_with(self.response_payload())
        self.assertEqual(page.status_code, 400)
        self.assertEqual(posts, [])


if __name__ == "__main__":
    unittest.main()
