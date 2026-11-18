"""Report HighLevel Voice AI usage to Stripe and replay calls in a sandbox."""

import argparse
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import stripe
from sqlalchemy import Column, DateTime, String
from sqlalchemy.exc import IntegrityError

from app.ai_usage_review import fetch_live_calls
from app.database import Base, SessionLocal, engine
from app.models import Shop


logger = logging.getLogger(__name__)


class LiveAIMeterDelivery(Base):
    __tablename__ = "live_ai_meter_deliveries"

    identifier = Column(String(64), primary_key=True)
    customer_id = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime)


class SandboxAIMeterDelivery(Base):
    __tablename__ = "sandbox_ai_meter_deliveries"

    identifier = Column(String(64), primary_key=True)
    started_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime)


def deliver_call(db, stripe_client, customer_id, location, call, *, live=False):
    call_id, _, occurred_at, seconds = call
    scope = "live" if live else customer_id
    identifier = hashlib.sha256(f"{scope}:{location}:{call_id}".encode()).hexdigest()
    model = LiveAIMeterDelivery if live else SandboxAIMeterDelivery
    delivery = db.get(model, identifier)
    if delivery is None:
        delivery = model(
            identifier=identifier, started_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        if live:
            delivery.customer_id = customer_id
        db.add(delivery)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            delivery = db.get(model, identifier)

    if live and delivery.customer_id != customer_id:
        raise RuntimeError("HighLevel call was previously mapped to a different customer.")
    if delivery.accepted_at is not None:
        return False
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if (now - delivery.started_at).total_seconds() >= 23 * 3600:
        raise RuntimeError("Unconfirmed Stripe delivery requires reconciliation before retrying.")

    minutes = (Decimal(str(seconds)) / 60).quantize(Decimal("0.000000000001"))
    stripe_client.v1.billing.meter_events.create(
        {
            "event_name": "daytello_ai_receptionist_minutes",
            "identifier": identifier,
            "timestamp": int(occurred_at.timestamp()),
            "payload": {"stripe_customer_id": customer_id, "value": str(minutes)},
        },
        options={"idempotency_key": identifier},
    )
    delivery.accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return True


def report_live_usage(db, client, location, token, usage_price, now):
    """Reconcile recent calls during each shop's current paid cycle."""
    shops = db.query(Shop).filter(
        Shop.ai_voice_enabled.is_(True),
        Shop.highlevel_location_id == location,
        Shop.highlevel_agent_id.is_not(None),
        Shop.stripe_customer_id.is_not(None),
        Shop.stripe_subscription_id.is_not(None),
    ).all()
    end = now - timedelta(minutes=3)
    start = end - timedelta(hours=24)
    windows = {}
    failures = 0
    for shop in shops:
        try:
            sub = client.v1.subscriptions.retrieve(shop.stripe_subscription_id)
            if not sub.livemode or sub.customer != shop.stripe_customer_id:
                raise ValueError("Stripe subscription does not match shop customer")
            if sub.status not in {"active", "past_due"}:
                continue
            items = [item for item in sub["items"].data if item.price.id == usage_price]
            if not items:
                continue
            item, = items
            if not item.price.recurring or item.price.recurring.usage_type != "metered":
                raise ValueError("Configured usage price is not metered")
            window_start = max(item.current_period_start, sub.trial_end or 0)
            windows[shop.highlevel_agent_id] = (
                shop.stripe_customer_id, window_start, item.current_period_end,
            )
        except (stripe.StripeError, ValueError, AttributeError) as exc:
            failures += 1
            logger.error("AI meter subscription lookup failed for shop %s (%s)", shop.id, type(exc).__name__)

    delivered = 0
    if windows:
        calls = fetch_live_calls(location, token, windows, start, end)
        for call in calls:
            _, agent, occurred_at, seconds = call
            customer_id, period_start, period_end = windows[agent]
            if seconds <= 0 or not period_start <= occurred_at.timestamp() < period_end:
                continue
            try:
                delivered += deliver_call(db, client, customer_id, location, call, live=True)
            except Exception as exc:
                db.rollback()
                failures += 1
                logger.error("AI meter event delivery failed (%s)", type(exc).__name__)
    return delivered, failures


def run_live_meter_worker(stop):
    key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    price = os.getenv("STRIPE_AI_USAGE_PRICE_ID", "").strip()
    location = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    token = os.getenv("HIGHLEVEL_API_TOKEN", "").strip()
    if not key.startswith(("sk_live_", "rk_live_")) or not all((price, location, token)):
        logger.error("Live AI meter worker configuration is incomplete")
        return

    client = stripe.StripeClient(key)
    while not stop.is_set():
        try:
            with SessionLocal() as db:
                delivered, failures = report_live_usage(
                    db, client, location, token, price, datetime.now(timezone.utc)
                )
            if delivered or failures:
                logger.info("AI meter events accepted=%s failures=%s", delivered, failures)
        except Exception as exc:
            logger.error("AI meter polling failed (%s)", type(exc).__name__)
        stop.wait(300)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shop")
    parser.add_argument("start", type=datetime.fromisoformat)
    parser.add_argument("end", type=datetime.fromisoformat)
    parser.add_argument("--sandbox-subscription")
    args = parser.parse_args()
    if args.start.utcoffset() is None or args.end.utcoffset() is None or args.start >= args.end:
        parser.error("Provide an increasing time window with explicit UTC offsets.")

    with SessionLocal() as db:
        shop = db.query(Shop).filter_by(slug=args.shop, ai_voice_enabled=True).one()
        location = os.environ["HIGHLEVEL_LOCATION_ID"].strip()
        if not shop.highlevel_agent_id or shop.highlevel_location_id != location:
            raise RuntimeError("Shop is not mapped to this HighLevel location and agent.")
        calls = fetch_live_calls(
            location, os.environ["HIGHLEVEL_API_TOKEN"].strip(),
            {shop.highlevel_agent_id}, args.start, args.end,
        )
        calls = [call for call in calls if call[2] < args.end and call[3] > 0]
        report = {"shop": shop.slug, "calls": len(calls), "ai_seconds": sum(call[3] for call in calls)}
        if args.sandbox_subscription:
            key = os.environ["DAYTELLO_STRIPE_SANDBOX_KEY"].strip()
            if not key.startswith(("sk_test_", "rk_test_")):
                raise RuntimeError("A Stripe sandbox key is required.")
            client = stripe.StripeClient(key)
            subscription = client.v1.subscriptions.retrieve(args.sandbox_subscription)
            if subscription.livemode or subscription.status != "active":
                raise RuntimeError("An active Stripe sandbox subscription is required.")
            usage_price = os.environ["DAYTELLO_STRIPE_SANDBOX_AI_USAGE_PRICE_ID"].strip()
            meter_items = [item for item in subscription["items"].data if item.price.id == usage_price
                           and item.price.recurring and item.price.recurring.usage_type == "metered"]
            if len(meter_items) != 1:
                raise RuntimeError("Sandbox subscription must contain the configured metered price.")
            item = meter_items[0]
            if args.start.timestamp() < item.current_period_start or args.end.timestamp() > item.current_period_end:
                raise RuntimeError("Replay window must be inside the active paid billing period.")
            SandboxAIMeterDelivery.__table__.create(bind=engine, checkfirst=True)
            report["new_deliveries"] = sum(
                deliver_call(db, client, subscription.customer, location, call) for call in calls
            )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
