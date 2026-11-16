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


_FETCH_FAILURES = (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError, AttributeError, InvalidOperation)
RELAY_REVIEW_DOLLARS = Decimal("25")


def _account_auth():
    account = os.getenv("DAYTELLO_VOICE_RELAY_ACCOUNT_SID", "").strip()
    key, secret = _report_credentials()
    if re.fullmatch(r"AC[0-9a-fA-F]{32}", account) and re.fullmatch(r"SK[0-9a-fA-F]{32}", key) and secret:
        return account, (key, secret)
    return account, None


def _matched_calls(client, account, start, end, shops, db, deadline):
    shop_by_id = {str(shop.id): shop.slug for shop in shops}
    relay_call = DayTelloVoiceRelayCall
    # A Dial child can begin after its inbound parent, including near a window boundary.
    first = start.date() - timedelta(days=1)
    bindings = db.query(relay_call.call_sid, relay_call.shop_id).filter(
        relay_call.account_sid == account,
        relay_call.created_at >= datetime.combine(first, datetime.min.time()),
        relay_call.created_at <= end.replace(tzinfo=None),
    )
    shop_by_call = {sid: shop_by_id[shop_id] for sid, shop_id in bindings if shop_id in shop_by_id}
    if not shop_by_call:
        return
    params = {"StartTime>": first.isoformat(),
              "StartTime<": (end.date() + timedelta(days=1)).isoformat(), "PageSize": 1000}
    seen = set()
    for call in _pages(client, f"/2010-04-01/Accounts/{account}", "Calls", "calls", params, deadline, limit=6):
        sid = call["sid"]
        shop = shop_by_call.get(sid) or shop_by_call.get(call.get("parent_call_sid"))
        if not shop or sid in seen or call.get("account_sid") != account:
            continue
        if not call.get("start_time") and call.get("status") in {"busy", "no-answer", "canceled", "failed"} and call.get("price") is None:
            continue
        when = parsedate_to_datetime(call["start_time"]).astimezone(timezone.utc)
        if start <= when < end:
            seen.add(sid)
            yield shop, call, sid in shop_by_call


def relay_cost_review(shops, db, *, end=None):
    """Flag shops on observed call-leg charges, without estimating missing prices."""
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    result = {"status": "unavailable", "shops": [], "partial": False, "window_ends_at": end.isoformat()}
    account, auth = _account_auth()
    if not auth:
        return result
    by_slug = {shop.slug: shop.name for shop in shops}
    costs, seconds, missing = {}, {}, set()
    try:
        with httpx.Client(auth=auth, follow_redirects=False) as client:
            for slug, call, inbound in _matched_calls(client, account, start, end, shops, db, time.monotonic() + 7):
                if call.get("price") is None:
                    missing.add(slug)
                    continue
                costs[slug] = costs.get(slug, Decimal(0)) + _usd(call, "price_unit", call_price=True)
                if call.get("duration") is not None:
                    key = slug, "inbound" if inbound else "outbound"
                    seconds[key] = seconds.get(key, 0) + int(call["duration"])
    except _FETCH_FAILURES as exc:
        _log_failure("relay cost review", exc)
        return result

    flagged = [
        {"slug": slug, "name": by_slug[slug], "cost_cents": _cents(cost),
         "inbound_minutes": round(seconds[slug, "inbound"] / 60, 1) if (slug, "inbound") in seconds else None,
         "outbound_minutes": round(seconds[slug, "outbound"] / 60, 1) if (slug, "outbound") in seconds else None}
        for slug, cost in costs.items() if cost >= RELAY_REVIEW_DOLLARS
    ]
    return {**result, "status": "connected", "partial": bool(missing),
            "shops": sorted(flagged, key=lambda shop: (-shop["cost_cents"], shop["name"]))}


def month_usage(start, end, shops, db):
    result = {"status": "not_configured", "total_cents": None, "shared_cents": None,
              "shop_cents": {}, "categories": {}, "call_attribution_complete": False}
    account, auth = _account_auth()
    if not auth:
        return result

    base = f"/2010-04-01/Accounts/{account}"
    # Usage Records are day-based in GMT. Use the same calendar dates for call matching.
    first, last = start.date(), end.date()
    if first > datetime.now(timezone.utc).date():
        return result
    params = {"StartDate": first.isoformat(), "EndDate": min(last - timedelta(days=1), datetime.now(timezone.utc).date()).isoformat(),
              "PageSize": 1000, "IncludeSubaccounts": "false"}
    deadline = time.monotonic() + 7
    with httpx.Client(auth=auth, follow_redirects=False) as client:
        try:
            usage = {}
            for item in _pages(client, base, "Usage/Records", "usage_records", params, deadline, limit=3):
                category = item["category"]
                if category in CATEGORIES:
                    if category in usage or item["account_sid"] != account:
                        raise ValueError("Unexpected Twilio account or duplicate category")
                    usage[category] = _cents(_usd(item, "price_unit"))
            total = usage.pop("totalprice")
        except _FETCH_FAILURES as exc:
            _log_failure("usage report", exc)
            return {**result, "status": "unavailable"}

        result.update(status="connected", total_cents=total, shared_cents=total, categories=usage)
        call_costs = {}
        missing_price = False
        try:
            utc_start = datetime.combine(first, datetime.min.time(), tzinfo=timezone.utc)
            utc_end = datetime.combine(last, datetime.min.time(), tzinfo=timezone.utc)
            for shop, call, _ in _matched_calls(client, account, utc_start, utc_end, shops, db, deadline):
                if call.get("price") is None:
                    missing_price = True
                    continue
                amount = _usd(call, "price_unit", call_price=True)
                call_costs[shop] = call_costs.get(shop, Decimal(0)) + amount
            attributed = {shop: _cents(cost) for shop, cost in call_costs.items()}
            if sum(attributed.values()) > max(0, total):
                raise ValueError("Call charges do not reconcile to usage total")
        except _FETCH_FAILURES as exc:
            _log_failure("call attribution", exc)
            return result
        result.update(shop_cents=attributed, shared_cents=total - sum(attributed.values()),
                      call_attribution_complete=not missing_price)
    return result
