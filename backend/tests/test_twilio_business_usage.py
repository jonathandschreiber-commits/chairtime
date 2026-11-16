import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

from app.twilio_business_usage import month_usage

ACCOUNT = "AC" + "a" * 32
KEY = "SK" + "b" * 32
START, END = datetime(2026, 1, 1), datetime(2026, 2, 1)


class TwilioBusinessUsageTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {
            "DAYTELLO_VOICE_RELAY_ACCOUNT_SID": ACCOUNT,
            "DAYTELLO_TWILIO_REPORT_KEY_SID": KEY,
            "DAYTELLO_TWILIO_REPORT_KEY_SECRET": "test",
        }))
        self.client = self.enterContext(patch("app.twilio_business_usage.httpx.Client")).return_value.__enter__.return_value
        self.db = Mock()
        self.db.query.return_value.filter.return_value = [("parent", "shop-id")]
        self.shops = [SimpleNamespace(id="shop-id", slug="shop")]
        self.base = f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT}"

    def reply(self, resource, data, status=200):
        return httpx.Response(status, json=data, request=httpx.Request("GET", f"{self.base}/{resource}.json"))

    def usage(self):
        return self.reply("Usage/Records", {"usage_records": [
            {"account_sid": ACCOUNT, "category": "totalprice", "price_unit": "usd", "price": "2.99"},
            {"account_sid": ACCOUNT, "category": "phonenumbers", "price_unit": "usd", "price": "2.30"},
        ]})

    def test_account_total_counts_once_and_matches_both_legs(self):
        def call(sid, parent, price):
            return {"sid": sid, "parent_call_sid": parent, "account_sid": ACCOUNT,
                    "start_time": "Wed, 14 Jan 2026 12:00:00 +0000", "price_unit": "USD", "price": price}
        self.client.get.side_effect = [self.usage(), self.reply("Calls", {"calls": [
            call("parent", None, "-0.0085"), call("child", "parent", "-0.014"),
            call("unrelated", None, "-0.25"),
        ]})]
        report = month_usage(START, END, self.shops, self.db)
        self.assertEqual(report["total_cents"], 299)
        self.assertEqual(report["shop_cents"], {"shop": 2})
        self.assertEqual(report["shared_cents"], 297)
        self.assertEqual(report["categories"]["phonenumbers"], 230)

    def test_denied_call_access_keeps_provider_total_shared(self):
        self.client.get.side_effect = [self.usage(), self.reply("Calls", {}, 403)]
        report = month_usage(START, END, self.shops, self.db)
        self.assertEqual(report["shared_cents"], 299)
        self.assertEqual(report["shop_cents"], {})
        self.assertFalse(report["call_attribution_complete"])

    def test_denied_usage_access_does_not_show_zero_cost(self):
        self.client.get.return_value = self.reply("Usage/Records", {}, 403)
        report = month_usage(START, END, self.shops, self.db)
        self.assertEqual(report["status"], "unavailable")
        self.assertIsNone(report["total_cents"])
