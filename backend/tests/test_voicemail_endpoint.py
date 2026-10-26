"""HTTP-level offline integration tests; no calls to HighLevel or Railway.

Run from backend/ with:
python -m unittest discover -s tests -p 'test_voicemail*.py' -v
"""

import base64
import json
import os
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Shop
from app.routes import voicemail_webhook
from app.voicemail_models import DayTelloVoicemailEvent


class VoicemailEndpointTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False
        )
        with self.session_factory() as session:
            session.add(Shop(
                id="shop-stan-test",
                slug="stan-s-shop",
                name="Stan's Shop",
                ai_voice_enabled=True,
                highlevel_location_id="test-hl-location",
            ))
            session.commit()

        app = FastAPI()
        app.include_router(voicemail_webhook.router, prefix="/api")

        def override_db():
            with self.session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.private_key = Ed25519PrivateKey.generate()
        public_key_pem = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        self.key_patch = patch.object(
            voicemail_webhook, "GHL_WEBHOOK_ED25519_PUBLIC_KEY", public_key_pem
        )
        self.key_patch.start()
        self.env_patch = patch.dict(
            os.environ,
            {
                "HIGHLEVEL_LOCATION_ID": "test-hl-location",
                "DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP":
                    '{"+12403875085":"stan-s-shop"}',
            },
        )
        self.env_patch.start()
        self.payload = {
            "type": "InboundMessage",
            "locationId": "test-hl-location",
            "direction": "inbound",
            "messageType": "CALL",
            "status": "voicemail",
            "messageId": "test-event-123",
            "to": "+12403875085",
            "from": "+14102088338",
            "messageTypeString": "TYPE_VOICEMAIL",
            "attachments": ["https://example.test/not-a-real-recording"],
        }

    def tearDown(self):
        self.client.close()
        self.env_patch.stop()
        self.key_patch.stop()
        self.engine.dispose()

    def post(self, payload=None, signature=True, body=None):
        if body is None:
            body = json.dumps(
                self.payload if payload is None else payload,
                separators=(",", ":"),
            ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if signature:
            headers["X-GHL-Signature"] = base64.b64encode(
                self.private_key.sign(body)
            ).decode("ascii")
        return self.client.post(
            "/api/daytello/voicemail", content=body, headers=headers
        )

    def count_events(self):
        with self.session_factory() as session:
            return session.query(DayTelloVoicemailEvent).count()

    def test_valid_event_recorded_without_notification(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "recorded_no_notification")
        self.assertEqual(self.count_events(), 1)
        with self.session_factory() as session:
            event = session.query(DayTelloVoicemailEvent).one()
            self.assertEqual(event.shop_id, "shop-stan-test")
            self.assertEqual(event.receiving_number, "+12403875085")
            self.assertEqual(event.notification_status, "disabled")

    def test_duplicate_event_records_only_once(self):
        self.assertEqual(self.post().status_code, 200)
        again = self.post()
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["action"], "duplicate")
        self.assertEqual(self.count_events(), 1)

    def test_unsigned_request_rejected(self):
        response = self.post(signature=False)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.count_events(), 0)

    def test_tampering_rejected(self):
        payload = dict(self.payload, to="+12403875086")
        body = json.dumps(self.payload).encode("utf-8")
        original_signature = base64.b64encode(
            self.private_key.sign(body)
        ).decode("ascii")
        changed_body = json.dumps(payload).encode("utf-8")
        result = self.client.post(
            "/api/daytello/voicemail",
            content=changed_body,
            headers={"X-GHL-Signature": original_signature},
        )
        self.assertEqual(result.status_code, 401)
        self.assertEqual(self.count_events(), 0)

    def test_unmapped_number_ignored(self):
        payload = dict(self.payload, to="+12403875086")
        response = self.post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "ignored_unmapped_number")
        self.assertEqual(self.count_events(), 0)

    def test_wrong_location_ignored(self):
        payload = dict(self.payload, locationId="a-different-location")
        response = self.post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "ignored_other_location")
        self.assertEqual(self.count_events(), 0)

    def test_sms_ignored(self):
        payload = dict(
            self.payload, messageType="SMS",
            messageTypeString="TYPE_SMS", status="delivered"
        )
        response = self.post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "ignored_non_voicemail")
        self.assertEqual(self.count_events(), 0)

    def test_unknown_shop_ignored(self):
        os.environ["DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP"] = (
            '{"+12403875085":"missing-shop"}'
        )
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "ignored_inactive_shop")
        self.assertEqual(self.count_events(), 0)

    def test_disabled_shop_ignored(self):
        with self.session_factory() as session:
            shop = session.query(Shop).filter(Shop.id == "shop-stan-test").one()
            shop.ai_voice_enabled = False
            session.commit()
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "ignored_inactive_shop")
        self.assertEqual(self.count_events(), 0)

    def test_missing_configuration_fails_closed(self):
        os.environ["DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP"] = ""
        response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.count_events(), 0)


if __name__ == "__main__":
    unittest.main()
