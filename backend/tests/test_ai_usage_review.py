import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

from app.ai_usage_review import review_usage


class AIUsageReviewTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {
            "HIGHLEVEL_LOCATION_ID": "loc-a",
            "HIGHLEVEL_API_TOKEN": "test",
        }))
        self.db = Mock()
        self.db.get.return_value = None
        self.client = self.enterContext(patch("app.ai_usage_review.httpx.Client")).return_value.__enter__.return_value
        self.shops = [
            SimpleNamespace(ai_voice_enabled=True, highlevel_agent_id=agent, highlevel_location_id="loc-a",
                            slug=agent, name=agent.upper())
            for agent in ("a", "b")
        ]

    def test_exact_threshold_uses_live_calls_in_rolling_window(self):
        now = datetime.now(timezone.utc)
        def call(id, agent, duration, age, trial=False):
            return dict(id=id, agentId=agent, locationId="loc-a", duration=duration,
                        createdAt=(now - timedelta(days=age)).isoformat(), trialCall=trial)
        self.client.get.return_value = httpx.Response(
            200, request=httpx.Request("GET", "https://example.test"), json={"total": 6, "callLogs": [
                call("1", "a", 4000, 6), call("2", "a", 4400, 1),
                call("3", "b", 8399, 1), call("4", "b", 60, 1, trial=True),
                call("5", "b", 60, 8), call("6", "unknown", 10000, 1),
            ]})
        result = review_usage(self.shops, self.db)
        self.assertEqual(result["status"], "connected")
        self.assertEqual(result["shops"], [{"slug": "a", "name": "A", "minutes": 140.0}])
        self.assertEqual(self.client.get.call_args.kwargs["params"]["callType"], "LIVE")

    def test_covered_location_does_not_flag_any_shops(self):
        self.db.get.return_value = SimpleNamespace(unlimited=True, updated_at=datetime.now(timezone.utc))
        self.assertEqual(review_usage(self.shops, self.db)["status"], "covered")
        self.client.get.assert_not_called()

    def test_denied_provider_does_not_display_zero_usage(self):
        self.client.get.return_value = httpx.Response(
            403, request=httpx.Request("GET", "https://example.test"))
        result = review_usage(self.shops, self.db)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["provider_http_status"], 403)

    def test_incomplete_pagination_does_not_display_zero_usage(self):
        self.client.get.return_value = httpx.Response(
            200, request=httpx.Request("GET", "https://example.test"), json={"total": 1, "callLogs": []})
        self.assertEqual(review_usage(self.shops, self.db)["status"], "unavailable")
