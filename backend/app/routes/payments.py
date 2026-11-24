"""One customer-approved Stripe Checkout payment per appointment."""
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import quote

import jwt
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from uuid import UUID
from typing import Literal
from zoneinfo import ZoneInfo

from app.database import get_db
from app.models import Appointment, Barber, Service, ServiceCatalog, Shop, User
from app.service_packages import (PackageOffer, PackageSale, PackageRedemption, PackageCheckout, DeletedPackageOffer, PackageExpiration, expiration_date, package_sales, available_sales,
    current_redemption, matching_offers, phone_key, reject_redeemed, timestamp)
from app.payment_records import ManualAppointmentPayment, ServicePayment, TerminalPaymentAttempt, PaymentLinkDelivery, ServicePaymentRefund
from app.routes.reminders import send_highlevel_sms
from app.routes.auth import get_current_user, get_jwt_secret
from app.routes.billing import get_stripe_secret_key

router = APIRouter()
SETTLED_STATUSES = {"paid", "partially_refunded", "refunded", "refund_pending"}


def value(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def object_id(obj):
    return obj if isinstance(obj, str) else value(obj, "id")


def require_payment_user(user):
    role = str(user.role or "").strip().lower()
    if not user.is_active or not user.shop_slug or not (
        role == "owner" or (role == "staff" and user.can_accept_payments)
    ):
        raise HTTPException(403, "You do not have permission to collect payments.")


def appointment_for_user(db, appointment_id, user):
    require_payment_user(user)
    # Every payment operation locks the same appointment in PostgreSQL.
    query = db.query(Appointment).filter(
        Appointment.id == appointment_id, Appointment.shop_slug == user.shop_slug
    )
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    appointment = query.first()
    if not appointment:
        raise HTTPException(404, "Appointment not found.")
    return appointment


def receipt_token(record):
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "purpose": "service_payment_receipt", "payment_id": record.id,
        "shop_slug": record.shop_slug, "iat": now,
        "exp": now + timedelta(days=2),
    }, get_jwt_secret(), algorithm="HS256")


def reconcile(db, record):
    """Never mark paid from a browser redirect or a client-supplied flag."""
    if record.status in SETTLED_STATUSES and record.payment_intent_id:
        reconcile_refunds(db, record)
        return
    terminal_attempt = db.get(TerminalPaymentAttempt, record.id)
    if terminal_attempt:
        if record.payment_intent_id:
            stripe.api_key = get_stripe_secret_key()
            intent = stripe.PaymentIntent.retrieve(
                record.payment_intent_id, stripe_account=record.account_id
            )
            verify_terminal_intent(record, intent)
            if record.status == "paid":
                reconcile_refunds(db, record)
        return
    if not record.session_id:
        return
    stripe.api_key = get_stripe_secret_key()
    session = stripe.checkout.Session.retrieve(
        record.session_id, stripe_account=record.account_id,
        expand=["payment_intent"],
    )
    metadata = value(session, "metadata", {}) or {}
    expected = {"purpose": "service_payment", "payment_id": record.id,
                "shop_slug": record.shop_slug, "appointment_id": record.appointment_id}
    if (any(value(metadata, k) != v for k, v in expected.items())
        or value(session, "mode") != "payment"
        or value(session, "amount_total") != record.amount_cents
        or value(session, "currency") != record.currency):
        raise HTTPException(409, "The Stripe payment does not match this appointment.")
    intent = value(session, "payment_intent")
    if value(session, "payment_status") == "paid":
        if (value(intent, "status") != "succeeded"
            or value(intent, "amount_received") != record.amount_cents
            or value(intent, "currency") != record.currency):
            raise HTTPException(409, "Stripe has not confirmed the full payment.")
        record.status = "paid"
        record.payment_intent_id = object_id(intent)
        record.paid_at = record.paid_at or datetime.now(timezone.utc).replace(tzinfo=None)
        record.checkout_url = None
        reconcile_refunds(db, record)
    elif value(session, "status") == "expired":
        record.status = "expired"
        record.checkout_url = None
    elif value(session, "status") == "complete":
        record.status = "processing"
    else:
        record.status = "unpaid"


def verify_terminal_intent(record, intent):
    metadata = value(intent, "metadata", {}) or {}
    expected = {"purpose": "service_payment_terminal", "payment_id": record.id,
                "shop_slug": record.shop_slug, "appointment_id": record.appointment_id}
    if (any(value(metadata, key) != item for key, item in expected.items())
        or object_id(intent) != record.payment_intent_id
        or value(intent, "amount") != record.amount_cents
        or value(intent, "currency") != record.currency
        or "card_present" not in value(intent, "payment_method_types", [])
        or (value(intent, "application_fee_amount") or 0) != record.fee_cents):
        raise HTTPException(409, "The Tap to Pay payment does not match this appointment.")
    status = value(intent, "status")
    if status == "succeeded":
        if value(intent, "amount_received") != record.amount_cents:
            raise HTTPException(409, "Stripe has not confirmed the full payment.")
        record.status = "paid"
        record.paid_at = record.paid_at or datetime.now(timezone.utc).replace(tzinfo=None)
        record.checkout_url = None
    elif status in {"processing", "requires_capture"}:
        record.status = "processing"
    elif status == "canceled":
        record.status = "canceled"
    else:
        record.status = "unpaid"


def reconcile_refunds(db, record):
    """Read actual connected-account refunds, including dashboard refunds."""
    stripe.api_key = get_stripe_secret_key()
    intent = stripe.PaymentIntent.retrieve(record.payment_intent_id,
        stripe_account=record.account_id, expand=["latest_charge"])
    metadata = value(intent, "metadata", {}) or {}
    if (object_id(intent) != record.payment_intent_id
        or value(intent, "status") != "succeeded"
        or value(intent, "amount_received") != record.amount_cents
        or value(intent, "currency") != record.currency
        or value(metadata, "payment_id") != record.id
        or value(metadata, "shop_slug") != record.shop_slug
        or value(metadata, "appointment_id") != record.appointment_id
        or value(metadata, "purpose") not in {"service_payment", "service_payment_terminal"}):
        raise HTTPException(409, "The Stripe payment does not match this appointment.")
    charge = value(intent, "latest_charge")
    if isinstance(charge, str):
        charge = stripe.Charge.retrieve(charge, stripe_account=record.account_id)
    if (not object_id(charge) or object_id(value(charge, "payment_intent")) != record.payment_intent_id
        or value(charge, "amount") != record.amount_cents
        or value(charge, "currency") != record.currency):
        raise HTTPException(409, "The Stripe charge does not match this payment.")
    snapshot = db.get(ServicePaymentRefund, record.id)
    if not snapshot:
        snapshot = ServicePaymentRefund(payment_id=record.id, refunded_cents=0, pending_cents=0)
        db.add(snapshot)
    refunded = value(charge, "amount_refunded", 0)
    if not isinstance(refunded, int) or not 0 <= refunded <= record.amount_cents:
        raise HTTPException(409, "Stripe returned an invalid refunded amount.")
    # The individual refund status determines completion; an initiated refund
    # must never be presented to the customer as money already returned.
    refunded = 0
    pending = 0
    refunds = stripe.Refund.list(charge=object_id(charge), limit=100, stripe_account=record.account_id)
    for refund in refunds.auto_paging_iter():
        if (object_id(value(refund, "charge")) != object_id(charge)
            or value(refund, "currency") != record.currency):
            raise HTTPException(409, "The refund does not match this payment.")
        amount = value(refund, "amount")
        status = value(refund, "status")
        if (not isinstance(amount, int) or amount <= 0
            or status not in {"pending", "requires_action", "succeeded", "failed", "canceled"}):
            raise HTTPException(409, "Stripe returned an unverified refund status.")
        if status == "succeeded":
            refunded += amount
        elif status in {"pending", "requires_action"}:
            pending += amount
        if value(value(refund, "metadata", {}) or {}, "chairtime_payment_id") == record.id:
            snapshot.refund_id = object_id(refund)
            snapshot.request_status = value(refund, "status")
    if refunded > record.amount_cents or pending > record.amount_cents - refunded:
        raise HTTPException(409, "Stripe returned an invalid pending refund amount.")
    snapshot.refunded_cents = refunded
    snapshot.pending_cents = pending
    unresolved = snapshot.requested_at and snapshot.request_status in {"requesting", "unknown", "succeeded"}
    record.status = ("refunded" if refunded == record.amount_cents else
        "refund_pending" if pending or unresolved else "partially_refunded" if refunded else "paid")
    record.checkout_url = None


def payment_data(record, db=None):
    snapshot = db.get(ServicePaymentRefund, record.id) if db and record else None
    return {
        "payment_status": record.status if record else "unpaid",
        "amount": f"{Decimal(record.amount_cents) / 100:.2f}" if record else None,
        "currency": record.currency if record else "usd",
        "service_name": record.service_name if record else None,
        "paid_at": record.paid_at.isoformat() if record and record.paid_at else None,
        "checkout_url": record.checkout_url if record and record.status == "unpaid" else None,
        "refunded_amount": f"{Decimal(snapshot.refunded_cents if snapshot else 0) / 100:.2f}",
        "refund_pending_amount": f"{Decimal(snapshot.pending_cents if snapshot else 0) / 100:.2f}",
        "refundable_amount": f"{Decimal(max(0, record.amount_cents - snapshot.refunded_cents - snapshot.pending_cents) if snapshot and record else record.amount_cents if record else 0) / 100:.2f}",
        "refund_request_status": snapshot.request_status if snapshot else None,
    }


def service_fee_cents(amount):
    try:
        bps = int(os.getenv("STRIPE_SERVICE_PLATFORM_FEE_BPS", "0"))
    except ValueError:
        bps = -1
    if not 0 <= bps < 10000:
        raise HTTPException(503, "The platform payment fee is not configured correctly.")
    return amount * bps // 10000


def stripe_failure():
    return HTTPException(502, "Stripe could not verify the payment. Please try again.")


@router.get("/appointments/{appointment_id}")
def get_payment(appointment_id: str, response: Response,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    appointment = appointment_for_user(db, appointment_id, user)
    service = db.query(Service).filter(
        Service.id == appointment.service_id, Service.shop_slug == user.shop_slug,
        Service.barber_id == appointment.barber_id,
    ).first()
    record = db.query(ServicePayment).filter(
        ServicePayment.appointment_id == appointment.id,
        ServicePayment.shop_slug == user.shop_slug,
    ).first()
    try:
        if record:
            reconcile(db, record)
        db.commit()
    except stripe.StripeError:
        db.rollback()
        raise stripe_failure()
    manual = db.get(ManualAppointmentPayment, appointment.id)
    offers = matching_offers(db, appointment)
    sales = available_sales(db, appointment, offers)
    zone = shop_zone(db, appointment.shop_slug)
    redemption = current_redemption(db, appointment)
    replaceable_checkout = bool(
        record and record.session_id and record.status in {"unpaid", "expired"}
        and not db.get(TerminalPaymentAttempt, record.id)
    )
    delivery = db.get(PaymentLinkDelivery, record.session_id) if record and record.session_id else None
    return {"success": True, "shop_slug": user.shop_slug,
            "can_refund": bool(str(user.role or "").lower() == "owner" and record and
                record.status in {"paid", "partially_refunded"} and not
                (db.get(ServicePaymentRefund, record.id) and db.get(ServicePaymentRefund, record.id).requested_at)),
            "uses_tap_to_pay": bool(record and db.get(TerminalPaymentAttempt, record.id)),
            "text_link_status": delivery.status if delivery else None,
            "text_link_recipient": delivery.recipient_last4 if delivery else None,
            "appointment_id": appointment.id, "customer_name": appointment.customer_name,
            "appointment_status": appointment.status,
            "package_paid": bool(redemption),
            "manual_payment_method": manual.method if manual else None,
            "package_offers": [offer_view(offer, db) for offer in offers if offer.sessions > 1 and not db.get(DeletedPackageOffer, offer.id)],
            "can_edit_package_expiration": user.role == "owner",
            "package_balances": [
                {"id": sale.id, "sessions_remaining": sale.sessions_remaining,
                 "purchased_at": sale.created_at.replace(tzinfo=timezone.utc).isoformat(),
                 "expires_at": terms.expires_at.replace(tzinfo=timezone.utc).isoformat() if terms else None,
                 "expiration_date": (terms.expires_at.replace(tzinfo=timezone.utc).astimezone(zone) - timedelta(microseconds=1)).date().isoformat() if terms else None,
                 "expired": bool(terms and terms.expires_at <= timestamp())}
                for sale, terms in package_sales(db, appointment, offers)
            ],
            "package_sessions_remaining": sum(sale.sessions_remaining for sale in sales),
            "can_redeem_package": bool(sales and not manual and not redemption and
                (not record or replaceable_checkout) and appointment.status not in {"completed", "canceled", "no_show"}),
            "package_replaces_payment_link": replaceable_checkout and record.status == "unpaid",
            "service_name": record.service_name if record else (service.name if service else None),
            "amount": f"{service.price:.2f}" if service else None,
            **{k: v for k, v in payment_data(record, db).items() if v is not None}}


@router.post("/appointments/{appointment_id}/checkout")
def create_service_checkout(appointment_id: str,
                            user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    appointment = appointment_for_user(db, appointment_id, user)
    reject_redeemed(db, appointment)
    if db.get(ManualAppointmentPayment, appointment.id):
        raise HTTPException(409, "Payment was already recorded for this appointment.")
    shop = db.query(Shop).filter(Shop.slug == user.shop_slug).first()
    if not shop or shop.payment_policy not in {"accept_cards", "card_required"}:
        raise HTTPException(409, "Enable credit card payments for this shop first.")
    if not shop.stripe_connect_account_id:
        raise HTTPException(409, "Connect this shop to Stripe first.")
    if appointment.status in {"canceled", "no_show"}:
        raise HTTPException(409, "Collect payment only for a confirmed or completed service.")
    service = db.query(Service).filter(
        Service.id == appointment.service_id, Service.shop_slug == shop.slug,
        Service.barber_id == appointment.barber_id,
    ).first()
    if not service:
        raise HTTPException(409, "This appointment's service could not be found.")
    stripe.api_key = get_stripe_secret_key()
    try:
        account = stripe.Account.retrieve(shop.stripe_connect_account_id)
        if not value(account, "charges_enabled", False):
            raise HTTPException(409, "This shop's Stripe account cannot accept payments yet.")
        record = db.query(ServicePayment).filter(
            ServicePayment.appointment_id == appointment.id
        ).first()
        if record and (record.shop_slug != shop.slug or record.account_id != shop.stripe_connect_account_id):
            raise HTTPException(409, "The payment account does not match this shop.")
        if not record:
            amount = int((Decimal(service.price) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            if amount < 50:
                raise HTTPException(400, "The service price must be at least $0.50.")
            record = ServicePayment(
                appointment_id=appointment.id, shop_slug=shop.slug,
                account_id=shop.stripe_connect_account_id, service_name=service.name,
                amount_cents=amount, fee_cents=service_fee_cents(amount),
                currency="usd", generation=1, status="unpaid", receipt_token="",
            )
            db.add(record)
            db.flush()
            record.receipt_token = receipt_token(record)
            # Persist the idempotency identity BEFORE requesting money from Stripe.
            db.commit()
            appointment_for_user(db, appointment_id, user)
            db.refresh(record)
        reconcile(db, record)
        if record.status in SETTLED_STATUSES:
            db.commit()
            return {"success": True, "shop_slug": shop.slug, **payment_data(record, db)}
        if db.get(TerminalPaymentAttempt, record.id):
            db.commit()
            raise HTTPException(409, "This appointment uses Tap to Pay. Resume it in the mobile app.")
        if record.status == "processing":
            db.commit()
            raise HTTPException(409, "This payment is still processing. Do not create another charge.")
        if record.status == "unpaid" and record.session_id and record.checkout_url:
            db.commit()
            return {"success": True, "shop_slug": shop.slug, **payment_data(record, db)}
        if record.status == "expired":
            record.generation += 1
            record.session_id = None
            record.receipt_token = receipt_token(record)
            record.status = "unpaid"
            db.commit()
            appointment_for_user(db, appointment_id, user)
            db.refresh(record)
            # A competing request may have created the replacement while waiting.
            if record.session_id:
                reconcile(db, record)
                db.commit()
                return {"success": True, "shop_slug": shop.slug, **payment_data(record, db)}
        base = (os.getenv("CHAIRTIME_FRONTEND_URL") or os.getenv("FRONTEND_URL") or "https://www.daytello.com").rstrip("/")
        return_url = f"{base}/{quote(shop.slug, safe='')}/payment?token={record.receipt_token}"
        metadata = {"purpose": "service_payment", "payment_id": record.id,
                    "shop_slug": shop.slug, "appointment_id": appointment.id}
        intent_data = {"metadata": metadata}
        if record.fee_cents:
            intent_data["application_fee_amount"] = record.fee_cents
        session = stripe.checkout.Session.create(
            mode="payment", payment_method_types=["card"],
            line_items=[{"price_data": {"currency": record.currency,
                "unit_amount": record.amount_cents,
                "product_data": {"name": f"{shop.name} - {record.service_name}"}}, "quantity": 1}],
            metadata=metadata, payment_intent_data=intent_data,
            success_url=return_url, cancel_url=return_url,
            stripe_account=record.account_id,
            idempotency_key=f"service-payment:{record.id}:{record.generation}",
        )
        record.session_id = object_id(session)
        record.checkout_url = value(session, "url")
        if not record.session_id or not record.checkout_url:
            raise HTTPException(502, "Stripe did not return a checkout link.")
        db.commit()
        return {"success": True, "shop_slug": shop.slug, **payment_data(record, db)}
    except stripe.StripeError:
        db.rollback()
        raise stripe_failure()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Another payment request is in progress. Please refresh.")


@router.post("/appointments/{appointment_id}/refund")
def refund_service_payment(appointment_id: str,
                           user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    if str(user.role or "").strip().lower() != "owner":
        raise HTTPException(403, "Only the shop owner can refund payments.")
    appointment = appointment_for_user(db, appointment_id, user)
    record = db.query(ServicePayment).filter(
        ServicePayment.appointment_id == appointment.id,
        ServicePayment.shop_slug == user.shop_slug,
    ).first()
    if not record:
        raise HTTPException(409, "No payment has been collected for this appointment.")
    try:
        reconcile(db, record)
        snapshot = db.get(ServicePaymentRefund, record.id)
        if record.status == "refunded" or (snapshot and snapshot.refund_id):
            db.commit()
            return {"success": True, "shop_slug": user.shop_slug,
                    "can_refund": False, **payment_data(record, db)}
        if snapshot and snapshot.pending_cents:
            db.commit()
            raise HTTPException(409, "A refund is already pending in Stripe. Do not submit another refund.")
        if not snapshot or record.status not in SETTLED_STATUSES:
            raise HTTPException(409, "Stripe must confirm payment before it can be refunded.")
        if snapshot.requested_at:
            # Stripe retains idempotency keys for at least 24 hours. Never
            # automatically resubmit an unresolved old request after that window.
            age = datetime.now(timezone.utc).replace(tzinfo=None) - snapshot.requested_at
            if age >= timedelta(hours=23) or snapshot.request_status in {"failed", "canceled"}:
                db.commit()
                raise HTTPException(409, "Check this refund in Stripe before proceeding. DayTello will not risk issuing a duplicate refund.")
        else:
            snapshot.requested_cents = record.amount_cents - snapshot.refunded_cents
            snapshot.requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
            snapshot.requested_by = user.id
            snapshot.request_status = "requesting"
            record.status = "refund_pending"
            # Persist the amount and idempotency identity before Stripe can act.
            db.commit()
            appointment_for_user(db, appointment_id, user)
            db.refresh(record)
            db.refresh(snapshot)
        parameters = {"payment_intent": record.payment_intent_id,
            "amount": snapshot.requested_cents,
            "metadata": {"chairtime_payment_id": record.id,
                         "shop_slug": record.shop_slug, "appointment_id": record.appointment_id}}
        if record.fee_cents:
            parameters["refund_application_fee"] = True
        refund = stripe.Refund.create(**parameters, stripe_account=record.account_id,
            idempotency_key=f"chairtime-service-refund:{record.id}")
        if (object_id(value(refund, "payment_intent")) != record.payment_intent_id
            or value(refund, "amount") != snapshot.requested_cents
            or value(refund, "currency") != record.currency or not object_id(refund)):
            snapshot.request_status = "unknown"
            db.commit()
            raise HTTPException(502, "The refund result could not be verified. Refresh its status before proceeding.")
        snapshot.refund_id = object_id(refund)
        snapshot.request_status = value(refund, "status", "pending")
        db.commit()
        appointment_for_user(db, appointment_id, user)
        db.refresh(record)
        reconcile(db, record)
        db.commit()
        return {"success": True, "shop_slug": user.shop_slug,
                "can_refund": False, **payment_data(record, db)}
    except stripe.StripeError:
        db.rollback()
        raise HTTPException(502, "Stripe could not confirm the refund. Refresh payment status before trying again; your refund request is protected against duplicate submission.")
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Another payment request is in progress. Please refresh.")


@router.post("/appointments/{appointment_id}/text-link")
def text_payment_link(appointment_id: str,
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    # Recipient and amount always come from this authenticated shop's appointment.
    appointment = appointment_for_user(db, appointment_id, user)
    reject_redeemed(db, appointment)
    if db.get(ManualAppointmentPayment, appointment.id):
        raise HTTPException(409, "Payment was already recorded for this appointment.")
    digits = "".join(c for c in appointment.customer_phone or "" if c.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise HTTPException(400, "Update the customer's US phone number on the appointment first.")
    checkout = create_service_checkout(appointment_id, user, db)
    if checkout.get("payment_status") in SETTLED_STATUSES:
        return checkout
    appointment = appointment_for_user(db, appointment_id, user)
    record = db.query(ServicePayment).filter(
        ServicePayment.appointment_id == appointment.id,
        ServicePayment.shop_slug == user.shop_slug,
    ).one()
    reconcile(db, record)
    if record.status in SETTLED_STATUSES:
        db.commit()
        return {"success": True, "shop_slug": user.shop_slug, **payment_data(record, db)}
    if record.status != "unpaid" or not record.checkout_url:
        raise HTTPException(409, "Refresh the payment status before sending a link.")
    if appointment.status in {"canceled", "no_show"}:
        raise HTTPException(409, "This appointment is canceled or marked no-show.")
    # Check the saved recipient again after reacquiring the appointment lock.
    latest = "".join(c for c in appointment.customer_phone or "" if c.isdigit())
    if latest not in {digits, "1" + digits}:
        raise HTTPException(409, "The customer's phone changed. Refresh before sending.")
    shop = db.query(Shop).filter(Shop.slug == user.shop_slug).one()
    delivery = db.get(PaymentLinkDelivery, record.session_id)
    if delivery and delivery.status == "sent":
        return {"success": True, "shop_slug": user.shop_slug,
                "text_link_status": "sent", "text_link_recipient": delivery.recipient_last4,
                **payment_data(record, db)}
    if delivery and delivery.status in {"sending", "unknown"}:
        raise HTTPException(409, "Text delivery is pending or unconfirmed. Check the customer's messages before attempting another send.")
    if not delivery:
        delivery = PaymentLinkDelivery(session_id=record.session_id, payment_id=record.id,
                                       recipient_last4=digits[-4:], status="sending")
        db.add(delivery)
    delivery.status = "sending"
    delivery.recipient_last4 = digits[-4:]
    message = (f"{shop.name}: Pay ${Decimal(record.amount_cents) / 100:.2f} for "
               f"{record.service_name} securely on your own device: {record.checkout_url} "
               "Reply STOP to unsubscribe.")
    # Reserve before the network call: a browser retry cannot send duplicate SMS.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A payment text is already being sent. Refresh its status.")
    try:
        result = send_highlevel_sms("+1" + digits, message, shop_id=shop.id,
                                   shop_slug=shop.slug, purpose="payment_link", source_id=record.id)
    except Exception:
        result = {"success": False, "step": "message"}
    if result.get("success"):
        delivery.status = "sent"
    elif result.get("step") in {"config", "contact", "contact_id", "tracking"}:
        delivery.status = "failed"  # No message request was made; retry is safe.
    else:
        delivery.status = "unknown"  # A timeout may occur after the provider accepted it.
    db.commit()
    if delivery.status != "sent":
        if delivery.status == "failed":
            raise HTTPException(502, "The payment text was not sent. Check the SMS configuration and try again.")
        raise HTTPException(502, "Text delivery could not be confirmed. Check messages before sending again.")
    return {"success": True, "shop_slug": user.shop_slug,
            "text_link_status": "sent", "text_link_recipient": delivery.recipient_last4,
            **payment_data(record, db)}


@router.get("/receipt")
def get_receipt(token: str, shop_slug: str, response: Response,
                db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    try:
        claims = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "This receipt link has expired or is invalid.")
    if claims.get("purpose") != "service_payment_receipt" or claims.get("shop_slug") != shop_slug:
        raise HTTPException(404, "Payment not found.")
    record = db.query(ServicePayment).filter(
        ServicePayment.id == claims.get("payment_id"), ServicePayment.shop_slug == shop_slug
    ).first()
    if not record:
        raise HTTPException(404, "Payment not found.")
    # Serialize receipt reconciliation with checkout creation and webhook delivery.
    query = db.query(Appointment).filter(Appointment.id == record.appointment_id)
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    query.first()
    db.refresh(record)
    try:
        reconcile(db, record)
        db.commit()
    except stripe.StripeError:
        db.rollback()
        raise stripe_failure()
    shop = db.query(Shop).filter(Shop.slug == shop_slug).first()
    return {"success": True, "shop_slug": shop_slug,
            "shop_name": shop.name if shop else "Your shop", **payment_data(record, db)}


@router.post("/webhook")
async def payment_webhook(request: Request, db: Session = Depends(get_db)):
    secret = os.getenv("STRIPE_CONNECT_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(503, "The service payment webhook is not configured.")
    try:
        event = stripe.Webhook.construct_event(
            await request.body(), request.headers.get("stripe-signature", ""), secret
        )
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid Stripe signature.")
    if value(event, "type") not in {
        "checkout.session.completed", "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed", "checkout.session.expired",
        "payment_intent.succeeded", "payment_intent.payment_failed",
        "payment_intent.processing", "payment_intent.canceled",
        "charge.refunded", "refund.created", "refund.updated", "refund.failed",
    }:
        return {"received": True}
    session = value(value(event, "data", {}), "object", {})
    event_type = str(value(event, "type", ""))
    if event_type.startswith("checkout.session.") and value(value(session, "metadata"), "purpose") == "package_payment":
        settle_package_checkout(db, session, value(event, "account"))
        return {"received": True}
    is_terminal = event_type.startswith("payment_intent.")
    is_refund = event_type.startswith(("charge.", "refund."))
    match_column = ServicePayment.payment_intent_id if is_terminal or is_refund else ServicePayment.session_id
    identity = object_id(value(session, "payment_intent")) if is_refund else object_id(session)
    record = db.query(ServicePayment).filter(
        match_column == identity,
        ServicePayment.account_id == value(event, "account"),
    ).first()
    if is_terminal and record and not db.get(TerminalPaymentAttempt, record.id):
        return {"received": True}
    if record:
        query = db.query(Appointment).filter(Appointment.id == record.appointment_id)
        if db.get_bind().dialect.name == "postgresql":
            query = query.with_for_update()
        query.first()
        db.refresh(record)
        try:
            reconcile(db, record)
            db.commit()
        except stripe.StripeError:
            db.rollback()
            raise stripe_failure()
    return {"received": True}



class PackageOfferInput(BaseModel):
    catalog_id: str
    name: str = Field(min_length=1, max_length=100, pattern=r"\S")
    sessions: int = Field(ge=2, le=1000)
    price_cents: int = Field(ge=50, le=99999999)
    expiration_duration: int = Field(ge=1, le=3650)
    expiration_unit: Literal["days", "months", "years"]


class PackageSaleInput(BaseModel):
    offer_id: str
    request_id: UUID


def offer_view(offer, db):
    terms = db.get(PackageExpiration, "offer:" + offer.id)
    return {**{key: getattr(offer, key) for key in ("id", "name", "catalog_id", "sessions", "price_cents")},
            "expiration_duration": terms.duration if terms else 1, "expiration_unit": terms.unit if terms else "years"}


@router.get("/packages")
def get_packages(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_payment_user(user)
    return [offer_view(offer, db) for offer in db.query(PackageOffer).filter_by(shop_slug=user.shop_slug)
            .filter(PackageOffer.sessions > 1, ~PackageOffer.id.in_(db.query(DeletedPackageOffer.offer_id))).order_by(PackageOffer.name)]


@router.post("/packages")
def create_package(payload: PackageOfferInput, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    require_payment_user(user)
    if user.role != "owner":
        raise HTTPException(403, "Only the owner can set up packages.")
    if not db.query(ServiceCatalog).filter_by(id=payload.catalog_id, shop_slug=user.shop_slug).first():
        raise HTTPException(404, "Service not found.")
    offer = PackageOffer(shop_slug=user.shop_slug, **payload.model_dump(exclude={"expiration_duration", "expiration_unit"}))
    db.add(offer)
    db.flush()
    save_offer_expiration(db, offer, payload)
    db.commit()
    return offer_view(offer, db)


def save_offer_expiration(db, offer, payload):
    db.merge(PackageExpiration(key="offer:" + offer.id, duration=payload.expiration_duration, unit=payload.expiration_unit))


def package_for_owner(db, user, offer_id):
    require_payment_user(user)
    if user.role != "owner":
        raise HTTPException(403, "Only the owner can manage packages.")
    offer = db.query(PackageOffer).filter_by(id=offer_id, shop_slug=user.shop_slug).with_for_update().first()
    if not offer:
        raise HTTPException(404, "Package not found.")
    return offer


@router.post("/packages/{offer_id}/edit")
def edit_package(offer_id: str, payload: PackageOfferInput, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    offer = package_for_owner(db, user, offer_id)
    if db.get(DeletedPackageOffer, offer.id):
        raise HTTPException(404, "Package not found.")
    if payload.catalog_id != offer.catalog_id:
        raise HTTPException(409, "Create a new package to use a different service.")
    offer.name = payload.name
    offer.sessions = payload.sessions
    offer.price_cents = payload.price_cents
    save_offer_expiration(db, offer, payload)
    db.commit()
    return offer_view(offer, db)


@router.post("/packages/{offer_id}/delete")
def delete_package(offer_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    offer = package_for_owner(db, user, offer_id)
    if not db.get(DeletedPackageOffer, offer.id):
        db.add(DeletedPackageOffer(offer_id=offer.id))
        db.commit()
    return {"success": True}


def settle_package_checkout(db, session, account_id):
    purchase_id = value(value(session, "metadata"), "purchase_id")
    purchase = db.query(PackageCheckout).filter_by(
        id=purchase_id, account_id=account_id, session_id=object_id(session)
    ).with_for_update().first()
    if not purchase:
        # Stripe can deliver an event before the session ID is committed.
        raise HTTPException(503, "Package checkout has not been matched yet.")
    if purchase.status == "paid":
        return
    if value(session, "status") == "expired":
        purchase.status = "expired"
    elif value(session, "payment_status") == "paid":
        if (value(session, "mode") != "payment" or value(session, "currency") != "usd"
                or value(session, "amount_total") != purchase.price_cents):
            raise HTTPException(409, "Stripe payment does not match the package purchase.")
        db.add(PackageSale(
            id=purchase.id, shop_slug=purchase.shop_slug, offer_id=purchase.offer_id,
            customer_phone=purchase.customer_phone, sessions=purchase.sessions,
            sessions_remaining=purchase.sessions, price_cents=purchase.price_cents,
            recorded_by=purchase.recorded_by,
        ))
        terms = db.get(PackageExpiration, "checkout:" + purchase.id)
        if terms:
            db.add(PackageExpiration(key="sale:" + purchase.id, duration=terms.duration, unit=terms.unit,
                                     expires_at=expiration_date(timestamp(), terms.duration, terms.unit)))
        purchase.status = "paid"
    db.commit()


@router.post("/appointments/{appointment_id}/text-package-link")
def text_package_link(appointment_id: str, payload: PackageSaleInput,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    appointment = appointment_for_user(db, appointment_id, user)
    offer = next((item for item in matching_offers(db, appointment) if item.id == payload.offer_id), None)
    if offer and offer.sessions == 1:
        offer = None
    return send_purchase_link(db, user, offer, phone_key(appointment.customer_phone or ""), appointment.id, payload.request_id)


def send_purchase_link(db, user, offer, digits, sale_context, request_id):
    shop = db.query(Shop).filter_by(slug=user.shop_slug).one()
    if not offer or db.get(DeletedPackageOffer, offer.id) or len(digits) != 10:
        raise HTTPException(409, "Choose an available service or package and check the customer's US phone number.")
    if shop.payment_policy not in {"accept_cards", "card_required"} or not shop.stripe_connect_account_id:
        raise HTTPException(409, "Enable card payments and connect this shop to Stripe first.")
    purchase_id = str(request_id)
    purchase = db.get(PackageCheckout, purchase_id)
    if purchase and (purchase.appointment_id, purchase.offer_id, purchase.customer_phone, purchase.shop_slug) != (
        sale_context, offer.id, digits, shop.slug
    ):
        raise HTTPException(409, "This purchase reference does not match.")
    if not purchase and sale_context != "retail":
        purchase = db.query(PackageCheckout).filter_by(
            appointment_id=sale_context, offer_id=offer.id, customer_phone=digits,
            status="pending",
        ).first()
    if not purchase:
        purchase = PackageCheckout(
            id=purchase_id, appointment_id=sale_context, shop_slug=shop.slug,
            account_id=shop.stripe_connect_account_id, offer_id=offer.id, name=offer.name,
            customer_phone=digits, sessions=offer.sessions, price_cents=offer.price_cents,
            fee_cents=service_fee_cents(offer.price_cents),
            recorded_by=user.id,
        )
        db.add(purchase)
        if offer.sessions > 1:
            terms = offer_view(offer, db)
            db.add(PackageExpiration(key="checkout:" + purchase.id,
                                 duration=terms["expiration_duration"], unit=terms["expiration_unit"]))
        db.commit()
        if sale_context != "retail":
            appointment_for_user(db, sale_context, user)
    db.refresh(purchase, with_for_update=True)
    if purchase.account_id != shop.stripe_connect_account_id:
        raise HTTPException(409, "This purchase belongs to a previous Stripe account.")
    if purchase.status != "pending":
        return {"status": purchase.status}
    stripe.api_key = get_stripe_secret_key()
    try:
        if not purchase.session_id:
            if timestamp() - purchase.created_at >= timedelta(hours=23):
                raise HTTPException(409, "An earlier checkout attempt needs review before retrying.")
            metadata = {"purpose": "package_payment", "purchase_id": purchase.id}
            terms = db.get(PackageExpiration, "checkout:" + purchase.id)
            product = {"name": f"{shop.name} - {purchase.name} ({purchase.sessions} sessions)"}
            if terms:
                unit = terms.unit.rstrip("s") if terms.duration == 1 else terms.unit
                product["description"] = f"Unused sessions expire {terms.duration} {unit} after purchase."
            base = (os.getenv("CHAIRTIME_FRONTEND_URL") or os.getenv("FRONTEND_URL")
                    or "https://www.daytello.com").rstrip("/")
            intent_data = {"metadata": metadata}
            if purchase.fee_cents:
                intent_data["application_fee_amount"] = purchase.fee_cents
            session = stripe.checkout.Session.create(
                mode="payment", payment_method_types=["card"], metadata=metadata,
                payment_intent_data=intent_data,
                line_items=[{"quantity": 1, "price_data": {
                    "currency": "usd", "unit_amount": purchase.price_cents,
                    "product_data": product,
                }}],
                success_url=f"{base}/package-payment?result=complete",
                cancel_url=f"{base}/package-payment?result=canceled",
                stripe_account=purchase.account_id, idempotency_key=f"package-checkout:{purchase.id}",
            )
            purchase.session_id = object_id(session)
            purchase.checkout_url = value(session, "url")
            if not purchase.session_id or not purchase.checkout_url:
                raise stripe_failure()
        else:
            session = stripe.checkout.Session.retrieve(purchase.session_id, stripe_account=purchase.account_id)
            if value(session, "status") != "open":
                settle_package_checkout(db, session, purchase.account_id)
                return {"status": purchase.status}
    except stripe.StripeError:
        db.rollback()
        raise stripe_failure()
    delivery = db.get(PaymentLinkDelivery, purchase.session_id)
    if delivery and delivery.status in {"sending", "sent", "unknown"}:
        return {"status": delivery.status}
    if not delivery:
        delivery = PaymentLinkDelivery(session_id=purchase.session_id, payment_id=purchase.id,
                                       recipient_last4=digits[-4:], status="sending")
        db.add(delivery)
    delivery.status = "sending"
    message = (f"{shop.name}: Buy {purchase.name} ({purchase.sessions} sessions) for "
               f"${Decimal(purchase.price_cents) / 100:.2f}: {purchase.checkout_url} Reply STOP to unsubscribe.")
    db.commit()
    try:
        result = send_highlevel_sms("+1" + digits, message, shop_id=shop.id, shop_slug=shop.slug,
                                    purpose="payment_link", source_id=purchase.id)
    except Exception:
        result = {"step": "message"}
    if result.get("success"):
        delivery.status = "sent"
    elif result.get("step") in {"config", "contact", "contact_id", "tracking"}:
        delivery.status = "failed"
    else:
        delivery.status = "unknown"
    db.commit()
    return {"status": delivery.status}


@router.post("/appointments/{appointment_id}/redeem-package")
def redeem_package(appointment_id: str, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    appointment = appointment_for_user(db, appointment_id, user)
    if current_redemption(db, appointment):
        return {"success": True}
    if appointment.status not in {"confirmed", "completed"} or db.query(ServicePayment).filter_by(
        appointment_id=appointment.id
    ).first():
        raise HTTPException(409, "This appointment cannot be paid with a package.")
    for sale in available_sales(db, appointment, matching_offers(db, appointment)):
        updated = db.query(PackageSale).filter(PackageSale.id == sale.id, PackageSale.sessions_remaining > 0).update(
            {PackageSale.sessions_remaining: PackageSale.sessions_remaining - 1}
        )
        if updated:
            db.add(PackageRedemption(appointment_id=appointment.id, sale_id=sale.id, redeemed_by=user.id))
            db.commit()
            return {"success": True}
    raise HTTPException(409, "There are no eligible package sessions left.")


@router.post("/appointments/{appointment_id}/reverse-package")
def reverse_package(appointment_id: str, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    appointment = appointment_for_user(db, appointment_id, user)
    redemption = current_redemption(db, appointment)
    if redemption:
        db.query(PackageSale).filter_by(id=redemption.sale_id).update(
            {PackageSale.sessions_remaining: PackageSale.sessions_remaining + 1}
        )
        redemption.reversed_at = timestamp()
        redemption.reversed_by = user.id
        db.commit()
    return {"success": True}


def shop_zone(db, slug):
    shop = db.query(Shop).filter_by(slug=slug).first()
    return ZoneInfo(shop.timezone if shop and shop.timezone else "America/New_York")


class PurchaseExpirationInput(BaseModel):
    purchase_id: str
    expiration_date: date


@router.post("/appointments/{appointment_id}/package-expiration")
def update_purchase_expiration(appointment_id: str, payload: PurchaseExpirationInput,
                               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    appointment = appointment_for_user(db, appointment_id, user)
    if user.role != "owner":
        raise HTTPException(403, "Only the owner can change a package expiration date.")
    sale = next((item for item in available_sales(db, appointment, matching_offers(db, appointment))
                 if item.id == payload.purchase_id), None)
    if not sale:
        raise HTTPException(404, "Active package purchase not found.")
    db.refresh(sale, with_for_update=True)
    terms = db.get(PackageExpiration, "sale:" + sale.id, populate_existing=True)
    if sale.sessions_remaining < 1 or (terms and terms.expires_at <= timestamp()):
        raise HTTPException(409, "This purchase is no longer active.")
    zone = shop_zone(db, appointment.shop_slug)
    if not datetime.now(zone).date() <= payload.expiration_date < date.max:
        raise HTTPException(422, "Choose today or a future expiration date.")
    expires_at = datetime.combine(payload.expiration_date + timedelta(days=1), datetime.min.time(), zone)
    if not terms:
        terms = PackageExpiration(key="sale:" + sale.id, duration=1, unit="years")
        db.add(terms)
    terms.expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"success": True}
def retail_catalog(db, slug):
    catalog = {item.name.strip().casefold(): item for item in db.query(ServiceCatalog).filter_by(shop_slug=slug)}
    staff = {item.id: item.name for item in db.query(Barber).filter_by(shop_slug=slug)}
    return [(item, catalog[item.name.strip().casefold()], staff.get(item.barber_id)) for item in
            db.query(Service).filter_by(shop_slug=slug, is_active=True).order_by(Service.name)
            if item.name.strip().casefold() in catalog and item.duration_minutes > 0 and item.price >= Decimal("0.50")]


@router.get("/retail")
def retail_options(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_payment_user(user)
    return {
        "services": [{"id": item.id, "catalog_id": catalog.id, "name": item.name, "staff": staff,
                      "duration_minutes": item.duration_minutes, "price_cents": int(item.price * 100)}
                     for item, catalog, staff in retail_catalog(db, user.shop_slug)],
        "packages": get_packages(user, db),
    }


@router.get("/retail/customers")
def retail_customers(q: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_payment_user(user)
    q = q.strip()[:100]
    if len(q) < 2:
        return []
    query = db.query(Appointment.customer_name, Appointment.customer_phone).filter_by(shop_slug=user.shop_slug)
    digits = phone_key(q)
    predicate = Appointment.customer_name.icontains(q, autoescape=True)
    if digits:
        predicate |= Appointment.customer_phone.contains(digits, autoescape=True)
    return [{"name": name, "phone": phone} for name, phone in query.filter(predicate).distinct().limit(30)
            if len(phone_key(phone or "")) == 10]


class RetailSaleInput(BaseModel):
    request_id: UUID
    kind: Literal["service", "package"]
    item_id: str
    phone: str = Field(max_length=32)
    method: Literal["cash", "check", "external_card", "bank_transfer", "other"] | None = None
    reference: str = Field(default="", max_length=250)


@router.post("/retail")
def retail_sale(payload: RetailSaleInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_payment_user(user)
    digits = phone_key(payload.phone)
    if len(digits) != 10:
        raise HTTPException(422, "Enter a valid US mobile number.")
    if payload.kind == "package":
        offer = db.query(PackageOffer).filter_by(id=payload.item_id, shop_slug=user.shop_slug).filter(
            PackageOffer.sessions > 1
        ).first()
    else:
        selected = next((entry for entry in retail_catalog(db, user.shop_slug) if entry[0].id == payload.item_id), None)
        if not selected:
            raise HTTPException(404, "Service with a price and duration not found.")
        service, catalog, _ = selected
        price = int(service.price * 100)
        offer_id = f"retail-{service.id}-{price}-{service.duration_minutes}"
        offer = db.get(PackageOffer, offer_id)
        if not offer:
            offer = PackageOffer(id=offer_id, shop_slug=user.shop_slug, catalog_id=catalog.id,
                                 name=f"{service.name} ({service.duration_minutes} min)", sessions=1, price_cents=price)
            db.add(offer)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                offer = db.get(PackageOffer, offer_id)
    if payload.method:
        from app.routes.sales import record_retail_payment

        return record_retail_payment(db, user, offer, digits, payload)
    return send_purchase_link(db, user, offer, digits, "retail", payload.request_id)
