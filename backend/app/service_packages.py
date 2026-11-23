"""Prepaid service entitlements recorded by shop staff."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

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


def available_sales(db, appointment, offers):
    return db.query(PackageSale).filter(
        PackageSale.shop_slug == appointment.shop_slug,
        PackageSale.customer_phone == phone_key(appointment.customer_phone),
        PackageSale.offer_id.in_([offer.id for offer in offers]),
        PackageSale.sessions_remaining > 0,
    ).order_by(PackageSale.created_at, PackageSale.id).all()


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
