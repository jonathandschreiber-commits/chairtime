"""Send one welcome email per live shop, even when Stripe retries checkout."""
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import Column, DateTime, JSON, String

from app.database import Base
from app.models import Shop, User

logger = logging.getLogger(__name__)

SUBJECTS = {
    "scheduling": "Welcome to DayTello — your trial has started",
    "scheduling_ai": "Welcome to DayTello — your AI Receptionist trial has started",
}


class ShopWelcomeEmail(Base):
    __tablename__ = "shop_welcome_emails"

    shop_id = Column(String, primary_key=True)
    created_at = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    payload = Column(JSON, nullable=True)


def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _message(shop, owner, plan, frontend_url):
    try:
        shop_timezone = ZoneInfo(shop.timezone or "America/New_York")
    except ZoneInfoNotFoundError:
        shop_timezone = ZoneInfo("America/New_York")
    trial_end = shop.trial_ends_at
    if trial_end.tzinfo is None:
        trial_end = trial_end.replace(tzinfo=timezone.utc)
    billing_day = trial_end.astimezone(shop_timezone).date()
    shop_url = f"{frontend_url.rstrip('/')}/{quote(shop.slug, safe='')}"
    values = {
        "owner_first_name": ((owner.name or "").split() or ["there"])[0],
        "shop_name": shop.name,
        "first_billing_date": f"{billing_day:%B} {billing_day.day}, {billing_day.year}",
        "setup_url": f"{shop_url}/onboarding",
        "account_options_url": f"{shop_url}/admin/account",
    }
    template = Path(__file__).with_name("email_templates") / f"welcome_{plan}.html"
    html = re.sub(r"\{\{(\w+)\}\}", lambda match: escape(values[match[1]]),
                  template.read_text(encoding="utf-8"))
    return {
        "from": "DayTello <welcome@updates.daytello.com>",
        "reply_to": "info@daytello.com",
        "to": [owner.email],
        "subject": SUBJECTS[plan],
        "html": html,
    }


def send_checkout_welcome(db, shop, *, owner_id, plan, frontend_url):
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key or plan not in SUBJECTS or not owner_id or not shop.trial_ends_at:
        logger.warning("Welcome email skipped because checkout email configuration is incomplete")
        return

    shop_id = shop.id
    db.query(Shop).filter_by(id=shop_id).with_for_update().one()
    delivery = db.get(ShopWelcomeEmail, shop_id)
    if delivery is None:
        owner = db.query(User).filter_by(id=owner_id, shop_id=shop_id, role="owner").one_or_none()
        if owner is None:
            logger.warning("Welcome email skipped because checkout owner could not be verified")
            return
        delivery = ShopWelcomeEmail(
            shop_id=shop_id, created_at=_utc_now(),
            payload=_message(shop, owner, plan, frontend_url),
        )
        db.add(delivery)
        db.commit()

    delivery = db.query(ShopWelcomeEmail).filter_by(shop_id=shop_id).with_for_update().one()
    if delivery.sent_at is not None:
        return
    # Resend deduplicates for 24 hours. An older ambiguous attempt requires review.
    if _utc_now() - delivery.created_at >= timedelta(hours=23):
        logger.error("Welcome email delivery requires reconciliation")
        return

    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Idempotency-Key": f"daytello-welcome/{shop_id}",
            },
            json=delivery.payload,
            timeout=8,
        )
    except httpx.RequestError:
        raise RuntimeError("Welcome email provider request failed") from None
    if not response.is_success:
        logger.warning("Welcome email provider returned HTTP %s", response.status_code)
        raise RuntimeError("Welcome email provider rejected the request")

    delivery.sent_at = _utc_now()
    delivery.payload = None
    db.commit()
