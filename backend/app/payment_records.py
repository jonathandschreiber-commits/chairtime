"""Persistent service payments, separate from shop subscription billing."""
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func
from app.database import Base
from app.models import generate_uuid


class ServicePayment(Base):
    __tablename__ = "service_payments"

    id = Column(String, primary_key=True, default=generate_uuid)
    appointment_id = Column(String, nullable=False, unique=True, index=True)
    shop_slug = Column(String, nullable=False, index=True)
    account_id = Column(String, nullable=False)
    service_name = Column(String, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    fee_cents = Column(Integer, nullable=False, default=0)
    currency = Column(String, nullable=False, default="usd")
    generation = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="unpaid")
    session_id = Column(String, nullable=True, unique=True)
    checkout_url = Column(String, nullable=True)
    receipt_token = Column(String, nullable=False)
    payment_intent_id = Column(String, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class TerminalPaymentAttempt(Base):
    """Durable method reservation before a Stripe request can time out."""
    __tablename__ = "terminal_payment_attempts"
    payment_id = Column(String, primary_key=True)
    created_at = Column(DateTime, server_default=func.now())


class TerminalShopLocation(Base):
    __tablename__ = "terminal_shop_locations"
    shop_slug = Column(String, primary_key=True)
    account_id = Column(String, nullable=False)
    location_id = Column(String, nullable=False)


class PaymentLinkDelivery(Base):
    """One explicit SMS attempt per Checkout session; never blindly resend."""
    __tablename__ = "payment_link_deliveries"
    session_id = Column(String, primary_key=True)
    payment_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="sending")
    recipient_last4 = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class ServicePaymentRefund(Base):
    """Refund snapshot and one durable owner request per service payment."""
    __tablename__ = "service_payment_refunds"
    payment_id = Column(String, primary_key=True)
    refunded_cents = Column(Integer, nullable=False, default=0)
    pending_cents = Column(Integer, nullable=False, default=0)
    requested_cents = Column(Integer, nullable=True)
    requested_at = Column(DateTime, nullable=True)
    requested_by = Column(String, nullable=True)
    refund_id = Column(String, nullable=True)
    request_status = Column(String, nullable=True)
