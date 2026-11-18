"""Durable, once-per-paid-period owner alerts. Does not change call routing."""
import hashlib
import logging
import os
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

import httpx
from sqlalchemy import Column, DateTime, String
from sqlalchemy.exc import IntegrityError

from app.database import Base
from app.models import Shop, User
from app.ai_usage_summary import summarize, value, object_id

logger = logging.getLogger(__name__)


class AIUsageLimitAlert(Base):
    __tablename__ = "ai_usage_limit_alerts"
    id = Column(String(64), primary_key=True)
    shop_id = Column(String, nullable=False, index=True)
    subscription_id = Column(String, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    sms_state = Column(String(24), nullable=False, default="pending")
    email_state = Column(String(24), nullable=False, default="pending")


def identity(shop_id, subscription_id, period_start):
    return hashlib.sha256(f"{shop_id}:{subscription_id}:{period_start}".encode()).hexdigest()


def qualifies(billing):
    return bool(billing and billing.get("metered") and billing.get("usage_available")
        and billing.get("status") in {"active", "past_due"}
        and billing.get("included_minutes") == 250
        and billing.get("overage_rate_cents") == 29
        and billing.get("minutes_used") is not None and billing["minutes_used"] >= 250)


def alert_view(db, shop, billing):
    if not billing or not billing.get("metered") or billing.get("included_minutes") != 250:
        return None
    key = identity(shop.id, shop.stripe_subscription_id, billing["period_start"])
    row = db.get(AIUsageLimitAlert, key)
    from app.voicemail_models import DayTelloVoicemailShopSettings
    from app.voicemail_owner_verification import verified_owner_recipient
    settings = db.get(DayTelloVoicemailShopSettings, shop.id)
    sms_available = False
    if settings and settings.location_id == shop.highlevel_location_id == os.getenv("HIGHLEVEL_LOCATION_ID"):
        try:
            verified_owner_recipient(db, shop.id, settings.owner_phone)
            sms_available = bool(os.getenv("HIGHLEVEL_SMS_FROM_NUMBER"))
        except Exception:
            pass
    return {
        "reached": qualifies(billing),
        "sms_available": sms_available,
        "sms_state": row.sms_state if row else "pending",
        "email_state": row.email_state if row else "pending",
        "behavior": "continue",
        "pause_available": False,
        "pause_note": "Automatic pause is not available yet. Calls must be verified to reach your chosen phone or voicemail before this option can be enabled.",
        "checking_note": "Usage is checked about every five minutes. Recent calls may take additional time to appear.",
    }


def messages(shop, period_end, frontend_url):
    url = f"{frontend_url.rstrip('/')}/{quote(shop.slug, safe='')}/admin/ai-usage"
    date = period_end.strftime("%B %d, %Y")
    text = (f"DayTello: {shop.name} has used its 250 included AI minutes this billing period. "
            f"AI stays on at $0.29 per extra minute. Your allowance resets {date}. Details: {url}")
    return url, text


def _claim(db, key, channel):
    field = getattr(AIUsageLimitAlert, channel + "_state")
    claimed = db.query(AIUsageLimitAlert).filter(AIUsageLimitAlert.id == key, field.in_(["pending", "failed", "unavailable"])).update(
        {channel + "_state": "sending"}, synchronize_session=False)
    db.commit()
    return claimed == 1


def _finish(db, key, channel, state):
    db.query(AIUsageLimitAlert).filter(AIUsageLimitAlert.id == key).update(
        {channel + "_state": state}, synchronize_session=False)
    db.commit()


def send_limit_alert(db, shop, billing):
    """Claim each channel before provider I/O; never blindly retry ambiguous sends."""
    if not qualifies(billing):
        return False
    key = identity(shop.id, shop.stripe_subscription_id, billing["period_start"])
    start = datetime.fromisoformat(billing["period_start"]).replace(tzinfo=None)
    end = datetime.fromisoformat(billing["period_end"]).replace(tzinfo=None)
    if not db.get(AIUsageLimitAlert, key):
        db.add(AIUsageLimitAlert(id=key, shop_id=shop.id, subscription_id=shop.stripe_subscription_id,
            period_start=start, period_end=end, created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            sms_state="pending", email_state="pending"))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    url, text = messages(shop, end, os.getenv("CHAIRTIME_FRONTEND_URL", "https://www.daytello.com"))
    if _claim(db, key, "email"):
        state = "unavailable"
        try:
            owners = db.query(User).filter(User.shop_id == shop.id, User.role == "owner", User.is_active.is_(True)).all()
            api_key = os.getenv("RESEND_API_KEY", "").strip()
            if len(owners) == 1 and owners[0].email and api_key:
                response = httpx.post("https://api.resend.com/emails", timeout=8,
                    headers={"Authorization": f"Bearer {api_key}", "Idempotency-Key": f"daytello-usage/{key}"},
                    json={"from": "DayTello <welcome@updates.daytello.com>", "reply_to": "info@daytello.com",
                        "to": [owners[0].email], "subject": "DayTello: Your 250 included AI minutes are used",
                        "text": text,
                        "html": f"<h1>Your included AI minutes are used</h1><p>{escape(text.split(' Details:')[0])}</p><p><a href='{escape(url, quote=True)}'>View AI Usage &amp; Billing</a></p>"})
                state = "accepted" if response.is_success else ("failed" if 400 <= response.status_code < 500 else "unknown")
        except Exception:
            state = "unknown"
            logger.error("AI usage email outcome needs review for alert %s", key)
        _finish(db, key, "email", state)
    if _claim(db, key, "sms"):
        state = "unavailable"
        try:
            from app.voicemail_models import DayTelloVoicemailShopSettings
            from app.voicemail_owner_verification import verified_owner_recipient
            from app.routes.reminders import send_highlevel_sms
            settings = db.get(DayTelloVoicemailShopSettings, shop.id)
            if settings and settings.location_id == shop.highlevel_location_id == os.getenv("HIGHLEVEL_LOCATION_ID"):
                # Use only this shop's possession-verified owner number.
                recipient = verified_owner_recipient(db, shop.id, settings.owner_phone)
                result = send_highlevel_sms(recipient, text, shop_id=shop.id, shop_slug=shop.slug,
                    purpose="ai-usage-threshold", source_id=key)
                state = "accepted" if result.get("success") else ("failed" if result.get("step") != "message" or 400 <= (result.get("status") or 0) < 500 else "unknown")
        except Exception:
            state = "unavailable"
            logger.warning("AI usage SMS unavailable for alert %s", key)
        _finish(db, key, "sms", state)
    return True


def check_usage_alerts(db, client, usage_price):
    """Only the configured metered price is eligible; legacy and trials are excluded."""
    shops = db.query(Shop).filter(Shop.ai_voice_enabled.is_(True), Shop.stripe_subscription_id.is_not(None),
                                 Shop.stripe_customer_id.is_not(None)).all()
    price = None
    for shop in shops:
        try:
            sub = client.v1.subscriptions.retrieve(shop.stripe_subscription_id)
            if not sub.livemode or object_id(sub.customer) != shop.stripe_customer_id or sub.status not in {"active", "past_due"}:
                continue
            items = value(value(sub, "items", {}), "data", [])
            if not any(object_id(value(i, "price")) == usage_price for i in items):
                continue
            if price is None:
                price = client.v1.prices.retrieve(usage_price, params={"expand": ["tiers"]})
            preview = client.v1.invoices.create_preview({"customer": shop.stripe_customer_id, "subscription": sub.id})
            billing = summarize(sub, preview, price)
            send_limit_alert(db, shop, billing)
        except Exception as exc:
            db.rollback()
            logger.error("AI usage alert check failed for shop %s (%s)", shop.id, type(exc).__name__)
