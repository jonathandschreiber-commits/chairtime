"""Offline HTTP and owner delivery tests for DayTello's test voicemail link.

No HighLevel calls or SMS are sent. These protect shop isolation and verify
an actual audio response, not just token creation.
"""
import json
import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Shop
from app.routes import voicemail_owner_alert as owner
from app.voicemail_models import DayTelloVoicemailEvent
from app.voicemail_owner_links import make_recording_link


class AudioStream:
    status_code = 200
    headers = {"content-type": "audio/x-wav"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def aiter_bytes(self):
        yield b"RIFF-test-wave-audio"


class FakeHighLevelClient:
    def __init__(self, *args, **kwargs):
        self.called = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def stream(self, method, url, headers):
        assert method == "GET"
        assert url == ("https://services.leadconnectorhq.com/conversations/"
                       "messages/message-1/locations/test-location/recording")
        assert headers["Authorization"] == "Bearer test-token"
        return AudioStream()


class OwnerDeliveryRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            db.add(Shop(
                id="stan-1", slug="stan-s-shop", name="Stan's Shop",
                ai_voice_enabled=True, highlevel_location_id="test-location",
            ))
            db.add(DayTelloVoicemailEvent(
                location_id="test-location", message_id="message-1",
                shop_id="stan-1", receiving_number="+12025550123",
                notification_status="queued",
            ))
            db.commit()
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true",
            "DAYTELLO_VOICEMAIL_LINK_KEY": Fernet.generate_key().decode("ascii"),
            "DAYTELLO_VOICEMAIL_OWNER_PHONE_MAP":
                json.dumps({"stan-s-shop": "+12025550129"}),
            "DAYTELLO_VOICEMAIL_TEST_RECIPIENT": "+12025550129",
            "HIGHLEVEL_LOCATION_ID": "test-location",
            "HIGHLEVEL_API_TOKEN": "test-token",
        })
        self.env.start()
        self.dbpatch = patch.object(owner, "SessionLocal", self.factory)
        self.dbpatch.start()
        app = FastAPI()
        app.include_router(owner.router, prefix="/api")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.dbpatch.stop()
        self.env.stop()
        self.engine.dispose()

    def path(self, shop_id="stan-1"):
        return make_recording_link(
            "test-location", "message-1", shop_id
        ).replace(owner.__name__, owner.__name__).split(
            "chairtime-production-94da.up.railway.app"
        )[-1]

    def test_listening_returns_provider_audio_without_exposing_token(self):
        with patch.object(owner.httpx, "AsyncClient", FakeHighLevelClient):
            response = self.client.get(self.path())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"RIFF-test-wave-audio")
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertEqual(response.headers["content-type"], "audio/x-wav")
        self.assertNotIn(b"test-token", response.content)

    def test_wrong_shop_cannot_listen(self):
        with patch.object(
            owner.httpx, "AsyncClient",
            side_effect=AssertionError("Wrong-shop link must not call HighLevel"),
        ) as client:
            response = self.client.get(self.path("another-shop"))
        self.assertEqual(response.status_code, 404)
        client.assert_not_called()

    def test_disabled_mode_rejects_recording_links(self):
        os.environ["DAYTELLO_VOICEMAIL_TEST_ONLY"] = "false"
        response = self.client.get(self.path())
        self.assertEqual(response.status_code, 404)

    def test_owner_sms_has_correct_recipient_and_only_link(self):
        with patch.object(owner, "send_highlevel_sms", return_value={
            "success": True
        }) as send:
            owner.send_owner_voicemail_alert(
                "test-location", "message-1", "stan-s-shop",
                "Stan's Shop", "stan-1", "+14102088338",
            )
        send.assert_called_once()
        args, kwargs = send.call_args
        self.assertEqual(args[0], "+12025550129")
        self.assertIn("Stan's Shop", args[1])
        self.assertIn("Listen: https://", args[1])
        self.assertEqual(kwargs["shop_id"], "stan-1")
        with self.factory() as db:
            event = db.get(DayTelloVoicemailEvent, ("test-location", "message-1"))
            self.assertEqual(event.notification_status, "sent")


if __name__ == "__main__":
    unittest.main()
