import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

from app.twilio_business_usage import month_usage, relay_cost_review

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
        self.shops = [SimpleNamespace(id="shop-id", slug="shop", name="Test Shop")]
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

    def test_relay_review_flags_exact_threshold_across_matched_legs(self):
        def call(sid, parent, price, duration, start_time="Wed, 14 Jan 2026 12:00:00 +0000"):
            return {"sid": sid, "parent_call_sid": parent, "account_sid": ACCOUNT,
                    "start_time": start_time, "price_unit": "USD", "price": price, "duration": duration}

        old = call("old", "parent", "-100", "60", "Thu, 01 Jan 2026 00:00:00 +0000")
        self.client.get.return_value = self.reply("Calls", {"calls": [
            call("parent", None, "-10", "120"), call("child", "parent", "-15", "90"),
            call("pending", "parent", None, "50"), old, call("unrelated", None, "-100", "60"),
        ]})
        end = END.replace(tzinfo=timezone.utc)
        result = relay_cost_review(self.shops, self.db, end=end)
        self.assertTrue(result["partial"])
        self.assertEqual(result["shops"], [
            {"slug": "shop", "name": "Test Shop", "cost_cents": 2500,
             "inbound_minutes": 2.0, "outbound_minutes": 1.5},
        ])

    def test_relay_review_applies_threshold_before_rounding(self):
        self.client.get.return_value = self.reply("Calls", {"calls": [
            {"sid": "parent", "account_sid": ACCOUNT, "start_time": "Wed, 14 Jan 2026 12:00:00 +0000",
             "price_unit": "USD", "price": "-24.999", "duration": "60"},
        ]})
        result = relay_cost_review(self.shops, self.db, end=END.replace(tzinfo=timezone.utc))
        self.assertEqual(result["status"], "connected")
        self.assertEqual(result["shops"], [])
