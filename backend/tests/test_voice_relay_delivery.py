"""Offline signed Twilio callback -> durable recording -> owner SMS queue tests."""
import base64
import hashlib
import hmac
import os
import unittest
import httpx
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import Shop
from app.routes.voice_relay import router
from app.voice_relay_models import DayTelloVoiceRelayAssignment
from app.voice_relay_delivery import (
    DayTelloVoiceRelayCall, DayTelloVoiceRelayRecording,
    make_relay_recording_link, send_relay_owner_alert,
)
from app.voicemail_models import DayTelloVoicemailShopSettings
from app.voicemail_owner_links import decode_recording_link
from test_voice_relay_routes import FakeDB, DID, OWNER, CALL, ACCOUNT

RECORDING = "RE" + "b" * 32


class DeliveryDB(FakeDB):
    def __init__(self):
        # Signed delivery tests use a separate test location from the
        # general relay route tests. Keep the mocked shop and settings
        # consistent with the configured provider location.
        super().__init__(location_id="test-location", shop_location_id="test-location")
        self.recordings = {}
        self.pending = None
        self.notifications_enabled = True
        self.owner_phone = OWNER
        self.receiving_number = DID
        self.location_id = "test-location"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, model, identifier):
        if model is DayTelloVoiceRelayCall:
            return self.calls.get(identifier)
        if model is DayTelloVoiceRelayRecording:
            return self.recordings.get(identifier)
        if model is Shop:
            return SimpleNamespace(
                id=identifier, slug="test-shop-3", name="Test Shop 3",
                ai_voice_enabled=True, highlevel_location_id="test-location",
            )
        if model is DayTelloVoicemailShopSettings:
            return SimpleNamespace(
                owner_phone=self.owner_phone, notifications_enabled=self.notifications_enabled,
                receiving_number=self.receiving_number, location_id=self.location_id,
            )
        if model is DayTelloVoiceRelayAssignment:
            return SimpleNamespace(
                shop_id=identifier, relay_number=DID, enabled=True,
            )
        raise AssertionError(f"Unexpected model {model}")

    def query(self, model):
        if model is DayTelloVoiceRelayRecording:
            return RecordingClaimQuery(self)
        return super().query(model)

    def add(self, record):
        self.pending = record

    def commit(self):
        record = self.pending
        self.pending = None
        if record is None:
            return
        if isinstance(record, DayTelloVoiceRelayCall):
            if record.call_sid in self.calls:
                raise IntegrityError("insert", {}, Exception("duplicate call"))
            self.calls[record.call_sid] = record
        elif isinstance(record, DayTelloVoiceRelayRecording):
            if record.recording_sid in self.recordings:
                raise IntegrityError("insert", {}, Exception("duplicate recording"))
            self.recordings[record.recording_sid] = record
        else:
            raise AssertionError("Unexpected persisted record")

    def rollback(self):
        self.pending = None


class RecordingClaimQuery:
    """Simulate the database's conditional queued -> sending UPDATE."""

    def __init__(self, db):
        self.db = db
        self.filters = {}

    def filter_by(self, **kwargs):
        self.filters = kwargs
        return self

    def update(self, values, synchronize_session=False):
        assert synchronize_session is False
        receipt = self.db.recordings.get(self.filters["recording_sid"])
        if not receipt or receipt.notification_status != self.filters["notification_status"]:
            return 0
        receipt.notification_status = values["notification_status"]
        return 1


class SignedRecordingDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.db = DeliveryDB()
        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.notifications = []
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICE_RELAY_TEST_ONLY": "true",
            "DAYTELLO_VOICE_RELAY_AUTH_TOKEN": "test-only-secret",
            "DAYTELLO_VOICE_RELAY_ACCOUNT_SID": ACCOUNT,
            "DAYTELLO_VOICE_RELAY_PUBLIC_ORIGIN": "https://relay.example.test",
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true",
            "DAYTELLO_VOICEMAIL_TEST_RECIPIENT": OWNER,
            "DAYTELLO_VOICEMAIL_TEST_PUBLIC_ORIGIN": "https://relay.example.test",
            "DAYTELLO_VOICEMAIL_LINK_KEY": Fernet.generate_key().decode(),
            "HIGHLEVEL_LOCATION_ID": "test-location",
            "DAYTELLO_VOICE_RELAY_API_KEY_SID": "SK" + "e" * 32,
            "DAYTELLO_VOICE_RELAY_API_KEY_SECRET": "test-api-key-secret",
        })
        self.env.start()
        self.send = patch(
            "app.routes.voice_relay.send_relay_owner_alert",
            side_effect=self.notifications.append,
        )
        self.send.start()

    def tearDown(self):
        self.send.stop()
        self.env.stop()

    def post_signed(self, endpoint, fields):
        fields = {"AccountSid": ACCOUNT, "CallSid": CALL, **fields}
        signed_url = "https://relay.example.test" + endpoint
        data = signed_url + "".join(k + fields[k] for k in sorted(fields))
        signature = base64.b64encode(
            hmac.new(b"test-only-secret", data.encode(), hashlib.sha1).digest()
        ).decode()
        return self.client.post(endpoint, content=urlencode(fields), headers={
            "content-type": "application/x-www-form-urlencoded",
            "x-twilio-signature": signature,
        })

    def inbound(self):
        response = self.post_signed(
            "/api/daytello/voice-relay/inbound", {"To": DID})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(CALL, self.db.calls)

    def recording(self, **extra):
        return self.post_signed(
            "/api/daytello/voice-relay/record-ready",
            {"RecordingStatus": "completed", "RecordingSid": RECORDING, **extra},
        )

    def test_completed_recording_without_to_queues_exactly_one_sms(self):
        self.inbound()
        first = self.recording()
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["action"], "queued")
        self.assertEqual(self.notifications, [RECORDING])
        self.assertEqual(self.db.recordings[RECORDING].shop_id, "third-shop-id")
        second = self.recording()
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["action"], "duplicate")
        self.assertEqual(self.notifications, [RECORDING])

    def test_recording_without_signed_inbound_is_rejected(self):
        response = self.recording()
        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.notifications)

    def test_mismatched_destination_is_rejected(self):
        self.inbound()
        response = self.recording(To="+12405550198")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(self.notifications)

    def test_mismatched_provider_account_is_rejected(self):
        self.inbound()
        response = self.recording(AccountSid="AC" + "f" * 32)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.notifications)

    def test_sms_is_disabled_when_owner_has_not_opted_in(self):
        self.inbound()
        self.db.notifications_enabled = False
        response = self.recording()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["action"], "disabled")
        self.assertFalse(self.notifications)

    def test_owner_link_proxies_audio_with_server_side_provider_auth(self):
        self.inbound()
        self.assertEqual(self.recording().status_code, 200)
        link = make_relay_recording_link(self.db.recordings[RECORDING], OWNER)
        token = link.rsplit("/", 1)[1]
        requests = []
        def provider(request):
            requests.append(request)
            self.assertEqual(request.url.host, "api.twilio.com")
            self.assertIn("/Recordings/" + RECORDING + ".mp3", request.url.path)
            self.assertTrue(request.headers.get("authorization", "").startswith("Basic "))
            return httpx.Response(
                200, headers={"content-type": "audio/mpeg"}, content=b"mock-mp3"
            )
        real_async_client = httpx.AsyncClient
        def client_factory(**kwargs):
            return real_async_client(
                transport=httpx.MockTransport(provider), **kwargs,
            )
        with patch("app.voice_relay_delivery.SessionLocal", return_value=self.db), \
             patch("app.voice_relay_delivery.httpx.AsyncClient",
                   side_effect=client_factory):
            response = self.client.get(
                "/api/daytello/voice-relay/listen/" + token)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, b"mock-mp3")
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertEqual(len(requests), 1)

    def test_owner_link_rejects_unexpected_provider_content(self):
        self.inbound()
        self.assertEqual(self.recording().status_code, 200)
        token = make_relay_recording_link(
            self.db.recordings[RECORDING], OWNER).rsplit("/", 1)[1]
        real_async_client = httpx.AsyncClient
        def client_factory(**kwargs):
            return real_async_client(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(
                        200, headers={"content-type": "text/html"},
                        content=b"<html>not audio</html>",
                    )
                ), **kwargs,
            )
        with patch("app.voice_relay_delivery.SessionLocal", return_value=self.db), \
             patch("app.voice_relay_delivery.httpx.AsyncClient",
                   side_effect=client_factory):
            response = self.client.get(
                "/api/daytello/voice-relay/listen/" + token)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("not audio", response.text)

    def test_owner_opt_out_revokes_previously_issued_relay_link(self):
        self.inbound()
        self.assertEqual(self.recording().status_code, 200)
        token = make_relay_recording_link(
            self.db.recordings[RECORDING], OWNER).rsplit("/", 1)[1]
        self.db.notifications_enabled = False
        with patch("app.voice_relay_delivery.SessionLocal", return_value=self.db):
            response = self.client.get("/api/daytello/voice-relay/listen/" + token)
        self.assertEqual(response.status_code, 404)

    def test_owner_number_change_revokes_previously_issued_relay_link(self):
        self.inbound()
        self.assertEqual(self.recording().status_code, 200)
        token = make_relay_recording_link(
            self.db.recordings[RECORDING], OWNER).rsplit("/", 1)[1]
        # A separately approved new recipient must not inherit the old link.
        self.db.owner_phone = "+12405550177"
        with patch.dict(os.environ, {"DAYTELLO_VOICEMAIL_TEST_RECIPIENT": "+12405550177"}), \
             patch("app.voice_relay_delivery.SessionLocal", return_value=self.db):
            response = self.client.get("/api/daytello/voice-relay/listen/" + token)
        self.assertEqual(response.status_code, 404)

    def test_queued_sms_rechecks_current_did_and_location(self):
        # A recording can be queued before an owner changes routing. No SMS
        # should be sent against stale voicemail DID or location settings.
        for field, value in (
            ("receiving_number", "+12405550199"),
            ("location_id", "different-location"),
        ):
            with self.subTest(field=field):
                setattr(self.db, field, value)
                receipt = SimpleNamespace(
                    recording_sid=RECORDING, account_sid=ACCOUNT,
                    shop_id="third-shop-id", relay_number=DID,
                    notification_status="queued",
                )
                self.db.recordings[RECORDING] = receipt
                with patch("app.voice_relay_delivery.SessionLocal", return_value=self.db), \
                     patch("app.voice_relay_delivery.send_highlevel_sms") as send_sms:
                    send_relay_owner_alert(RECORDING)
                send_sms.assert_not_called()
                self.assertEqual(receipt.notification_status, "failed")
                setattr(self.db, field, DID if field == "receiving_number" else "test-location")

    def test_current_route_still_sends_one_queued_owner_sms(self):
        receipt = SimpleNamespace(
            recording_sid=RECORDING, account_sid=ACCOUNT,
            shop_id="third-shop-id", relay_number=DID,
            notification_status="queued",
        )
        self.db.recordings[RECORDING] = receipt
        with patch("app.voice_relay_delivery.SessionLocal", return_value=self.db), \
             patch("app.voice_relay_delivery.send_highlevel_sms",
                   return_value={"success": True}) as send_sms:
            send_relay_owner_alert(RECORDING)
        send_sms.assert_called_once()
        self.assertEqual(receipt.notification_status, "sent")

    def test_concurrent_owner_sms_attempt_is_claimed_once(self):
        receipt = SimpleNamespace(
            recording_sid=RECORDING, account_sid=ACCOUNT,
            shop_id="third-shop-id", relay_number=DID,
            notification_status="queued",
        )
        self.db.recordings[RECORDING] = receipt

        def send_with_reentrant_worker(*args, **kwargs):
            # Simulate a second worker processing the same queued recording
            # while the first worker is still waiting for the SMS provider.
            send_relay_owner_alert(RECORDING)
            return {"success": True}

        with patch("app.voice_relay_delivery.SessionLocal", return_value=self.db), \
             patch("app.voice_relay_delivery.send_highlevel_sms",
                   side_effect=send_with_reentrant_worker) as send_sms:
            send_relay_owner_alert(RECORDING)
        send_sms.assert_called_once()
        self.assertEqual(receipt.notification_status, "sent")

    def test_ambiguous_failed_owner_sms_is_not_retried(self):
        receipt = SimpleNamespace(
            recording_sid=RECORDING, account_sid=ACCOUNT,
            shop_id="third-shop-id", relay_number=DID,
            notification_status="queued",
        )
        self.db.recordings[RECORDING] = receipt
        with patch("app.voice_relay_delivery.SessionLocal", return_value=self.db), \
             patch("app.voice_relay_delivery.send_highlevel_sms",
                   return_value={"success": False}) as send_sms:
            send_relay_owner_alert(RECORDING)
            send_relay_owner_alert(RECORDING)
        send_sms.assert_called_once()
        self.assertEqual(receipt.notification_status, "failed")

    def test_in_progress_owner_sms_is_not_sent_again(self):
        receipt = SimpleNamespace(
            recording_sid=RECORDING, account_sid=ACCOUNT,
            shop_id="third-shop-id", relay_number=DID,
            notification_status="sending",
        )
        self.db.recordings[RECORDING] = receipt
        with patch("app.voice_relay_delivery.SessionLocal", return_value=self.db), \
             patch("app.voice_relay_delivery.send_highlevel_sms") as send_sms:
            send_relay_owner_alert(RECORDING)
        send_sms.assert_not_called()
        self.assertEqual(receipt.notification_status, "sending")

    def test_old_recording_link_revoked_on_did_or_location_change(self):
        self.inbound()
        self.assertEqual(self.recording().status_code, 200)
        token = make_relay_recording_link(
            self.db.recordings[RECORDING], OWNER).rsplit("/", 1)[1]
        for field, value in (
            ("receiving_number", "+12405550199"),
            ("location_id", "different-location"),
        ):
            with self.subTest(field=field):
                setattr(self.db, field, value)
                with patch("app.voice_relay_delivery.SessionLocal", return_value=self.db):
                    response = self.client.get(
                        "/api/daytello/voice-relay/listen/" + token)
                self.assertEqual(response.status_code, 404)
                setattr(self.db, field, DID if field == "receiving_number" else "test-location")

    def test_purpose_bound_recording_link(self):
        receipt = SimpleNamespace(
            account_sid=ACCOUNT, recording_sid=RECORDING,
            shop_id="third-shop-id",
        )
        link = make_relay_recording_link(receipt, OWNER)
        self.assertTrue(link.startswith(
            "https://relay.example.test/api/daytello/voice-relay/listen/"))
        token = link.rsplit("/", 1)[1]
        payload = decode_recording_link(token)
        self.assertEqual(payload["purpose"], "voice-relay")
        self.assertEqual(payload["message"], RECORDING)
        self.assertEqual(payload["shop"], "third-shop-id")


if __name__ == "__main__":
    unittest.main()
