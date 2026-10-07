"""Private cash-activity reporting. Does not change subscriptions or payments."""
import os
import json
from urllib import error as url_error, request as url_request
from urllib.parse import urlencode
import re
import time
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Literal
from zoneinfo import ZoneInfo

import stripe
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.message_tracking import sms_reference, sms_shop_matches, tracking_summary
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
    provider: Literal["highlevel", "highlevel_base", "railway", "vercel", "domain", "other"]
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


def highlevel_usage_category(description):
    text = description.casefold()
    # Wallet funding is a transfer, not an additional service cost.
    if re.search(r"recharg|top[ -]?up|wallet funding|fund(?:ing)? (?:the )?wallet|wallet transfer", text):
        return None
    for pattern, category in (
        (r"voiceai|voice ai", "Voice AI"),
        (r"sms carrier", "SMS carrier fees"),
        (r"(?:outbound|inbound) sms", "SMS"),
        (r"recording.*storage", "Recording storage"),
        (r"call recording", "Call recording"),
        (r"text to speech|amazon polly", "Text to speech"),
        (r"monthly charge for.*phone number", "Phone numbers"),
        (r"voice minutes|(?:inbound|outbound) call|call (?:charge|usage)", "Phone calls"),
        (r"a2p|registration fee", "Messaging registration"),
        (r"email", "Email"),
    ):
        if re.search(pattern, text):
            return category
    return "Unclassified"


def voice_billing_reference(description):
    match = re.fullmatch(r"voiceAI ref:\s*([A-Za-z0-9_-]+)\s*", description, re.I)
    return match.group(1) if match else None


def voice_shop_matches(location, descriptions, shops):
    """Exact provider call/message IDs only. Never infer ownership from caller numbers."""
    wanted = {ref for text in descriptions if (ref := voice_billing_reference(text))}
    token = (os.getenv("HIGHLEVEL_API_TOKEN") or "").strip()
    if not wanted:
        return {}, "not_needed"
    if not token:
        return {}, "not_configured"
    by_agent = {}
    for shop in shops:
        if shop.highlevel_agent_id and shop.highlevel_location_id == location:
            by_agent.setdefault(shop.highlevel_agent_id, set()).add(shop.slug)
    candidates = {}
    seen_calls = set()
    deadline = time.monotonic() + 8
    state = "partial"
    try:
        # Search newest-first without a call-date restriction: billing can settle late.
        # Any unsearched history remains unassigned. No partial financial totals result.
        for page in range(1, 21):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            query = urlencode({"locationId": location, "page": page, "pageSize": 50,
                               "sortBy": "createdAt", "sort": "descend"})
            req = url_request.Request(
                "https://services.leadconnectorhq.com/voice-ai/dashboard/call-logs?" + query,
                headers={"Authorization": f"Bearer {token}", "Version": "v3", "Accept": "application/json"})
            with url_request.urlopen(req, timeout=min(4, remaining)) as reply:
                raw = reply.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ValueError("Oversized call page")
            container = json.loads(raw.decode())
            if isinstance(container, dict) and "callLogs" not in container and isinstance(container.get("data"), dict):
                container = container["data"]
            logs = container.get("callLogs") if isinstance(container, dict) else None
            if not isinstance(logs, list) or len(logs) > 50:
                raise ValueError("Invalid call page")
            if not logs:
                state = "connected"
                break
            for log in logs:
                if not isinstance(log, dict) or not isinstance(log.get("id"), str) or not isinstance(log.get("agentId"), str):
                    raise ValueError("Invalid call identity")
                if log["id"] in seen_calls:
                    raise ValueError("Repeated call page")
                seen_calls.add(log["id"])
                if log.get("locationId") and log["locationId"] != location:
                    raise ValueError("Wrong call location")
                slugs = by_agent.get(log["agentId"], {None})
                for identity in {log["id"], log.get("messageId")}:
                    if identity in wanted:
                        candidates.setdefault(identity, set()).update(slugs)
                # Caller numbers, transcripts and summaries are never stored or returned.
        matches = {identity: next(iter(slugs)) for identity, slugs in candidates.items()
                   if len(slugs) == 1 and None not in slugs}
        return matches, state
    except url_error.HTTPError as failure:
        return {}, "permission_required" if failure.code in {401, 403} else "unavailable"
    except (url_error.URLError, TimeoutError, OSError, ValueError, TypeError, UnicodeError):
        return {}, "unavailable"


def highlevel_month_usage(start, end, shops, db=None):
    token = (os.getenv("HIGHLEVEL_AGENCY_API_TOKEN") or "").strip()
    company = (os.getenv("HIGHLEVEL_COMPANY_ID") or "").strip()
    location = (os.getenv("HIGHLEVEL_LOCATION_ID") or "").strip()
    empty = {"status": "not_configured", "complete": False, "location_id": location,
             "total_cents": None, "shared_cents": None, "shop_cents": {},
             "categories": [], "shared_categories": [], "transaction_count": 0,
             "unclassified_count": 0, "excluded_funding_count": 0}
    if not token or not all(re.fullmatch(r"[a-zA-Z0-9_-]{8,100}", v) for v in (company, location)):
        return empty
    from datetime import timedelta
    cutoff = min(end, datetime.now(timezone.utc))
    if cutoff <= start:
        return {**empty, "status": "connected", "complete": True, "total_cents": 0,
                "shared_cents": 0, "shop_cents": {shop.slug: 0 for shop in shops},
                "checked_at": datetime.now(timezone.utc).isoformat()}
    utc_text = lambda value: value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    deadline = time.monotonic() + 12
    seen = set()
    records = []
    offset = 0
    try:
        # A fixed upper bound prevents new transactions from shifting later pages.
        for page in range(10):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("Lookup deadline")
            payload = {"skip": offset, "limit": 1000, "timezone": "America/New_York",
                       "filters": {"locationId": location, "settlementTime": {
                           "from": utc_text(start), "to": utc_text(cutoff - timedelta(milliseconds=1))}}}
            req = url_request.Request(
                f"https://services.leadconnectorhq.com/saas/companies/{company}/wallet-transactions",
                data=json.dumps(payload).encode(), method="POST",
                headers={"Authorization": f"Bearer {token}", "Version": "v3",
                         "Accept": "application/json", "Content-Type": "application/json"})
            with url_request.urlopen(req, timeout=min(5, remaining)) as reply:
                raw = reply.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ValueError("Oversized page")
            data = json.loads(raw.decode())
            container = data if isinstance(data, dict) else {}
            if "transactions" not in container and isinstance(container.get("data"), dict):
                container = container["data"]
            rows = container.get("transactions")
            if not isinstance(rows, list) or len(rows) > 1000:
                raise ValueError("Invalid page")
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
                    raise ValueError("Invalid transaction")
                # Duplicate/repeated pages cannot be presented as a complete monthly report.
                if row["id"] in seen:
                    raise ValueError("Repeated transaction")
                seen.add(row["id"])
                if row.get("locationId") and row["locationId"] != location:
                    raise ValueError("Wrong location")
                if row.get("currency") and str(row["currency"]).lower() != "usd":
                    raise ValueError("Non USD transaction")
                stamp = datetime.fromisoformat(str(row.get("settlementTime", "")).replace("Z", "+00:00"))
                # Older wallet records use UTC timestamps without an explicit offset.
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                if not start <= stamp < cutoff:
                    raise ValueError("Transaction outside requested range")
                amount = Decimal(str(row.get("amount")))
                if not amount.is_finite() or abs(amount) > Decimal("1000000"):
                    raise ValueError("Invalid amount")
                description = row.get("description")
                if not isinstance(description, str):
                    raise ValueError("Missing description")
                records.append((row, amount, description))
            # Continue until an empty page, even if HighLevel caps pages below our requested limit.
            if not rows:
                break
            offset += len(rows)
        else:
            raise ValueError("Monthly page limit")
        phones = {}
        shared_number = re.sub(r"\D", "", os.getenv("HIGHLEVEL_SMS_FROM_NUMBER") or "+12405949454")
        if len(shared_number) == 10:
            shared_number = "1" + shared_number
        for shop in shops:
            digits = re.sub(r"\D", "", shop.highlevel_phone_number or "")
            if len(digits) == 10:
                digits = "1" + digits
            if digits and digits != shared_number and (not shop.highlevel_location_id or shop.highlevel_location_id == location):
                phones.setdefault(digits, []).append(shop.slug)
        message_matches = {}
        tracking_available = db is not None
        if db is not None:
            try:
                message_matches = sms_shop_matches(db, location, [text for _, _, text in records], shops)
            except Exception:
                # Preserve known total costs, but do not guess allocation.
                db.rollback()
                tracking_available = False
        voice_matches, voice_status = voice_shop_matches(location, [text for _, _, text in records], shops)
        matched_voice = unmatched_voice = matched_numbers = 0
        matched_sms = unmatched_sms = 0
        grouped = {}
        ignored = unknown = 0
        for row, amount, description in records:
            category = highlevel_usage_category(description)
            if category is None:
                ignored += 1
                continue
            # A positive wallet credit is not automatically a refund of service usage.
            # Only explicit service refunds/reimbursements offset recognized costs.
            if category == "Unclassified" or (amount > 0 and not re.search(r"refund|reimburse", description, re.I)):
                if amount != 0:
                    unknown += 1
                continue
            slug = None
            if category == "Phone numbers":
                number = re.search(r"phone number\s+(\+?[\d()-]+)", description, re.I)
                digits = re.sub(r"\D", "", number.group(1)) if number else ""
                if len(digits) == 10:
                    digits = "1" + digits
                candidates = phones.get(digits, [])
                if len(candidates) == 1:
                    slug = candidates[0]
                    matched_numbers += 1
            voice_reference = voice_billing_reference(description)
            if category == "Voice AI" and voice_reference:
                slug = voice_matches.get(voice_reference)
                if slug:
                    matched_voice += 1
                else:
                    unmatched_voice += 1
            reference = sms_reference(description)
            if category == "SMS" and reference:
                slug = message_matches.get(reference)
                if slug:
                    matched_sms += 1
                else:
                    unmatched_sms += 1
            # Aggregated carrier fees, inbound usage, emails and unmatched calls stay shared.
            key = (slug, category)
            grouped[key] = grouped.get(key, Decimal(0)) - amount
        cents = lambda value: int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        exact_total = sum(grouped.values(), Decimal(0))
        shop_cents = {shop.slug: cents(sum((value for (slug, _), value in grouped.items()
                                          if slug == shop.slug), Decimal(0))) for shop in shops}
        total_cents = cents(exact_total)
        # Keep displayed shop/shared totals reconciled to the rounded overall total.
        shared_cents = total_cents - sum(shop_cents.values())
        categories = []
        for category in sorted({category for _, category in grouped}):
            categories.append({"category": category, "amount_cents": cents(sum(
                (value for (_, name), value in grouped.items() if name == category), Decimal(0)))})
        shared_categories = [{"category": category, "amount_cents": cents(value)}
                             for (slug, category), value in sorted(grouped.items(), key=lambda item: item[0][1])
                             if slug is None]
        return {**empty, "status": "connected", "complete": unknown == 0,
                "total_cents": total_cents, "shared_cents": shared_cents, "shop_cents": shop_cents,
                "categories": categories, "shared_categories": shared_categories,
                "transaction_count": len(records), "unclassified_count": unknown,
                "matched_sms_transactions": matched_sms, "unmatched_sms_transactions": unmatched_sms,
                "message_tracking_available": tracking_available,
                "voice_attribution_status": voice_status,
                "matched_voice_transactions": matched_voice,
                "unmatched_voice_transactions": unmatched_voice,
                "matched_number_transactions": matched_numbers,
                "excluded_funding_count": ignored, "checked_at": datetime.now(timezone.utc).isoformat(),
                "through": cutoff.isoformat(), "basis": "USD wallet charges by settlement time; sub-cent amounts are rounded only after aggregation."}
    except (url_error.URLError, TimeoutError, OSError, ValueError, TypeError, InvalidOperation, UnicodeError):
        # Never publish a first-page or partial total as the monthly cost.
        return {**empty, "status": "unavailable"}


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
    highlevel = highlevel_month_usage(start, end, shops, db)
    shared = []
    suppressed = []
    for expense in expenses:
        if expense.is_void:
            continue
        if expense.provider == "highlevel" and highlevel["status"] == "connected":
            suppressed.append(expense.id)
            continue  # Preserve legacy entries in audit history; avoid counting wallet usage twice.
        if expense.shop_slug in rows:
            key = "highlevel_recorded_cents" if expense.provider == "highlevel" else "other_recorded_cents"
            rows[expense.shop_slug][key] += expense.amount_cents
        else:
            shared.append(expense_data(expense))
    warnings = []
    if highlevel["status"] == "unavailable":
        warnings.append("HighLevel costs could not be fully refreshed. Remaining totals are hidden; refresh to try again.")
    if highlevel.get("voice_attribution_status") == "permission_required":
        warnings.append("Voice AI cost matching needs the voice-ai-dashboard.readonly permission on the HighLevel location integration. Voice charges remain shared until access is available.")
    if highlevel.get("voice_attribution_status") in {"unavailable", "partial", "not_configured"}:
        warnings.append("Some Voice AI charges could not be matched to call logs and remain shared. Known wallet costs are still included.")
    if highlevel["unclassified_count"]:
        warnings.append("Some HighLevel transactions need classification. Known costs are shown, but remaining totals are hidden.")
    if suppressed:
        warnings.append("Legacy manual HighLevel entries are excluded while wallet costs are connected to prevent double counting. Record the separate agency subscription as HighLevel base plan.")
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
        row["highlevel_live_cents"] = highlevel["shop_cents"].get(row["slug"]) if highlevel["status"] == "connected" else None
        row["highlevel_shop_attribution_complete"] = False
        row["revenue_cents"] = (row["subscription_collected_cents"] - row["subscription_refunds_cents"]
            - row["subscription_tax_cents"] + row["transaction_fee_collected_cents"]
            - row["transaction_fee_refunds_cents"] + row["adjustments_cents"]) if complete else None
        row["remaining_cents"] = (row["revenue_cents"] - row["stripe_cost_cents"]
            - row["highlevel_recorded_cents"] - (row["highlevel_live_cents"] or 0) - row["other_recorded_cents"]) if complete and highlevel["status"] != "unavailable" and not highlevel["unclassified_count"] else None
        if not complete:
            for field in financial_keys:
                row[field] = None
            row["current_monthly_cents"] = None
    totals = {field: sum(row[field] for row in rows.values()) if complete and all(row[field] is not None for row in rows.values()) else None
              for field in (*financial_keys, "revenue_cents", "remaining_cents")}
    totals["recorded_shop_cost_cents"] = sum(row["highlevel_recorded_cents"] + row["other_recorded_cents"] for row in rows.values())
    totals["highlevel_live_cents"] = highlevel["total_cents"]
    totals["highlevel_shared_cents"] = highlevel["shared_cents"]
    totals["shared_expense_cents"] = sum(item["amount_cents"] for item in shared) + (highlevel["shared_cents"] or 0)
    totals["remaining_after_shared_cents"] = totals["remaining_cents"] - totals["shared_expense_cents"] if totals["remaining_cents"] is not None else None
    totals["active_monthly_cents"] = sum(row["current_monthly_cents"] or 0 for row in rows.values() if row["subscription_status"] == "active") if complete else None
    return {"success": True, "month": month, "currency": "usd", "timezone": str(REPORT_ZONE),
        "checked_at": datetime.now(timezone.utc).isoformat(), "stripe_mode": mode,
        "stripe_complete": complete, "warnings": warnings, "shops": list(rows.values()),
        "totals": totals, "highlevel": highlevel,
        "recent_outbound_messages": tracking_summary(db),
        "expenses": [{**expense_data(item), "excluded_from_totals": item.id in suppressed} for item in expenses],
        "shared_expenses": shared, "costs_complete": False,
        "cost_note": "HighLevel wallet usage refreshes with this report. Shared or unmatched usage is not assigned to individual shops. Agency subscription and other operating expenses require separate entries. Remaining amounts exclude unrecorded costs.",
        "basis_note": "USD cash activity by Stripe balance transaction date, in Eastern time. Subscription refunds and platform fee refunds reduce revenue in the month recorded. Subscription tax is excluded proportionally to each payment or refund. Shop service sales are excluded. Stripe costs include fees attached to matched transactions; separate platform charges need an expense entry. Plan amounts are current list prices before discounts or tax, separate from collections."}


# Read-only provider diagnostic. It does not import costs or alter financial totals.
def highlevel_diagnostic_redact(value, credential=""):
    sensitive = re.compile(r"secret|token|password|authorization|api.?key|credential|card.number|cvc|cvv", re.I)
    if isinstance(value, list):
        return [highlevel_diagnostic_redact(item, credential) for item in value]
    if isinstance(value, dict):
        header_name = str(value.get("key") or value.get("name") or "")
        return {key: "[REDACTED]" if sensitive.search(str(key)) or
                (key == "value" and sensitive.search(header_name)) else
                highlevel_diagnostic_redact(item, credential)
                for key, item in value.items()}
    if isinstance(value, str) and credential:
        return value.replace(credential, "[REDACTED]")
    return value


@router.get("/highlevel-test")
def test_highlevel_billing(response: Response, month: str | None = None,
                          user: User = Depends(require_business_admin)):
    response.headers["Cache-Control"] = "no-store"
    month = month or datetime.now(REPORT_ZONE).strftime("%Y-%m")
    start, end = month_bounds(month)
    token = (os.getenv("HIGHLEVEL_AGENCY_API_TOKEN") or "").strip()
    company = (os.getenv("HIGHLEVEL_COMPANY_ID") or "").strip()
    location = (os.getenv("HIGHLEVEL_LOCATION_ID") or "").strip()
    missing = [name for name, value in (("HIGHLEVEL_AGENCY_API_TOKEN", token),
               ("HIGHLEVEL_COMPANY_ID", company), ("HIGHLEVEL_LOCATION_ID", location)) if not value]
    if missing:
        raise HTTPException(503, {"message": "HighLevel billing configuration is incomplete.",
                                  "missing_variables": missing})
    if not all(re.fullmatch(r"[a-zA-Z0-9_-]{8,100}", value) for value in (company, location)):
        raise HTTPException(503, "HighLevel company or location ID has an invalid format.")
    # Company and location are server-configured. Browser input cannot select another business.
    # Use the documented v3 agency wallet API with a single bounded page for schema inspection.
    # The API to boundary is inclusive, so end at the last millisecond of the selected month.
    from datetime import timedelta
    utc_text = lambda value: value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    payload = {"skip": 0, "limit": 100, "timezone": "America/New_York",
               "filters": {"locationId": location, "settlementTime": {
                   "from": utc_text(start), "to": utc_text(end - timedelta(milliseconds=1))}}}
    provider_request = url_request.Request(
        f"https://services.leadconnectorhq.com/saas/companies/{company}/wallet-transactions",
        data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {token}", "Version": "v3",
                 "Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": "ChairTimeBusinessReport/1.0"})
    trace_headers = {}
    try:
        with url_request.urlopen(provider_request, timeout=20) as provider_response:
            status = provider_response.status
            trace_headers = {key: provider_response.headers.get(key) for key in
                             ("x-request-id", "x-trace-id", "cf-ray") if provider_response.headers.get(key)}
            raw = provider_response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise HTTPException(502, "HighLevel returned an oversized diagnostic response.")
        try:
            result = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise HTTPException(502, "HighLevel returned an invalid JSON response.")
    except url_error.HTTPError as failure:
        trace_headers = {key: failure.headers.get(key) for key in
                         ("x-request-id", "x-trace-id", "cf-ray") if failure.headers.get(key)}
        try:
            error_data = json.loads(failure.read(16_000).decode("utf-8"))
        except (ValueError, UnicodeError):
            error_data = {}
        safe_error = {key: error_data[key] for key in ("message", "error", "statusCode", "traceId", "requestId")
                      if isinstance(error_data, dict) and key in error_data}
        response.status_code = 502
        return {"success": False, "month": month, "highlevel_status": failure.code,
                "message": "HighLevel rejected the billing lookup. This does not change your report.",
                "highlevel_error": highlevel_diagnostic_redact(safe_error, token),
                "trace_headers": highlevel_diagnostic_redact(trace_headers, token)}
    except (url_error.URLError, TimeoutError, OSError):
        raise HTTPException(502, "HighLevel billing could not be reached. Retry this diagnostic later.")
    # Live HighLevel responses wrap transactions in data; also accept the documented shape.
    container = result if isinstance(result, dict) else {}
    transaction_path = "transactions"
    if "transactions" not in container and isinstance(container.get("data"), dict):
        container = container["data"]
        transaction_path = "data.transactions"
    transactions = container.get("transactions")
    valid = isinstance(transactions, list) and all(isinstance(item, dict) for item in transactions)
    if not valid:
        response.status_code = 502
    return {"success": valid, "highlevel_status": status, "month": month,
            "company_id": company, "location_id": location,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "request": payload, "trace_headers": highlevel_diagnostic_redact(trace_headers, token),
            "response_keys": sorted(result) if isinstance(result, dict) else [],
            "transaction_path": transaction_path if valid else None,
            "returned_count": len(transactions) if isinstance(transactions, list) else None,
            "transaction_fields": sorted({key for item in transactions for key in item}) if valid else [],
            "sample_transactions": highlevel_diagnostic_redact(transactions[:10], token) if valid else [],
            "message": "Diagnostic page only, not a complete cost report. Up to ten records are shown. No costs have been imported."
                       if valid else "The provider response did not match the documented transactions array.",
            # Never echo nested data here: it can repeat the full transaction page.
            "provider_metadata": highlevel_diagnostic_redact({key: value for key, value in result.items()
                                  if key not in ("transactions", "data")
                                  and isinstance(value, (str, int, float, bool, type(None)))}, token)
                                  if isinstance(result, dict) else {}}
