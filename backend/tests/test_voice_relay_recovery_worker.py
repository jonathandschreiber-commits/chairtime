"""Offline safety tests for the opt-in, one-shot relay recovery worker."""
import contextlib
import io
import os
import unittest
from unittest.mock import patch

from app.voice_relay_recovery_worker import main, run_once


FLAGS = {
    "DAYTELLO_VOICE_RELAY_TEST_ONLY": "true",
    "DAYTELLO_VOICEMAIL_TEST_ONLY": "true",
    "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "true",
    "DAYTELLO_VOICE_RELAY_RECOVERY_WORKER_ENABLED": "true",
}


class VoiceRelayRecoveryWorkerTests(unittest.TestCase):
    def test_explicit_execution_is_required_even_when_enabled(self):
        with patch.dict(os.environ, FLAGS):
            with self.assertRaises(PermissionError):
                run_once(shop_id="third-shop-id")
            with self.assertRaises(PermissionError):
                run_once(shop_id="third-shop-id", execute=1)

    def test_all_four_flags_are_required(self):
        for flag in FLAGS:
            with self.subTest(flag=flag):
                disabled = {**FLAGS, flag: "false"}
                with patch.dict(os.environ, disabled):
                    with self.assertRaises(PermissionError) as error:
                        run_once(shop_id="third-shop-id", execute=True)
                    self.assertIn(flag, str(error.exception))

    def test_rejects_invalid_batch_sizes_before_importing_delivery(self):
        with patch.dict(os.environ, FLAGS):
            for limit in (0, 101, True, "25", -1):
                with self.subTest(limit=limit):
                    with self.assertRaises(ValueError):
                        run_once(shop_id="third-shop-id", limit=limit, execute=True)

    def test_one_batch_delegates_to_atomic_delivery_recovery(self):
        with patch.dict(os.environ, FLAGS):
            with patch(
                "app.voice_relay_delivery.recover_queued_relay_alerts",
                return_value=3,
            ) as recover:
                self.assertEqual(run_once(shop_id="third-shop-id", limit=7, execute=True), 3)
            recover.assert_called_once_with(shop_id="third-shop-id", limit=7)

    def test_shop_scope_is_mandatory_and_validated_before_delivery_import(self):
        with patch.dict(os.environ, FLAGS), patch(
            "app.voice_relay_delivery.recover_queued_relay_alerts",
        ) as recover:
            for shop_id in (None, "", " ", "../other-shop", "a" * 129, 123):
                with self.subTest(shop_id=shop_id):
                    with self.assertRaises(ValueError):
                        run_once(shop_id=shop_id, execute=True)
            recover.assert_not_called()

    def test_cli_rejects_missing_shop_scope_without_sending(self):
        stderr = io.StringIO()
        with patch.dict(os.environ, FLAGS), patch(
            "app.voice_relay_delivery.recover_queued_relay_alerts",
        ) as recover, contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as result:
                main(["--execute"])
        self.assertEqual(result.exception.code, 2)
        self.assertIn("exact shop ID", stderr.getvalue())
        recover.assert_not_called()

    def test_cli_requires_opt_in_without_attempting_recovery(self):
        stderr = io.StringIO()
        with patch.dict(os.environ, FLAGS), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as result:
                main([])
        self.assertEqual(result.exception.code, 2)
        self.assertIn("Explicit recovery execution approval", stderr.getvalue())

    def test_cli_reports_examined_receipts_not_confirmed_sms(self):
        stdout = io.StringIO()
        with patch.dict(os.environ, FLAGS), \
             patch(
                 "app.voice_relay_delivery.recover_queued_relay_alerts",
                 return_value=2,
             ) as recover, \
             contextlib.redirect_stdout(stdout):
            self.assertEqual(main(["--execute", "--shop-id", "third-shop-id", "--limit", "4"]), 0)
        recover.assert_called_once_with(shop_id="third-shop-id", limit=4)
        self.assertIn("Examined 2 queued", stdout.getvalue())
        self.assertIn("SMS delivery not confirmed", stdout.getvalue())


    def test_preview_only_needs_isolated_test_flags_and_never_executes(self):
        preview_flags = {**FLAGS,
            "DAYTELLO_VOICEMAIL_OWNER_SMS_ENABLED": "false",
            "DAYTELLO_VOICE_RELAY_RECOVERY_WORKER_ENABLED": "false",
        }
        with patch.dict(os.environ, preview_flags), \
             patch("app.voice_relay_delivery.preview_queued_relay_alerts",
                   return_value=2) as preview, \
             patch("app.voice_relay_delivery.recover_queued_relay_alerts") as recover:
            self.assertEqual(run_once(shop_id="third-shop-id", limit=4, preview=True), 2)
        preview.assert_called_once_with(shop_id="third-shop-id", limit=4)
        recover.assert_not_called()

    def test_preview_rejects_non_test_environment(self):
        with patch.dict(os.environ, {**FLAGS, "DAYTELLO_VOICEMAIL_TEST_ONLY": "false"}), \
             patch("app.voice_relay_delivery.preview_queued_relay_alerts") as preview:
            with self.assertRaises(PermissionError):
                run_once(shop_id="third-shop-id", preview=True)
        preview.assert_not_called()

    def test_preview_and_execution_are_mutually_exclusive(self):
        with patch.dict(os.environ, FLAGS):
            with self.assertRaises(ValueError):
                run_once(shop_id="third-shop-id", preview=True, execute=True)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as result:
                main(["--preview", "--execute", "--shop-id", "third-shop-id"])
        self.assertEqual(result.exception.code, 2)

    def test_cli_preview_reports_count_without_sms(self):
        stdout = io.StringIO()
        with patch.dict(os.environ, FLAGS), \
             patch("app.voice_relay_delivery.preview_queued_relay_alerts",
                   return_value=3) as preview, \
             patch("app.voice_relay_delivery.recover_queued_relay_alerts") as recover, \
             contextlib.redirect_stdout(stdout):
            self.assertEqual(main(["--preview", "--shop-id", "third-shop-id"]), 0)
        preview.assert_called_once_with(shop_id="third-shop-id", limit=25)
        recover.assert_not_called()
        self.assertIn("Preview: up to 3 eligible", stdout.getvalue())
        self.assertIn("no SMS sent", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
