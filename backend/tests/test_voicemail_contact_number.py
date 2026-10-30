"""Offline unified owner number API tests; no real calls or texts."""
import os
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Shop, User
from app.routes.auth import get_current_user
from app.routes import voicemail_contact_number as route
from app.voicemail_models import DayTelloVoicemailShopSettings
from app.voice_relay_models import DayTelloVoiceRelayAssignment


class UnifiedPhoneTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        with self.factory() as db:
            db.add_all([
                Shop(id="s1", slug="shop-a", name="Shop A", ai_voice_enabled=True,
                     highlevel_location_id="loc-test", highlevel_agent_id="test-agent-a"),
                Shop(id="s2", slug="shop-b", name="Shop B", ai_voice_enabled=True,
                     highlevel_location_id="loc-test", highlevel_agent_id="test-agent-b"),
                DayTelloVoicemailShopSettings(
                    shop_id="s1", location_id="loc-test",
                    receiving_number="+12025550123",
                    notifications_enabled=False,
                ),
            ])
            db.commit()
        self.user = User(
            id="u1", role="owner", shop_slug="shop-a", shop_id="s1",
            is_active=True, email="owner@example.test",
        )
        self.env = patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
            "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true",
            "DAYTELLO_VOICEMAIL_TEST_RECIPIENT": "+12025550199",
            "DAYTELLO_VOICEMAIL_LINK_KEY": Fernet.generate_key().decode(),
            "DAYTELLO_VOICEMAIL_TEST_PUBLIC_ORIGIN": "https://daytello-voicemail-test.example.org",
            "HIGHLEVEL_SMS_FROM_NUMBER": "+12025550124",
            "HIGHLEVEL_LOCATION_ID": "loc-test",
        })
        self.env.start()
        app = FastAPI()
        app.include_router(route.router, prefix="/api")
        def db_override():
            with self.factory() as db:
                yield db
        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)
        self.url = "/api/shops/shop-a/call-voicemail-number"

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.engine.dispose()

    def test_one_number_saved_after_verified_transfer(self):
        with patch.object(route, "daytello_save_staff_transfer", return_value={
            "enabled": True, "phone_number": "+12025550123",
        }) as provider:
            response = self.client.put(self.url, json={"phone_number": "+12025550199"})
        self.assertEqual(response.status_code, 200, response.text)
        provider.assert_called_once()
        self.assertEqual(
            provider.call_args.args[0].phone_number, "+12025550123",
            "AI must transfer to the dedicated HighLevel voicemail relay, "
            "not to the owner's personal carrier voicemail",
        )
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "s1")
            self.assertEqual(prefs.owner_phone, "+12025550199")
            self.assertTrue(prefs.notifications_enabled)

    def test_sms_enabled_without_claiming_external_forwarding(self):
        with patch.object(route, "daytello_save_staff_transfer", return_value={
            "enabled": True, "phone_number": "+12025550123",
        }):
            response = self.client.put(
                self.url, json={"phone_number": "+12025550199"}
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["sms_ready"])
        # SMS activation alone must never be exposed as customer-call readiness.
        self.assertFalse(response.json()["ready"])
        self.assertTrue(response.json()["settings_saved"])
        self.assertFalse(response.json()["forwarding_verified"])
        self.assertFalse(response.json()["setup_complete"])
        with self.factory() as db:
            record = db.get(DayTelloVoicemailShopSettings, "s1")
            self.assertEqual(record.owner_phone, "+12025550199")
            self.assertTrue(record.notifications_enabled)

    def test_saved_sms_flag_not_ready_when_global_delivery_is_disabled(self):
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "s1")
            prefs.owner_phone = "+12025550199"
            prefs.notifications_enabled = True
            db.commit()
        with patch.dict(os.environ, {"DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "false"}):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["notifications_enabled"])
        self.assertFalse(response.json()["sms_ready"])
        self.assertFalse(response.json()["ready"])

    def test_saved_sms_flag_not_ready_when_recipient_is_not_approved(self):
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "s1")
            prefs.owner_phone = "+12025550199"
            prefs.notifications_enabled = True
            db.commit()
        with patch.dict(os.environ, {
            "DAYTELLO_VOICEMAIL_TEST_RECIPIENT_MAP": "",
            "DAYTELLO_VOICEMAIL_TEST_RECIPIENT": "+12025550198",
        }):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["sms_ready"])

    def test_saved_sms_flag_not_ready_without_secure_link_configuration(self):
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "s1")
            prefs.owner_phone = "+12025550199"
            prefs.notifications_enabled = True
            db.commit()
        with patch.dict(os.environ, {"DAYTELLO_VOICEMAIL_LINK_KEY": ""}):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["sms_ready"])

    def test_saved_sms_flag_not_ready_with_invalid_voicemail_did(self):
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "s1")
            prefs.owner_phone = "+12025550199"
            prefs.receiving_number = "invalid-did"
            prefs.notifications_enabled = True
            db.commit()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["sms_ready"])

    def assert_internal_owner_number_rejected(self, number):
        os.environ["DAYTELLO_VOICEMAIL_TEST_RECIPIENT"] = number
        with patch.object(route, "daytello_save_staff_transfer") as transfer:
            result = self.client.put(self.url, json={"phone_number": number})
        self.assertEqual(result.status_code, 409, result.text)
        transfer.assert_not_called()
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "s1")
            self.assertIsNone(prefs.owner_phone)
            self.assertFalse(prefs.notifications_enabled)

    def test_owner_number_cannot_equal_own_voicemail_did(self):
        self.assert_internal_owner_number_rejected("+12025550123")

    def test_owner_number_cannot_be_another_shop_voicemail_did(self):
        with self.factory() as db:
            db.add(DayTelloVoicemailShopSettings(
                shop_id="s2", location_id="loc-test",
                receiving_number="+12025550198", notifications_enabled=False,
            ))
            db.commit()
        self.assert_internal_owner_number_rejected("+12025550198")

    def test_owner_number_cannot_be_an_ai_receptionist_did(self):
        with self.factory() as db:
            db.get(Shop, "s2").highlevel_phone_number = "+12025550198"
            db.commit()
        self.assert_internal_owner_number_rejected("+12025550198")

    def test_owner_number_cannot_be_another_shops_business_line(self):
        # A public business number may forward into another shop's AI agent
        # even when highlevel_phone_number is not populated.
        with self.factory() as db:
            db.get(Shop, "s2").phone = "+12025550198"
            db.commit()
        self.assert_internal_owner_number_rejected("+12025550198")

    def test_owner_number_cannot_be_own_published_business_line(self):
        # A shop's own public number may forward into its AI, causing a loop.
        with self.factory() as db:
            db.get(Shop, "s1").phone = "+12025550198"
            db.commit()
        self.assert_internal_owner_number_rejected("+12025550198")

    def test_test_activation_rejects_saved_own_business_line(self):
        with self.factory() as db:
            db.get(Shop, "s1").phone = "+12025550198"
            prefs = db.get(DayTelloVoicemailShopSettings, "s1")
            prefs.owner_phone = "+12025550198"
            db.commit()
        os.environ["DAYTELLO_VOICEMAIL_TEST_RECIPIENT"] = "+12025550198"
        result = self.client.post(
            "/api/shops/shop-a/voicemail-notifications/activate-test",
            json={"confirmed_live_call_test": True},
        )
        self.assertEqual(result.status_code, 409, result.text)
        with self.factory() as db:
            self.assertFalse(db.get(DayTelloVoicemailShopSettings, "s1").notifications_enabled)

    def test_test_activation_rejects_saved_cross_shop_business_line(self):
        with self.factory() as db:
            db.get(Shop, "s2").phone = "+12025550198"
            prefs = db.get(DayTelloVoicemailShopSettings, "s1")
            prefs.owner_phone = "+12025550198"
            db.commit()
        os.environ["DAYTELLO_VOICEMAIL_TEST_RECIPIENT"] = "+12025550198"
        result = self.client.post(
            "/api/shops/shop-a/voicemail-notifications/activate-test",
            json={"confirmed_live_call_test": True},
        )
        self.assertEqual(result.status_code, 409, result.text)
        with self.factory() as db:
            self.assertFalse(db.get(DayTelloVoicemailShopSettings, "s1").notifications_enabled)

    def test_owner_number_cannot_be_disabled_voice_relay_did(self):
        with self.factory() as db:
            db.add(DayTelloVoiceRelayAssignment(
                shop_id="s2", relay_number="+12025550198", enabled=False,
            ))
            db.commit()
        self.assert_internal_owner_number_rejected("+12025550198")

    def test_test_activation_rejects_previously_saved_internal_did(self):
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "s1")
            prefs.owner_phone = "+12025550123"
            db.commit()
        os.environ["DAYTELLO_VOICEMAIL_TEST_RECIPIENT"] = "+12025550123"
        response = self.client.post(
            "/api/shops/shop-a/voicemail-notifications/activate-test",
            json={"confirmed_live_call_test": True},
        )
        self.assertEqual(response.status_code, 409, response.text)
        with self.factory() as db:
            self.assertFalse(db.get(DayTelloVoicemailShopSettings, "s1").notifications_enabled)

    def test_failed_transfer_leaves_notification_unchanged(self):
        with patch.object(
            route, "daytello_save_staff_transfer",
            side_effect=HTTPException(502, "Provider unavailable"),
        ):
            response = self.client.put(self.url, json={"phone_number": "+12025550199"})
        self.assertEqual(response.status_code, 502)
        with self.factory() as db:
            self.assertIsNone(db.get(DayTelloVoicemailShopSettings, "s1").owner_phone)

    def test_another_shop_denied(self):
        response = self.client.get("/api/shops/shop-b/call-voicemail-number")
        self.assertEqual(response.status_code, 403)

    def test_invalid_and_unapproved_numbers_rejected(self):
        self.assertEqual(
            self.client.put(self.url, json={"phone_number": "1234"}).status_code, 422
        )
        self.assertEqual(
            self.client.put(self.url, json={"phone_number": "+12025550198"}).status_code, 503
        )

    def test_unconfigured_shop_is_provisioned_during_save(self):
        self.user.shop_slug = "shop-b"
        self.user.shop_id = "s2"
        with self.factory() as db:
            shop = db.get(Shop, "s2")
            shop.highlevel_location_id = "loc-test"
            db.commit()
        from app.voicemail_models import DayTelloVoicemailShopSettings
        from unittest.mock import patch
        def allocate(shop, db):
            binding = DayTelloVoicemailShopSettings(
                shop_id=shop.id, location_id="loc-test",
                receiving_number="+12025550130", notifications_enabled=False,
            )
            db.add(binding)
            db.commit()
            return binding
        with patch.object(route, "ensure_test_voicemail_number", side_effect=allocate), (
             patch.object(route, "daytello_save_staff_transfer",
                          return_value={"enabled": True, "phone_number": "+12025550130"})):
            response = self.client.put(
                "/api/shops/shop-b/call-voicemail-number",
                json={"phone_number": "+12025550199"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        with self.factory() as db:
            settings = db.get(DayTelloVoicemailShopSettings, "s2")
            self.assertTrue(settings.notifications_enabled)
            self.assertEqual(settings.owner_phone, "+12025550199")

    def test_second_shop_requires_its_own_approved_recipient(self):
        self.user.shop_slug = "shop-b"
        self.user.shop_id = "s2"
        os.environ["DAYTELLO_VOICEMAIL_TEST_RECIPIENT_MAP"] = (
            '{"shop-a":"+12025550199","shop-b":"+12025550198"}'
        )
        def allocate(shop, db):
            settings = DayTelloVoicemailShopSettings(
                shop_id=shop.id, location_id="loc-test",
                receiving_number="+12025550130",
                notifications_enabled=False,
            )
            db.add(settings)
            db.commit()
            return settings
        with patch.object(route, "ensure_test_voicemail_number", side_effect=allocate):
            response = self.client.put(
                "/api/shops/shop-b/call-voicemail-number",
                json={"phone_number": "+12025550199"},
            )
        self.assertEqual(response.status_code, 503)
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "s2")
            self.assertFalse(prefs.notifications_enabled)
            self.assertIsNone(prefs.owner_phone)

    def test_second_shop_approved_recipient_is_accepted(self):
        self.user.shop_slug = "shop-b"
        self.user.shop_id = "s2"
        os.environ["DAYTELLO_VOICEMAIL_TEST_RECIPIENT_MAP"] = (
            '{"shop-a":"+12025550199","shop-b":"+12025550198"}'
        )
        def allocate(shop, db):
            settings = DayTelloVoicemailShopSettings(
                shop_id=shop.id, location_id="loc-test",
                receiving_number="+12025550130",
                notifications_enabled=False,
            )
            db.add(settings)
            db.commit()
            return settings
        with patch.object(route, "ensure_test_voicemail_number", side_effect=allocate), (
             patch.object(route, "daytello_save_staff_transfer",
                          return_value={"enabled": True, "phone_number": "+12025550130"})):
            response = self.client.put(
                "/api/shops/shop-b/call-voicemail-number",
                json={"phone_number": "+12025550198"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        with self.factory() as db:
            prefs = db.get(DayTelloVoicemailShopSettings, "s2")
            self.assertEqual(prefs.owner_phone, "+12025550198")
            self.assertTrue(prefs.notifications_enabled)

    def test_unprovisioned_owner_can_save_approved_phone_without_sending(self):
        with self.factory() as db:
            shop = db.get(Shop, "s1")
            shop.highlevel_agent_id = None
            db.commit()
        with patch.object(route, "daytello_save_staff_transfer") as provider:
            result = self.client.put(self.url, json={"phone_number": "+12025550199"})
            provider.assert_not_called()
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()["pending_provisioning"])
        self.assertFalse(result.json()["sms_ready"])
        self.assertFalse(result.json()["notifications_enabled"])
        self.assertFalse(result.json()["forwarding_verified"])
        with self.factory() as db:
            settings = db.get(DayTelloVoicemailShopSettings, "s1")
            self.assertEqual(settings.owner_phone, "+12025550199")
            self.assertFalse(settings.notifications_enabled)
            self.assertEqual(settings.receiving_number, "+12025550123")

    def test_unprovisioned_rejects_unapproved_recipient(self):
        with self.factory() as db:
            db.get(Shop, "s1").highlevel_agent_id = None
            db.commit()
        response = self.client.put(self.url, json={"phone_number": "+12025550198"})
        self.assertEqual(response.status_code, 503)
        with self.factory() as db:
            self.assertIsNone(db.get(DayTelloVoicemailShopSettings, "s1").owner_phone)

    def test_test_relay_activation_requires_platform_call_permission(self):
        with self.factory() as db:
            db.add(DayTelloVoiceRelayAssignment(
                shop_id="s1", relay_number="+12025550123", enabled=False))
            db.commit()
        with patch.object(route, "daytello_save_staff_transfer") as transfer:
            result = self.client.put(
                self.url, json={"phone_number": "+12025550199"})
        self.assertEqual(result.status_code, 409)
        transfer.assert_not_called()
        with self.factory() as db:
            self.assertFalse(db.get(DayTelloVoiceRelayAssignment, "s1").enabled)

    def test_test_relay_activation_requires_verified_provider_route(self):
        with self.factory() as db:
            db.add(DayTelloVoiceRelayAssignment(
                shop_id="s1", relay_number="+12025550123", enabled=False))
            db.commit()
        with (
            patch.dict(os.environ, {"DAYTELLO_VOICE_RELAY_ALLOW_TEST_CALLS": "true"}),
            patch.object(route, "VoiceRelayNumberProvider") as provider,
            patch.object(route, "daytello_save_staff_transfer") as transfer,
        ):
            provider.return_value.find_existing.return_value = None
            result = self.client.put(
                self.url, json={"phone_number": "+12025550199"})
        self.assertEqual(result.status_code, 409)
        transfer.assert_not_called()
        with self.factory() as db:
            self.assertFalse(db.get(DayTelloVoiceRelayAssignment, "s1").enabled)

    def test_test_relay_activation_after_verified_ai_transfer(self):
        with self.factory() as db:
            db.add(DayTelloVoiceRelayAssignment(
                shop_id="s1", relay_number="+12025550123", enabled=False))
            db.commit()
        with (
            patch.dict(os.environ, {"DAYTELLO_VOICE_RELAY_ALLOW_TEST_CALLS": "true"}),
            patch.object(route, "VoiceRelayNumberProvider") as provider,
            patch.object(route, "daytello_save_staff_transfer",
                         return_value={
                             "enabled": True, "phone_number": "+12025550123",
                         }) as transfer,
        ):
            provider.return_value.find_existing.return_value = {
                "number": "+12025550123", "route_verified": True,
            }
            result = self.client.put(
                self.url, json={"phone_number": "+12025550199"})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()["test_relay_enabled_for_calls"])
        self.assertFalse(result.json()["ready"])
        transfer.assert_called_once()
        with self.factory() as db:
            self.assertTrue(db.get(DayTelloVoiceRelayAssignment, "s1").enabled)
            settings = db.get(DayTelloVoicemailShopSettings, "s1")
            self.assertTrue(settings.notifications_enabled)
            self.assertEqual(settings.owner_phone, "+12025550199")

    def test_test_relay_transfer_mismatch_never_activates(self):
        with self.factory() as db:
            db.add(DayTelloVoiceRelayAssignment(
                shop_id="s1", relay_number="+12025550123", enabled=False))
            db.commit()
        with (
            patch.dict(os.environ, {"DAYTELLO_VOICE_RELAY_ALLOW_TEST_CALLS": "true"}),
            patch.object(route, "VoiceRelayNumberProvider") as provider,
            patch.object(route, "daytello_save_staff_transfer",
                         return_value={
                             "enabled": True, "phone_number": "+12405550198",
                         }),
        ):
            provider.return_value.find_existing.return_value = {
                "number": "+12025550123", "route_verified": True,
            }
            result = self.client.put(
                self.url, json={"phone_number": "+12025550199"})
        self.assertEqual(result.status_code, 502)
        with self.factory() as db:
            self.assertFalse(db.get(DayTelloVoiceRelayAssignment, "s1").enabled)
            self.assertFalse(db.get(DayTelloVoicemailShopSettings, "s1").notifications_enabled)

    def test_relay_prepare_requires_explicit_owner_purchase_approval(self):
        endpoint = "/api/shops/shop-a/voice-relay/prepare-test"
        with patch.object(route, "reserve_relay_for_area_code") as provider:
            result = self.client.post(
                endpoint, json={"area_code": "240",
                                "authorize_number_purchase": False})
        self.assertEqual(result.status_code, 409)
        provider.assert_not_called()

    def test_relay_prepare_rejects_disabled_platform_purchase_gate(self):
        endpoint = "/api/shops/shop-a/voice-relay/prepare-test"
        with patch.object(route, "reserve_relay_for_area_code") as provider:
            result = self.client.post(
                endpoint, json={"area_code": "240",
                                "authorize_number_purchase": True})
        self.assertEqual(result.status_code, 409)
        provider.assert_not_called()

    def test_relay_prepare_is_tenant_scoped_and_never_claims_live_ready(self):
        endpoint = "/api/shops/shop-a/voice-relay/prepare-test"
        with patch.dict(os.environ, {
            "DAYTELLO_VOICE_RELAY_TEST_ONLY": "true",
            "DAYTELLO_VOICE_RELAY_PURCHASE_ENABLED": "true",
        }), patch.object(route, "reserve_relay_for_area_code",
                         return_value={
                             "shop_slug": "shop-a", "relay_number": "+12405550123",
                             "provider_route_verified": True,
                             "enabled_for_calls": False,
                         }) as provider:
            result = self.client.post(
                endpoint, json={"area_code": "240",
                                "authorize_number_purchase": True})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertFalse(result.json()["ready_for_customer_calls"])
        self.assertFalse(result.json()["enabled_for_calls"])
        self.assertEqual(provider.call_args.args[0].id, "s1")
        self.assertEqual(provider.call_args.args[2], "240")
        self.assertTrue(provider.call_args.kwargs["approved"])

    def test_relay_prepare_cannot_access_other_shop(self):
        endpoint = "/api/shops/shop-b/voice-relay/prepare-test"
        with patch.dict(os.environ, {
            "DAYTELLO_VOICE_RELAY_TEST_ONLY": "true",
            "DAYTELLO_VOICE_RELAY_PURCHASE_ENABLED": "true",
        }), patch.object(route, "reserve_relay_for_area_code") as provider:
            result = self.client.post(
                endpoint, json={"area_code": "240",
                                "authorize_number_purchase": True})
        self.assertIn(result.status_code, (403, 404))
        provider.assert_not_called()

    def test_no_provisioning_fails_closed(self):
        self.user.shop_slug = "shop-b"
        self.user.shop_id = "s2"
        self.assertEqual(self.client.put(
            "/api/shops/shop-b/call-voicemail-number",
            json={"phone_number": "+12025550199"},
        ).status_code, 409)


if __name__ == "__main__":
    unittest.main()
