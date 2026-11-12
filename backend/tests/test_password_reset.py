import os
import re
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import User
from app.password_reset import PasswordReset
from app.routes.auth import hash_password, router


class PasswordResetTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)
        self.secret = "password-reset-test-only-secret-value"
        env = patch.dict(os.environ, JWT_SECRET=self.secret, RESEND_API_KEY="test", REDIS_URL="redis://test")
        env.start()
        self.addCleanup(env.stop)

        def test_db():
            with self.session() as db:
                yield db

        app = FastAPI()
        app.include_router(router, prefix="/api/auth")
        app.dependency_overrides[get_db] = test_db
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.sender = self.enterContext(patch("app.password_reset.httpx.post", return_value=httpx.Response(200)))
        self.enterContext(patch("app.password_reset.SessionLocal", self.session))
        self.enterContext(patch("app.routes.auth.allow_reset_request", return_value=True))

    def create_user(self, role="owner", active=True):
        email = f"{role}@example.test"
        with self.session.begin() as db:
            db.add(User(
                id=role, name=role, email=email, password_hash=hash_password("old-password"),
                role=role, is_active=active,
            ))
        return email

    def request_link(self, email):
        response = self.client.post("/api/auth/forgot-password", json={"email": email})
        self.assertEqual(response.status_code, 202)
        return response.json()

    def get_token(self):
        return re.search(r"#token=([\w-]+)", self.sender.call_args.kwargs["json"]["text"])[1]

    def reset(self, token):
        return self.client.post("/api/auth/reset-password", json={"token": token, "password": "new-password"})

    def login(self, email, password):
        return self.client.post("/api/auth/login", json={"email": email, "password": password})

    def me(self, token):
        return self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    def test_owner_and_staff_can_recover_once_and_old_sessions_expire(self):
        for role in ("owner", "staff"):
            with self.subTest(role=role):
                email = self.create_user(role)
                prior = self.login(email, "old-password").json()["access_token"]
                legacy = jwt.encode(
                    {"sub": role, "exp": datetime.now(timezone.utc) + timedelta(days=1)}, self.secret,
                    algorithm="HS256",
                )
                self.assertEqual(self.me(legacy).status_code, 200)
                self.request_link(email.upper())
                token = self.get_token()
                self.assertEqual(self.sender.call_args.kwargs["json"]["to"], [email])
                self.assertEqual(self.reset(token).status_code, 200)
                self.assertEqual(self.reset(token).status_code, 400)
                self.assertEqual(self.me(prior).status_code, 401)
                self.assertEqual(self.me(legacy).status_code, 401)
                self.assertEqual(self.login(email, "old-password").status_code, 401)
                new_session = self.login(email, "new-password").json()["access_token"]
                self.assertEqual(self.me(new_session).status_code, 200)

    def test_unknown_and_inactive_addresses_receive_same_response(self):
        inactive = self.create_user("staff", active=False)
        self.assertEqual(self.request_link(inactive), self.request_link("unknown@example.test"))
        self.sender.assert_not_called()

    def test_expired_and_replaced_links_cannot_change_password(self):
        email = self.create_user()
        self.request_link(email)
        first = self.get_token()
        self.request_link(email)
        second = self.get_token()
        self.assertEqual(self.reset(first).status_code, 400)
        with self.session.begin() as db:
            db.get(PasswordReset, "owner").expires_at = datetime(2000, 1, 1)
        self.assertEqual(self.reset(second).status_code, 400)
        self.assertEqual(self.login(email, "old-password").status_code, 200)

    def test_owner_managed_password_change_invalidates_an_outstanding_link(self):
        email = self.create_user("staff")
        self.request_link(email)
        token = self.get_token()
        with self.session.begin() as db:
            db.get(User, "staff").password_hash = hash_password("replacement-password")
        self.assertEqual(self.reset(token).status_code, 400)
        self.assertEqual(self.login(email, "replacement-password").status_code, 200)
