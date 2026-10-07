"""Private cash-activity reporting. Does not change subscriptions or payments."""
import os
import re
import time
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from zoneinfo import ZoneInfo

import stripe
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.database import Base, get_db
from app.models import Shop, User, generate_uuid
from app.routes.auth import get_current_user, is_platform_admin
from app.routes.billing import get_stripe_secret_key

router = APIRouter()
REPORT_ZONE = ZoneInfo("America/New_York")


class BusinessExpense(Base):
    __tablename__ = "business_expenses"
    id = Column(String, primary_key=True, default=generate_uuid)
    request_id = Column(String, nullable=False, unique=True)
    reference_key = Column(String, nullable=False, unique=True)
    incurred_on = Column(Date, nullable=False, index=True)
    shop_slug = Column(String, nullable=True, index=True)
    provider = Column(String, nullable=False)
    description = Column(String, nullable=False)
    reference = Column(String, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    is_void = Column(Boolean, nullable=False, default=False)
    voided_by = Column(String, nullable=True)
    voided_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class ExpenseInput(BaseModel):
    request_id: str = Field(pattern=r"^[a-zA-Z0-9-]{16,64}$")
    incurred_on: date
    shop_slug: str | None = None
    provider: Literal["highlevel", "railway", "vercel", "domain", "other"]
    description: str = Field(min_length=1, max_length=160)
    reference: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(gt=0, le=1000000, decimal_places=2)
    kind: Literal["cost", "credit"] = "cost"


def require_business_admin(user: User = Depends(get_current_user)):
    if not is_platform_admin(user):
        raise HTTPException(403, "This report is restricted to the platform administrator.")
    return user


def obj(value, key, default=None):
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


def oid(value):
    return value if isinstance(value, str) else obj(value, "id")


def month_bounds(month):
    if not re.fullmatch(r"\d{4}-\d{2}", month or ""):
        raise HTTPException(400, "Choose a month as YYYY-MM.")
    try:
        year, number = map(int, month.split("-"))
        if not 2020 <= year <= 2100:
            raise ValueError()
        start = datetime(year, number, 1, tzinfo=REPORT_ZONE)
        end = datetime(year + (number == 12), 1 if number == 12 else number + 1,
                       1, tzinfo=REPORT_ZONE)
    except ValueError:
        raise HTTPException(400, "Choose a valid month.")
    return start, end


def expense_data(row):
    return {"id": row.id, "incurred_on": row.incurred_on.isoformat(),
            "shop_slug": row.shop_slug, "provider": row.provider,
            "description": row.description, "reference": row.reference,
            "amount_cents": row.amount_cents, "is_void": row.is_void}


@router.post("/expenses")
def add_expense(payload: ExpenseInput, user=Depends(require_business_admin),
                db: Session = Depends(get_db)):
    slug = (payload.shop_slug or "").strip() or None
    if slug and not db.query(Shop).filter(Shop.slug == slug).first():
        raise HTTPException(404, "Shop not found.")
    if payload.incurred_on > datetime.now(REPORT_ZONE).date():
        raise HTTPException(400, "Record incurred costs, not future estimates.")
    description, reference = payload.description.strip(), payload.reference.strip()
    if not description or not reference:
        raise HTTPException(400, "Description and a unique invoice or transaction reference are required.")
    cents = int(payload.amount * 100) * (-1 if payload.kind == "credit" else 1)
    reference_key = f"{payload.provider}:{reference.casefold()}"
    existing = db.query(BusinessExpense).filter(
        BusinessExpense.request_id == payload.request_id).first()
    if existing:
        if (existing.incurred_on != payload.incurred_on or existing.shop_slug != slug
            or existing.provider != payload.provider or existing.description != description
            or existing.reference != reference or existing.amount_cents != cents):
            raise HTTPException(409, "This saved request has different details. Start a new entry.")
        return {"success": True, "expense": expense_data(existing)}
    row = BusinessExpense(request_id=payload.request_id, reference_key=reference_key,
        incurred_on=payload.incurred_on, shop_slug=slug, provider=payload.provider,
        description=description, reference=reference, amount_cents=cents, created_by=user.id)
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except IntegrityError:
        db.rollback()
        # A network retry or concurrent click must not create another expense.
        existing = db.query(BusinessExpense).filter(
            BusinessExpense.request_id == payload.request_id).first()
        if existing:
            return add_expense(payload, user, db)
        raise HTTPException(409, "That provider/reference is already recorded. Use a unique reference for each line.")
    return {"success": True, "expense": expense_data(row)}


@router.patch("/expenses/{expense_id}/void")
def void_expense(expense_id: str, user=Depends(require_business_admin),
                 db: Session = Depends(get_db)):
    row = db.get(BusinessExpense, expense_id)
    if not row:
        raise HTTPException(404, "Expense not found.")
    if not row.is_void:
        row.is_void = True
        row.voided_by = user.id
        row.voided_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"success": True}


class ReportIncomplete(Exception):
    pass


class StripeReader:
    """Per-request credentials and bounded, fully paginated read-only requests."""
    def __init__(self, key):
        self.client = stripe.StripeClient(key, max_network_retries=0,
            http_client=stripe.RequestsClient(timeout=8))
        self.v1 = self.client.v1
        self.deadline = time.monotonic() + 40
        self.cache = {}

    def check(self):
        if time.monotonic() > self.deadline:
            raise ReportIncomplete("Stripe lookup exceeded the report time limit.")

    def get(self, resource, identity):
        if not identity:
            return None
        if not isinstance(identity, str):
            return identity
        cache_key = (resource, identity)
        if cache_key not in self.cache:
            self.check()
            self.cache[cache_key] = getattr(self.v1, resource).retrieve(identity)
        return self.cache[cache_key]

    def pages(self, resource, parameters):
        parameters = dict(parameters, limit=100)
        for _ in range(50):
            self.check()
            page = getattr(self.v1, resource).list(parameters)
            rows = obj(page, "data", [])
            yield from rows
            if not obj(page, "has_more", False):
                return
            if not rows:
                raise ReportIncomplete("Stripe returned an incomplete page.")
            parameters["starting_after"] = oid(rows[-1])
        raise ReportIncomplete("Stripe activity exceeded the report size limit.")


def invoice_for_charge(reader, charge):
    # Legacy Stripe versions include charge.invoice. Current versions use Invoice Payments.
    invoice = obj(charge, "invoice")
    if invoice:
        return reader.get("invoices", invoice)
    intent_id = oid(obj(charge, "payment_intent"))
    if intent_id:
        payments = list(reader.pages("invoice_payments", {
            "payment": {"type": "payment_intent", "payment_intent": intent_id},
            "status": "paid"}))
        invoices = {oid(obj(payment, "invoice")) for payment in payments}
        if len(invoices) == 1:
            return reader.get("invoices", next(iter(invoices)))
    return None


def subscription_shop(reader, charge, by_customer):
    shop = by_customer.get(oid(obj(charge, "customer")))
    if not shop:
        return None, None
    invoice = invoice_for_charge(reader, charge)
    if not invoice or oid(obj(invoice, "customer")) != shop.stripe_customer_id:
        raise ReportIncomplete("A shop payment could not be verified as subscription revenue.")
    details = obj(obj(invoice, "parent", {}) or {}, "subscription_details", {}) or {}
    subscription_id = oid(obj(invoice, "subscription")) or oid(obj(details, "subscription"))
    if not subscription_id:
        raise ReportIncomplete("A shop invoice has no verifiable subscription.")
    if subscription_id != shop.stripe_subscription_id:
        # Historical subscriptions remain reportable after a shop changes subscriptions.
        subscription = reader.get("subscriptions", subscription_id)
        metadata = obj(subscription, "metadata", {}) or {}
        if (oid(obj(subscription, "customer")) != shop.stripe_customer_id
            or obj(metadata, "shop_id") != str(shop.id)):
            raise ReportIncomplete("A historical subscription could not be matched to a shop.")
    return shop, invoice


def tax_share(invoice, signed_amount):
    taxes = obj(invoice, "total_taxes")
    if taxes is None:
        taxes = obj(invoice, "total_tax_amounts")
    tax = sum(int(obj(item, "amount", 0)) for item in (taxes or []))
    if taxes is None:
        tax = int(obj(invoice, "tax", 0) or 0)
    total = int(obj(invoice, "total", 0) or 0)
    if not tax or total <= 0:
        return 0
    return int((Decimal(signed_amount) * Decimal(tax) / Decimal(total)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP))


def blank_row(shop):
    return {"slug": shop.slug, "name": shop.name, "subscription_status": shop.subscription_status or "not_started",
        "ai_enabled": bool(shop.ai_voice_enabled), "trial_ends_at": shop.trial_ends_at.isoformat() if shop.trial_ends_at else None,
        "current_monthly_cents": None, "subscription_collected_cents": 0,
        "subscription_refunds_cents": 0, "subscription_tax_cents": 0,
        "transaction_fee_collected_cents": 0, "transaction_fee_refunds_cents": 0,
        "stripe_cost_cents": 0, "adjustments_cents": 0,
        "highlevel_recorded_cents": 0, "other_recorded_cents": 0}


def apply_transaction(reader, transaction, rows, by_customer, by_account):
    kind = obj(transaction, "type")
    if kind not in {"charge", "payment", "refund", "payment_refund", "refund_failure", "application_fee",
                    "application_fee_refund", "adjustment"}:
        return
    source = obj(transaction, "source")
    amount, fees = int(obj(transaction, "amount", 0)), int(obj(transaction, "fee", 0))
    invoice = None
    shop = None
    bucket = None
    if kind in {"application_fee", "application_fee_refund"}:
        source = source if not isinstance(source, str) else reader.get("application_fees", source)
        if kind == "application_fee_refund":
            if obj(source, "object") != "fee_refund":
                raise ReportIncomplete("A platform fee refund could not be read.")
            source = reader.get("application_fees", obj(source, "fee"))
        shop = by_account.get(oid(obj(source, "account")))
        bucket = "transaction_fee_collected_cents" if amount >= 0 else "transaction_fee_refunds_cents"
    else:
        if kind in {"refund", "payment_refund", "refund_failure"}:
            refund = reader.get("refunds", source)
            charge = reader.get("charges", obj(refund, "charge"))
        elif kind == "adjustment":
            # Only identifiable subscription disputes belong in this report.
            if obj(source, "object") != "dispute":
                return
            charge = reader.get("charges", obj(source, "charge"))
        else:
            charge = reader.get("charges", source)
        shop, invoice = subscription_shop(reader, charge, by_customer)
        if kind == "adjustment":
            bucket = "adjustments_cents"
        elif kind == "refund_failure":
            bucket = "subscription_refunds_cents"
        else:
            bucket = "subscription_collected_cents" if amount >= 0 else "subscription_refunds_cents"
    if not shop:
        return  # Other businesses sharing the Stripe account are excluded.
    if obj(transaction, "currency") != "usd":
        raise ReportIncomplete("A shop transaction needs currency conversion; it was not added to USD totals.")
    row = rows[shop.slug]
    row[bucket] += (-amount if kind == "refund_failure" else amount if bucket == "adjustments_cents" else abs(amount))
    row["stripe_cost_cents"] += fees
    if invoice:
        row["subscription_tax_cents"] += tax_share(invoice, amount)


def current_plan(reader, shop, row):
    if not shop.stripe_subscription_id:
        row["current_monthly_cents"] = 0
        return
    sub = reader.get("subscriptions", shop.stripe_subscription_id)
    if oid(obj(sub, "customer")) != shop.stripe_customer_id:
        raise ReportIncomplete("A current subscription does not match its shop.")
    row["subscription_status"] = obj(sub, "status")
    trial_end = obj(sub, "trial_end")
    row["trial_ends_at"] = datetime.fromtimestamp(trial_end, REPORT_ZONE).isoformat() if trial_end else None
    items = obj(sub, "items", {})
    if obj(items, "has_more", False):
        raise ReportIncomplete("A subscription has more items than the report can verify.")
    total = 0
    for item in obj(items, "data", []):
        price = obj(item, "price", {})
        recurring = obj(price, "recurring", {}) or {}
        if (obj(price, "currency") != "usd" or obj(price, "unit_amount") is None
            or obj(recurring, "interval") != "month" or obj(recurring, "interval_count", 1) != 1
            or obj(recurring, "usage_type") != "licensed"):
            raise ReportIncomplete("A plan uses pricing that cannot be shown as a fixed USD monthly amount.")
        total += int(obj(price, "unit_amount")) * int(obj(item, "quantity", 0) or 0)
    row["current_monthly_cents"] = total if row["subscription_status"] in {"active", "trialing", "past_due", "unpaid"} else 0


@router.get("/report")
def business_report(response: Response, month: str | None = None,
                    user=Depends(require_business_admin), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    month = month or datetime.now(REPORT_ZONE).strftime("%Y-%m")
    start, end = month_bounds(month)
    shops = db.query(Shop).order_by(Shop.name, Shop.slug).all()
    rows = {shop.slug: blank_row(shop) for shop in shops}
    by_customer = {shop.stripe_customer_id: shop for shop in shops if shop.stripe_customer_id}
    by_account = {shop.stripe_connect_account_id: shop for shop in shops if shop.stripe_connect_account_id}
    expenses = db.query(BusinessExpense).filter(
        BusinessExpense.incurred_on >= start.date(), BusinessExpense.incurred_on < end.date()
    ).order_by(BusinessExpense.incurred_on.desc(), BusinessExpense.created_at.desc()).all()
    shared = []
    for expense in expenses:
        if expense.is_void:
            continue
        if expense.shop_slug in rows:
            key = "highlevel_recorded_cents" if expense.provider == "highlevel" else "other_recorded_cents"
            rows[expense.shop_slug][key] += expense.amount_cents
        else:
            shared.append(expense_data(expense))
    warnings = []
    complete = True
    key = os.getenv("STRIPE_SECRET_KEY", "")
    mode = "test" if key.startswith(("sk_test_", "rk_test_")) else "live" if key.startswith(("sk_live_", "rk_live_")) else "unknown"
    if len(by_customer) != sum(bool(shop.stripe_customer_id) for shop in shops) or len(by_account) != sum(bool(shop.stripe_connect_account_id) for shop in shops):
        complete = False
        warnings.append("Stripe account identifiers are shared by more than one shop. Resolve the mapping before using totals.")
    elif key:
        try:
            reader = StripeReader(get_stripe_secret_key())
            for transaction in reader.pages("balance_transactions", {
                "created": {"gte": int(start.timestamp()), "lt": int(end.timestamp())},
                "expand": ["data.source"]}):
                apply_transaction(reader, transaction, rows, by_customer, by_account)
            for shop in shops:
                current_plan(reader, shop, rows[shop.slug])
        except (stripe.StripeError, ReportIncomplete, HTTPException, ValueError, TypeError):
            complete = False
            warnings.append("Stripe could not fully verify this report. Financial totals are hidden; refresh to try again.")
    else:
        complete = False
        warnings.append("Stripe is not configured. Financial totals are hidden.")
    financial_keys = ("subscription_collected_cents", "subscription_refunds_cents", "subscription_tax_cents",
        "transaction_fee_collected_cents", "transaction_fee_refunds_cents", "stripe_cost_cents", "adjustments_cents")
    for row in rows.values():
        row["revenue_cents"] = (row["subscription_collected_cents"] - row["subscription_refunds_cents"]
            - row["subscription_tax_cents"] + row["transaction_fee_collected_cents"]
            - row["transaction_fee_refunds_cents"] + row["adjustments_cents"]) if complete else None
        row["remaining_cents"] = (row["revenue_cents"] - row["stripe_cost_cents"]
            - row["highlevel_recorded_cents"] - row["other_recorded_cents"]) if complete else None
        if not complete:
            for field in financial_keys:
                row[field] = None
            row["current_monthly_cents"] = None
    totals = {field: sum(row[field] for row in rows.values()) if complete else None
              for field in (*financial_keys, "revenue_cents", "remaining_cents")}
    totals["recorded_shop_cost_cents"] = sum(row["highlevel_recorded_cents"] + row["other_recorded_cents"] for row in rows.values())
    totals["shared_expense_cents"] = sum(item["amount_cents"] for item in shared)
    totals["remaining_after_shared_cents"] = totals["remaining_cents"] - totals["shared_expense_cents"] if complete else None
    totals["active_monthly_cents"] = sum(row["current_monthly_cents"] or 0 for row in rows.values() if row["subscription_status"] == "active") if complete else None
    return {"success": True, "month": month, "currency": "usd", "timezone": str(REPORT_ZONE),
        "checked_at": datetime.now(timezone.utc).isoformat(), "stripe_mode": mode,
        "stripe_complete": complete, "warnings": warnings, "shops": list(rows.values()),
        "totals": totals, "expenses": [expense_data(item) for item in expenses],
        "shared_expenses": shared, "costs_complete": False,
        "cost_note": "HighLevel and operating costs are recorded from invoices or usage statements. They are not automatically synced yet. Remaining amounts exclude unrecorded costs.",
        "basis_note": "USD cash activity by Stripe balance transaction date, in Eastern time. Subscription refunds and platform fee refunds reduce revenue in the month recorded. Subscription tax is excluded proportionally to each payment or refund. Shop service sales are excluded. Stripe costs include fees attached to matched transactions; separate platform charges need an expense entry. Plan amounts are current list prices before discounts or tax, separate from collections."} 
