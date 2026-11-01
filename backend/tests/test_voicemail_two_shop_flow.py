"""Two-shop signed webhook -> SMS routing integration, with no outside traffic.

Both shops share a HighLevel location as in the isolated test environment,
but may never share a voicemail receiving number or notification recipient.
"""
import base64
import json
import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Shop
from app.routes import voicemail_owner_alert, voicemail_webhook
from app.voicemail_models import DayTelloVoicemailEvent, DayTelloVoicemailShopSettings


class SignedTwoShopFlowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.factory() as db:
            db.add_all([
                Shop(id="shop-a", slug="shop-a", name="Shop A",
                     ai_voice_enabled=True, highlevel_location_id="loc-a"),
                Shop(id="shop-b", slug="shop-b", name="Shop B",
                     ai_voice_enabled=True, highlevel_location_id="loc-a"),
                DayTelloVoicemailShopSettings(
                    shop_id="shop-a", location_id="loc-a",
                    receiving_number="+12025550121", owner_phone="+12025550191",
                    notifications_enabled=True,
                ),
                DayTelloVoicemailShopSettings(
                    shop_id="shop-b", location_id="loc-a",
                    receiving_number="+12025550122", owner_phone="+12025550192",
                    notifications_enabled=True,
                ),
            ])
            db.commit()
        self.key = Ed25519PrivateKey.generate()
        pem = self.key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true",
            "DAYTELLO_VOICEMAIL_TEST_RECIPIENT_MAP":
                '{"shop-a":"+12025550191","shop-b":"+12025550192"}',
            "DAYTELLO_VOICEMAIL_NUMBER_SHOP_MAP": "",
            "DAYTELLO_VOICEMAIL_LINK_KEY": Fernet.generate_key().decode("ascii"),
            "DAYTELLO_VOICEMAIL_TEST_PUBLIC_ORIGIN":
                "https://daytello-voicemail-test.example.org",
            "HIGHLEVEL_LOCATION_ID": "loc-a",
            "HIGHLEVEL_SMS_FROM_NUMBER": "+12025550199",
        })
        self.env.start()
        self.signing = patch.object(
            voicemail_webhook, "GHL_WEBHOOK_ED25519_PUBLIC_KEY", pem
        )
        self.signing.start()
        self.dbpatch = patch.object(voicemail_owner_alert, "SessionLocal", self.factory)
        self.dbpatch.start()
        self.sent = []
        def record_send(recipient, body, **kwargs):
            self.sent.append((recipient, body, kwargs))
            return {"success": True}
        self.sms = patch.object(
            voicemail_owner_alert, "send_highlevel_sms", side_effect=record_send
        )
        self.sms.start()
        app = FastAPI()
        app.include_router(voicemail_webhook.router, prefix="/api")
        def override():
            with self.factory() as db:
                yield db
        app.dependency_overrides[get_db] = override
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.sms.stop()
        self.dbpatch.stop()
        self.signing.stop()
        self.env.stop()
        self.engine.dispose()

    def post(self, number, message_id, location="loc-a"):
        payload = {
            "type": "InboundMessage", "direction": "inbound",
            "messageType": "CALL", "messageTypeString": "TYPE_CALL",
            "status": "voicemail", "locationId": location,
            "messageId": message_id, "to": number, "from": "+12025550150",
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = base64.b64encode(self.key.sign(body)).decode("ascii")
        return self.client.post(
            "/api/daytello/voicemail", content=body,
            headers={"X-GHL-Signature": signature, "Content-Type": "application/json"},
        )

    def test_two_shops_never_cross_deliver_and_duplicates_do_not_repeat_sms(self):
        first = self.post("+12025550121", "message-a")
        second = self.post("+12025550122", "message-b")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["action"], "queued_owner_notification")
        self.assertEqual(second.json()["action"], "queued_owner_notification")
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self.sent[0][0], "+12025550191")
        self.assertEqual(self.sent[1][0], "+12025550192")
        self.assertIn("Shop A", self.sent[0][1])
        self.assertNotIn("Shop B", self.sent[0][1])
        self.assertIn("Shop B", self.sent[1][1])
        self.assertNotIn("Shop A", self.sent[1][1])
        self.assertEqual(self.sent[0][2]["shop_id"], "shop-a")
        self.assertEqual(self.sent[1][2]["shop_id"], "shop-b")
        with self.factory() as db:
            events = db.query(DayTelloVoicemailEvent).all()
            self.assertEqual(len(events), 2)
            self.assertEqual({e.notification_status for e in events}, {"sent"})
            numbers = {e.shop_id: e.receiving_number for e in events}
            self.assertEqual(numbers, {
                "shop-a": "+12025550121", "shop-b": "+12025550122"
            })

        again = self.post("+12025550121", "message-a")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["action"], "duplicate")
        self.assertEqual(len(self.sent), 2)

    def test_owner_opt_out_does_not_fall_back_to_other_shop_number(self):
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "shop-b")
            prefs.notifications_enabled = False
            db.commit()
        response = self.post("+12025550122", "message-b-disabled")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "recorded_no_notification")
        self.assertEqual(self.sent, [])
        with self.factory() as db:
            event = db.get(DayTelloVoicemailEvent, ("loc-a", "message-b-disabled"))
            self.assertEqual(event.shop_id, "shop-b")
            self.assertEqual(event.notification_status, "disabled")

    def test_other_location_and_unmapped_numbers_cannot_deliver(self):
        elsewhere = self.post("+12025550121", "foreign-location", location="other-loc")
        # Signed unknown events may consult HighLevel inventory to find an
        # explicitly labeled test number. Supply an empty provider inventory
        # instead of making a network call during the offline test.
        from app import voicemail_auto_provision
        with patch.object(voicemail_auto_provision, "get_location_phone_numbers",
                          return_value=({}, [])):
            unknown = self.post("+12025550123", "unmapped-number")
        self.assertEqual(elsewhere.json()["action"], "ignored_other_location")
        # No legacy map was set; unknown incoming numbers fail closed, 503.
        self.assertEqual(unknown.status_code, 503)
        self.assertEqual(self.sent, [])
        with self.factory() as db:
            self.assertEqual(db.query(DayTelloVoicemailEvent).count(), 0)

    def test_approval_change_rejects_second_shop_recipient(self):
        os.environ["DAYTELLO_VOICEMAIL_TEST_RECIPIENT_MAP"] = (
            '{"shop-a":"+12025550191","shop-b":"+12025550193"}'
        )
        response = self.post("+12025550122", "not-allowed")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.sent, [])
        with self.factory() as db:
            self.assertEqual(db.query(DayTelloVoicemailEvent).count(), 0)


if __name__ == "__main__":
    unittest.main()
