"""Shop sales and payment details."""
from datetime import date, datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, User
from app.payment_records import ManualAppointmentPayment, ManualRetailPayment, ServicePayment, ServicePaymentRefund
from app.routes.auth import get_current_user
from app.routes.payments import (
    get_stripe_secret_key, object_id, offer_view, require_payment_user, shop_zone, stripe_failure, value,
)
from app.service_packages import (
    DeletedPackageOffer, PackageCheckout, PackageExpiration, PackageSale, expiration_date, timestamp,
)

router = APIRouter()


def record_retail_payment(db, user, offer, phone, payload):
    if not offer or db.get(DeletedPackageOffer, offer.id):
        raise HTTPException(404, "Service or package not found.")
    sale_id = str(payload.request_id)
    reference = payload.reference.strip()
    expected = (user.shop_slug, offer.id, phone, payload.method, reference)

    def recorded(prior):
        return (prior.shop_slug, prior.offer_id, prior.customer_phone, prior.method, prior.reference) == expected

    prior = db.get(ManualRetailPayment, sale_id)
    if not prior:
        now = timestamp()
        db.add(ManualRetailPayment(
            id=sale_id, shop_slug=user.shop_slug, offer_id=offer.id, customer_phone=phone,
            item_name=offer.name, amount_cents=offer.price_cents, method=payload.method,
            reference=reference, recorded_by=user.id, created_at=now,
        ))
        db.add(PackageSale(
            id=sale_id, shop_slug=user.shop_slug, offer_id=offer.id, customer_phone=phone,
            sessions=offer.sessions, sessions_remaining=offer.sessions, price_cents=offer.price_cents,
            recorded_by=user.id, created_at=now,
        ))
        if offer.sessions > 1:
            terms = offer_view(offer, db)
            duration, unit = terms["expiration_duration"], terms["expiration_unit"]
            db.add(PackageExpiration(key="sale:" + sale_id, duration=duration, unit=unit,
                                     expires_at=expiration_date(now, duration, unit)))
        try:
            db.commit()
            return {"status": "recorded"}
        except IntegrityError:
            db.rollback()
            prior = db.get(ManualRetailPayment, sale_id)
    if not prior or not recorded(prior):
        raise HTTPException(409, "This payment reference is already in use.")
    return {"status": "recorded"}


@router.get("/sales")
def sales_report(start: date | None = None, end: date | None = None,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_payment_user(user)
    zone = shop_zone(db, user.shop_slug)
    today = datetime.now(zone).date()
    start, end = start or today.replace(day=1), end or today
    if start > end or end == date.max or (end - start).days > 366:
        raise HTTPException(422, "Choose a date range of up to one year.")
    start_at = datetime.combine(start, datetime.min.time(), zone).astimezone(timezone.utc).replace(tzinfo=None)
    end_at = datetime.combine(end + timedelta(days=1), datetime.min.time(), zone).astimezone(timezone.utc).replace(tzinfo=None)
    rows = []
    posted = func.coalesce(ServicePayment.paid_at, ServicePayment.created_at)
    for payment, appointment, refund in db.query(ServicePayment, Appointment, ServicePaymentRefund).outerjoin(
        Appointment, (Appointment.id == ServicePayment.appointment_id) & (Appointment.shop_slug == user.shop_slug)
    ).outerjoin(ServicePaymentRefund, ServicePaymentRefund.payment_id == ServicePayment.id).filter(
        ServicePayment.shop_slug == user.shop_slug, posted >= start_at, posted < end_at,
    ):
        refunded = refund.refunded_cents if refund else 0
        paid = payment.paid_at or payment.status in {"paid", "refunded", "partially_refunded"}
        rows.append(dict(id=payment.id, date=payment.paid_at or payment.created_at,
                         item=payment.service_name, customer=appointment.customer_name if appointment else "",
                         phone=appointment.customer_phone if appointment else "", method="stripe", status=payment.status,
                         amount_cents=payment.amount_cents, refunded_cents=refunded,
                         collected_cents=payment.amount_cents - refunded if paid else 0,
                         appointment_id=payment.appointment_id))
    posted = func.coalesce(PackageSale.created_at, PackageCheckout.created_at)
    for checkout, sale in db.query(PackageCheckout, PackageSale).outerjoin(
        PackageSale, PackageSale.id == PackageCheckout.id
    ).filter(PackageCheckout.shop_slug == user.shop_slug, posted >= start_at, posted < end_at):
        rows.append(dict(id=checkout.id, date=sale.created_at if sale else checkout.created_at,
                         item=checkout.name, phone=checkout.customer_phone, method="stripe", status=checkout.status,
                         amount_cents=checkout.price_cents, refunded_cents=0,
                         collected_cents=checkout.price_cents if checkout.status == "paid" else 0,
                         retail_details=checkout.status == "paid"))
    for payment, operator in db.query(ManualRetailPayment, User).outerjoin(
        User, User.id == ManualRetailPayment.recorded_by
    ).filter(ManualRetailPayment.shop_slug == user.shop_slug,
             ManualRetailPayment.created_at >= start_at, ManualRetailPayment.created_at < end_at):
        rows.append(dict(id=payment.id, date=payment.created_at, item=payment.item_name,
                         phone=payment.customer_phone, method=payment.method, status="recorded",
                         amount_cents=payment.amount_cents, refunded_cents=0, collected_cents=payment.amount_cents,
                         reference=payment.reference, recorded_by=operator.name if operator else payment.recorded_by))
    for payment, appointment, operator in db.query(ManualAppointmentPayment, Appointment, User).join(
        Appointment, Appointment.id == ManualAppointmentPayment.appointment_id
    ).outerjoin(User, User.id == ManualAppointmentPayment.recorded_by).filter(
        ManualAppointmentPayment.shop_slug == user.shop_slug,
        ManualAppointmentPayment.created_at >= start_at, ManualAppointmentPayment.created_at < end_at,
    ):
        rows.append(dict(id="offline:" + payment.appointment_id, date=payment.created_at,
                         customer=appointment.customer_name, phone=appointment.customer_phone,
                         item="Appointment payment", method=payment.method, status="recorded",
                         amount_cents=payment.amount_cents, refunded_cents=0, collected_cents=payment.amount_cents,
                         appointment_id=appointment.id, recorded_by=operator.name if operator else payment.recorded_by))
    rows.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
    for row in rows:
        row["date"] = row["date"].replace(tzinfo=timezone.utc).astimezone(zone).isoformat()
    return {"sales": rows, "timezone": str(zone)}


@router.get("/sales/{sale_id}")
def sale_details(sale_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_payment_user(user)
    sale = db.query(PackageCheckout).filter_by(id=sale_id, shop_slug=user.shop_slug, status="paid").first()
    if not sale or not sale.session_id:
        raise HTTPException(404, "Paid Stripe sale not found.")
    try:
        stripe.api_key = get_stripe_secret_key()
        checkout = stripe.checkout.Session.retrieve(
            sale.session_id, stripe_account=sale.account_id, expand=["payment_intent.latest_charge"],
        )
        charge = value(value(checkout, "payment_intent"), "latest_charge")
        if not object_id(charge):
            return {"receipt_url": None, "refunds": []}
        refunds = stripe.Refund.list(charge=object_id(charge), stripe_account=sale.account_id)
        return {
            "receipt_url": value(charge, "receipt_url"),
            "refunded_cents": value(charge, "amount_refunded", 0),
            "refunds": [{"id": value(refund, "id"), "amount_cents": value(refund, "amount"),
                         "status": value(refund, "status"), "reason": value(refund, "reason"),
                         "created_at": datetime.fromtimestamp(value(refund, "created"), timezone.utc).isoformat()}
                        for refund in refunds.auto_paging_iter()],
        }
    except stripe.StripeError:
        raise stripe_failure()
