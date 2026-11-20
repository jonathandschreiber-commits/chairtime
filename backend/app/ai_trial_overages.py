"""Settle separately disclosed Voice AI usage after the free trial closes."""

import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Column, String
from sqlalchemy.exc import IntegrityError

from app.database import Base
from app.ai_usage_review import fetch_live_calls


POLICY = "250_minutes_29_cents_v1"


class AITrialSettlement(Base):
    __tablename__ = "ai_trial_settlements"

    key = Column(String(64), primary_key=True)


def overage_cents(seconds):
    billable_seconds = max(Decimal(0), seconds - Decimal(250 * 60))
    return int((billable_seconds * 29 / 60).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def settle_trial(db, client, sub, agent, location, token, now):
    if sub.metadata.get("ai_trial_overages") != POLICY or not sub.trial_start or not sub.trial_end:
        return
    if sub.status == "trialing":
        return

    start = datetime.fromtimestamp(sub.trial_start, timezone.utc)
    end = datetime.fromtimestamp(min(sub.trial_end, sub.ended_at or sub.trial_end), timezone.utc)
    # Allow the provider's completed call records to arrive before settling.
    if now < end + timedelta(minutes=15):
        return

    key = hashlib.sha256(f"daytello-ai-trial:{sub.id}:{sub.trial_start}".encode()).hexdigest()
    if db.get(AITrialSettlement, key):
        return

    invoices = client.v1.invoices
    invoice = next((item for item in invoices.list({"customer": sub.customer}).auto_paging_iter()
                    if item.metadata.get("ai_trial_settlement") == key), None)
    if invoice is None:
        seconds = Decimal(0)
        cursor = start
        while cursor < end:
            stop = min(cursor + timedelta(days=1), end)
            calls = fetch_live_calls(location, token, {agent}, cursor, stop)
            seconds += sum((Decimal(str(call[3])) for call in calls if cursor <= call[2] < stop), Decimal(0))
            cursor = stop
        amount = overage_cents(seconds)
        if amount:
            payment_method = sub.default_payment_method
            params = {
                "customer": sub.customer,
                "currency": "usd",
                "collection_method": "charge_automatically",
                "auto_advance": False,
                "metadata": {"ai_trial_settlement": key, "amount_cents": str(amount)},
            }
            if payment_method:
                params["default_payment_method"] = payment_method
            invoice = invoices.create(params, options={"idempotency_key": f"{key}:invoice"})

    if invoice is not None and invoice.status == "draft":
        if not any(line.metadata.get("ai_trial_settlement") == key for line in invoice.lines.auto_paging_iter()):
            client.v1.invoice_items.create({
                "customer": sub.customer,
                "invoice": invoice.id,
                "amount": int(invoice.metadata["amount_cents"]),
                "currency": "usd",
                "description": "DayTello trial AI Receptionist usage above 250 included minutes (29¢/minute)",
                "metadata": {"ai_trial_settlement": key},
            }, options={"idempotency_key": f"{key}:item"})
        invoices.finalize_invoice(invoice.id, {"auto_advance": True},
                                  options={"idempotency_key": f"{key}:finalize"})

    db.add(AITrialSettlement(key=key))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if not db.get(AITrialSettlement, key):
            raise
