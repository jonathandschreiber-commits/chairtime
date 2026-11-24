"""Prepaid service entitlements recorded by shop staff."""
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, or_

from app.database import Base
from app.models import Service, ServiceCatalog


def timestamp():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PackageOffer(Base):
    __tablename__ = "package_offers"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    shop_slug = Column(String, nullable=False, index=True)
    catalog_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    sessions = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)


class PackageSale(Base):
    __tablename__ = "package_sales"
    id = Column(String, primary_key=True)
    shop_slug = Column(String, nullable=False)
    offer_id = Column(String, ForeignKey("package_offers.id"), nullable=False)
    customer_phone = Column(String, nullable=False, index=True)
    sessions_remaining = Column(Integer, nullable=False)
    sessions = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)
    recorded_by = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=timestamp)


class PackageRedemption(Base):
    __tablename__ = "package_redemptions"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    appointment_id = Column(String, nullable=False, index=True)
    sale_id = Column(String, ForeignKey("package_sales.id"), nullable=False)
    redeemed_by = Column(String, nullable=False)
    redeemed_at = Column(DateTime, nullable=False, default=timestamp)
    reversed_by = Column(String)
    reversed_at = Column(DateTime)


def phone_key(value):
    digits = "".join(char for char in value if char in "0123456789")
    return digits[1:] if len(digits) == 11 and digits.startswith("1") else digits


def matching_offers(db, appointment):
    service = db.query(Service).filter_by(id=appointment.service_id, shop_slug=appointment.shop_slug).first()
    if not service:
        return []
    # Staff services are linked to catalog entries by name in Shop Setup.
    catalog = db.query(ServiceCatalog).filter_by(shop_slug=appointment.shop_slug).all()
    ids = [item.id for item in catalog if item.name.strip().casefold() == service.name.strip().casefold()]
    return db.query(PackageOffer).filter(
        PackageOffer.shop_slug == appointment.shop_slug, PackageOffer.catalog_id.in_(ids)
    ).order_by(PackageOffer.name).all()


def current_redemption(db, appointment):
    return db.query(PackageRedemption).filter_by(
        appointment_id=appointment.id, reversed_at=None
    ).first()


def reject_redeemed(db, appointment):
    if current_redemption(db, appointment):
        raise HTTPException(409, "This appointment was paid with a package session.")


class PackageExpiration(Base):
    __tablename__ = "package_expirations"
    key = Column(String, primary_key=True)
    duration = Column(Integer, nullable=False)
    unit = Column(String, nullable=False)
    expires_at = Column(DateTime)


def expiration_date(start, duration, unit):
    if unit == "days":
        return start + timedelta(days=duration)
    months = duration * (12 if unit == "years" else 1)
    year, month = divmod(start.year * 12 + start.month - 1 + months, 12)
    month += 1
    return start.replace(year=year, month=month, day=min(start.day, monthrange(year, month)[1]))


def package_sales(db, appointment, offers):
    return db.query(PackageSale, PackageExpiration).outerjoin(
        PackageExpiration, PackageExpiration.key == "sale:" + PackageSale.id
    ).filter(
        PackageSale.shop_slug == appointment.shop_slug,
        PackageSale.customer_phone == phone_key(appointment.customer_phone),
        PackageSale.offer_id.in_([offer.id for offer in offers]),
    ).order_by(PackageSale.created_at, PackageSale.id)


def available_sales(db, appointment, offers):
    return [sale for sale, _ in package_sales(db, appointment, offers).filter(
        PackageSale.sessions_remaining > 0,
        or_(PackageExpiration.expires_at.is_(None), PackageExpiration.expires_at > timestamp()),
    )]


class PackageCheckout(Base):
    """Purchase terms frozen before creating the Stripe session."""
    __tablename__ = "package_checkouts"
    id = Column(String, primary_key=True)
    appointment_id = Column(String, nullable=False, index=True)
    shop_slug = Column(String, nullable=False)
    account_id = Column(String, nullable=False)
    offer_id = Column(String, ForeignKey("package_offers.id"), nullable=False)
    name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    sessions = Column(Integer, nullable=False)
    fee_cents = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)
    recorded_by = Column(String, nullable=False)
    session_id = Column(String, unique=True)
    checkout_url = Column(String)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=timestamp)


class PackageAdjustment(Base):
    __tablename__ = "package_adjustments"
    id = Column(String, primary_key=True)
    sale_id = Column(String, ForeignKey("package_sales.id"), nullable=False)
    adjusted_by = Column(String, nullable=False)
    delta = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=timestamp)


class DeletedPackageOffer(Base):
    __tablename__ = "deleted_package_offers"
    offer_id = Column(String, ForeignKey("package_offers.id"), primary_key=True)



def redeem_on_completion(db, appointment, user_id, expired_payment=None):
    from app.payment_records import ServicePayment

    # Share the appointment lock used by payment and redemption routes.
    db.refresh(appointment, with_for_update=True)
    if appointment.status == "completed" or current_redemption(db, appointment):
        return
    payment = db.query(ServicePayment).filter_by(appointment_id=appointment.id).first()
    if payment and (payment is not expired_payment or payment.status != "expired"):
        return
    for sale in available_sales(db, appointment, matching_offers(db, appointment)):
        updated = db.query(PackageSale).filter(
            PackageSale.id == sale.id, PackageSale.sessions_remaining > 0,
        ).update({PackageSale.sessions_remaining: PackageSale.sessions_remaining - 1})
        if updated:
            db.add(PackageRedemption(appointment_id=appointment.id, sale_id=sale.id, redeemed_by=user_id))
            return
