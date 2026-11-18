"""Replay a shop's HighLevel Voice AI usage into a Stripe sandbox."""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import stripe
from sqlalchemy import Column, DateTime, String
from sqlalchemy.exc import IntegrityError

from app.ai_usage_review import fetch_live_calls
from app.database import Base, SessionLocal, engine
from app.models import Shop


class SandboxAIMeterDelivery(Base):
    __tablename__ = "sandbox_ai_meter_deliveries"

    identifier = Column(String(64), primary_key=True)
    started_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime)


def deliver_call(db, stripe_client, customer_id, location, call):
    call_id, _, occurred_at, seconds = call
    identifier = hashlib.sha256(f"{customer_id}:{location}:{call_id}".encode()).hexdigest()
    delivery = db.get(SandboxAIMeterDelivery, identifier)
    if delivery is None:
        delivery = SandboxAIMeterDelivery(
            identifier=identifier, started_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.add(delivery)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            delivery = db.get(SandboxAIMeterDelivery, identifier)

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
