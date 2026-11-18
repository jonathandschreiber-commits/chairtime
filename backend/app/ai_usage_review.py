"""Weekly Voice AI review for DayTello's HighLevel location."""

import logging
import math
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import Boolean, Column, DateTime, String

from app.database import Base

logger = logging.getLogger(__name__)
REVIEW_SECONDS = 140 * 60


class HighLevelAIPlanRecord(Base):
    __tablename__ = "highlevel_ai_plan_records"

    location_id = Column(String(128), primary_key=True)
    unlimited = Column(Boolean, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    updated_by = Column(String, nullable=False)


def review_usage(shops, db):
    location = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    record = db.get(HighLevelAIPlanRecord, location) if location else None
    result = {
        "location_id": location or None,
        "unlimited": record.unlimited if record else None,
        "confirmed_at": record.updated_at.isoformat() if record else None,
        "status": "unavailable",
        "shops": [],
        "location_shop_count": 0,
    }
    shops_by_agent = defaultdict(list)
    other_locations = 0
    for shop in shops:
        if not shop.ai_voice_enabled or not shop.highlevel_agent_id:
            continue
        if location and shop.highlevel_location_id == location:
            shops_by_agent[shop.highlevel_agent_id].append(shop)
        else:
            other_locations += 1
    result["location_shop_count"] = sum(map(len, shops_by_agent.values()))
    result["unmonitored_shop_count"] = other_locations
    if result["unlimited"]:
        return {**result, "status": "covered"}
    if not shops_by_agent:
        return {**result, "status": "empty"}
    if any(len(matched) != 1 for matched in shops_by_agent.values()):
        return {**result, "status": "ambiguous"}
    token = os.getenv("HIGHLEVEL_API_TOKEN", "").strip()
    if not token:
        return result

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    duration_by_agent = defaultdict(float)
    try:
        for _, agent, _, seconds in fetch_live_calls(location, token, shops_by_agent, start, end):
            duration_by_agent[agent] += seconds
    except httpx.HTTPStatusError as exc:
        logger.warning("Voice AI usage review received HighLevel HTTP %s", exc.response.status_code)
        return {**result, "provider_http_status": exc.response.status_code}
    except (httpx.RequestError, ValueError, TypeError, KeyError, AttributeError, TimeoutError) as exc:
        logger.warning("Voice AI usage review unavailable (%s)", type(exc).__name__)
        return result

    flagged = [
        {"slug": shops_by_agent[agent][0].slug, "name": shops_by_agent[agent][0].name,
         "minutes": round(seconds / 60, 1)}
        for agent, seconds in duration_by_agent.items() if seconds >= REVIEW_SECONDS
    ]
    return {**result, "status": "connected", "window_ends_at": end.isoformat(),
            "shops": sorted(flagged, key=lambda item: (-item["minutes"], item["name"]))}


def fetch_live_calls(location, token, agents, start, end):
    params = {"locationId": location, "startDate": int(start.timestamp() * 1000),
              "endDate": int(end.timestamp() * 1000), "timezone": "UTC",
              "callType": "LIVE", "pageSize": 50, "sortBy": "createdAt", "sort": "descend"}
    headers = {"Authorization": f"Bearer {token}", "Version": "v3"}
    calls = []
    seen = set()
    deadline = time.monotonic() + 6
    with httpx.Client(headers=headers, follow_redirects=False) as client:
        for page in range(1, 41):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            response = client.get("https://services.leadconnectorhq.com/voice-ai/dashboard/call-logs",
                                  params={**params, "page": page}, timeout=min(remaining, 3))
            response.raise_for_status()
            payload = response.json()
            if "callLogs" not in payload:
                payload = payload["data"]
            logs, total = payload["callLogs"], payload["total"]
            if not isinstance(logs, list) or len(logs) > 50 or type(total) is not int or total < 0:
                raise ValueError("Invalid call page")
            for call in logs:
                call_id, agent = call["id"], call["agentId"]
                if not call_id or call_id in seen:
                    raise ValueError("Invalid or repeated call ID")
                seen.add(call_id)
                if call.get("locationId") not in (None, location):
                    raise ValueError("Unexpected call location")
                if agent not in agents or call["trialCall"] is True:
                    continue
                if call["trialCall"] is not False:
                    raise ValueError("Unknown Voice AI call type")
                when = datetime.fromisoformat(call["createdAt"].replace("Z", "+00:00"))
                seconds = call["duration"]
                if when.tzinfo is None or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
                    raise ValueError("Invalid call time or duration")
                if start <= when <= end:
                    calls.append((call_id, agent, when, seconds))
            if len(seen) == total:
                break
            if not logs or len(seen) > total:
                raise ValueError("Incomplete call history")
        else:
            raise ValueError("Call log page limit reached")
    return calls
