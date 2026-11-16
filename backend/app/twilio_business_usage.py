"""Reconcile relay call connectivity to Twilio's account-level usage total."""

import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx

from app.voice_relay_delivery import DayTelloVoiceRelayCall

logger = logging.getLogger(__name__)
ORIGIN = "https://api.twilio.com"
CATEGORIES = ("totalprice", "calls", "phonenumbers", "recordings", "sms")


def _usd(item, currency_key, *, call_price=False):
    if item[currency_key].lower() != "usd":
        raise ValueError("Expected USD")
    price = Decimal(item["price"])
    if not price.is_finite():
        raise ValueError("Invalid price")
    return -price if call_price else price


def _cents(amount):
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _pages(client, base, resource, key, params, deadline, *, limit):
    path = f"{base}/{resource}.json"
    url = ORIGIN + path
    for _ in range(limit):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        response = client.get(url, params=params, timeout=min(remaining, 3))
        response.raise_for_status()
        payload = response.json()
        records = payload[key]
        if not isinstance(records, list):
            raise ValueError("Invalid usage records")
        yield from records
        next_page = payload.get("next_page_uri")
        if not next_page:
            return
        parts = urlsplit(next_page)
        if parts.scheme or parts.netloc or parts.path != path or not parts.query:
            raise ValueError("Invalid Twilio pagination link")
        url, params = ORIGIN + next_page, None
    raise ValueError("Twilio pagination limit reached")


def _report_credentials():
    for prefix in ("DAYTELLO_TWILIO_REPORT", "DAYTELLO_VOICE_RELAY_PRICING", "DAYTELLO_VOICE_RELAY_API"):
        sid = os.getenv(f"{prefix}_KEY_SID", "").strip()
        secret = os.getenv(f"{prefix}_KEY_SECRET", "").strip()
        if sid or secret:
            return sid, secret
    return "", ""


def _log_failure(stage, exc):
    if isinstance(exc, httpx.HTTPStatusError):
        logger.warning("Twilio %s returned HTTP %s", stage, exc.response.status_code)
    else:
        logger.warning("Twilio %s failed (%s)", stage, type(exc).__name__)


def month_usage(start, end, shops, db):
    result = {"status": "not_configured", "total_cents": None, "shared_cents": None,
              "shop_cents": {}, "categories": {}, "call_attribution_complete": False}
    account = os.getenv("DAYTELLO_VOICE_RELAY_ACCOUNT_SID", "").strip()
    key, secret = _report_credentials()
    if not re.fullmatch(r"AC[0-9a-fA-F]{32}", account) or not re.fullmatch(r"SK[0-9a-fA-F]{32}", key) or not secret:
        return result

    base = f"/2010-04-01/Accounts/{account}"
    # Usage Records are day-based in GMT. Use the same calendar dates for call matching.
    first, last = start.date(), end.date()
    if first > datetime.now(timezone.utc).date():
        return result
    params = {"StartDate": first.isoformat(), "EndDate": min(last - timedelta(days=1), datetime.now(timezone.utc).date()).isoformat(),
              "PageSize": 1000, "IncludeSubaccounts": "false"}
    deadline = time.monotonic() + 7
    failures = (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError, AttributeError, InvalidOperation)
    with httpx.Client(auth=(key, secret), follow_redirects=False) as client:
        try:
            usage = {}
            for item in _pages(client, base, "Usage/Records", "usage_records", params, deadline, limit=3):
                category = item["category"]
                if category in CATEGORIES:
                    if category in usage or item["account_sid"] != account:
                        raise ValueError("Unexpected Twilio account or duplicate category")
                    usage[category] = _cents(_usd(item, "price_unit"))
            total = usage.pop("totalprice")
        except failures as exc:
            _log_failure("usage report", exc)
            return {**result, "status": "unavailable"}

        result.update(status="connected", total_cents=total, shared_cents=total, categories=usage)
        shop_by_id = {str(shop.id): shop.slug for shop in shops}
        relay_call = DayTelloVoiceRelayCall
        bindings = db.query(relay_call.call_sid, relay_call.shop_id).filter(
            relay_call.account_sid == account,
            relay_call.created_at >= datetime.combine(first - timedelta(days=1), datetime.min.time()),
            relay_call.created_at < datetime.combine(last + timedelta(days=1), datetime.min.time()),
        )
        shop_by_call = {sid: shop_by_id[shop_id] for sid, shop_id in bindings if shop_id in shop_by_id}
        if not shop_by_call:
            return result
        call_costs = {}
        missing_price = False
        seen = set()
        try:
            call_params = {"StartTime>": (first - timedelta(days=1)).isoformat(),
                           "StartTime<": last.isoformat(), "PageSize": 1000}
            for call in _pages(client, base, "Calls", "calls", call_params, deadline, limit=6):
                sid = call["sid"]
                shop = shop_by_call.get(sid) or shop_by_call.get(call.get("parent_call_sid"))
                if not shop or sid in seen or call.get("account_sid") != account:
                    continue
                day = parsedate_to_datetime(call["start_time"]).astimezone(timezone.utc).date()
                if not first <= day < last:
                    continue
                seen.add(sid)
                if call.get("price") is None:
                    missing_price = True
                    continue
                amount = _usd(call, "price_unit", call_price=True)
                call_costs[shop] = call_costs.get(shop, Decimal(0)) + amount
            attributed = {shop: _cents(cost) for shop, cost in call_costs.items()}
            if sum(attributed.values()) > max(0, total):
                raise ValueError("Call charges do not reconcile to usage total")
        except failures as exc:
            _log_failure("call attribution", exc)
            return result
        result.update(shop_cents=attributed, shared_cents=total - sum(attributed.values()),
                      call_attribution_complete=not missing_price)
    return result
