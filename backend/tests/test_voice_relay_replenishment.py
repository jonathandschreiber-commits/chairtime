from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from app import voice_relay_replenishment as reserve


class ProductionReserveTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.db.get_bind.return_value.dialect.name = "postgresql"
        self.db.get.return_value = None
        self.provider = MagicMock()
        self.provider.list_reserved_relay_numbers.return_value = []
        self.provider.prepare_reserve_purchase.return_value = "+12025550123"
        for name, value in (
            ("reserve_replenishment_enabled", MagicMock(return_value=True)),
            ("VoiceRelayNumberProvider", MagicMock(return_value=self.provider)),
            ("SessionLocal", MagicMock()),
            ("_check_number_conflicts", MagicMock()),
        ):
            patcher = patch.object(reserve, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        reserve.SessionLocal.return_value.__enter__.return_value = self.db

    def test_keeps_existing_verified_spare(self):
        self.provider.list_reserved_relay_numbers.return_value = ["+12025550123"]
        reserve.ensure_production_relay_reserve()
        self.provider.prepare_reserve_purchase.assert_not_called()
        self.provider.purchase_reserve.assert_not_called()

    def test_commits_exact_intent_before_ordering(self):
        def purchase(number):
            self.db.commit.assert_called_once()
            self.assertEqual(self.db.add.call_args.args[0].relay_number, number)

        self.provider.purchase_reserve.side_effect = purchase
        reserve.ensure_production_relay_reserve()
        self.provider.purchase_reserve.assert_called_once_with("+12025550123")

    def test_unresolved_intent_blocks_another_charge(self):
        self.db.get.return_value = SimpleNamespace(relay_number="+12025550123")
        self.provider.find_verified_reserve.return_value = None
        with self.assertRaises(HTTPException) as result:
            reserve.ensure_production_relay_reserve()
        self.assertEqual(result.exception.status_code, 503)
        self.provider.prepare_reserve_purchase.assert_not_called()
        self.provider.purchase_reserve.assert_not_called()
