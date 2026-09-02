import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.sql import func

from app.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Shop(Base):
    __tablename__ = "shops"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )
    slug = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )
    name = Column(
        String,
        nullable=False,
    )
    business_type = Column(
        String,
        nullable=False,
        default="service_business",
    )
    phone = Column(
        String,
        nullable=True,
    )
    timezone = Column(
        String,
        nullable=False,
        default="America/New_York",
    )

    # ChairTime subscription billing
    stripe_customer_id = Column(
        String,
        nullable=True,
        unique=True,
        index=True,
    )
    stripe_subscription_id = Column(
        String,
        nullable=True,
        unique=True,
        index=True,
    )
    subscription_status = Column(
        String,
        nullable=True,
    )
    trial_ends_at = Column(
        DateTime,
        nullable=True,
    )

    # Optional AI Phone Receptionist
    ai_voice_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
    )
    highlevel_location_id = Column(
        String,
        nullable=True,
    )
    highlevel_phone_number = Column(
        String,
        nullable=True,
    )

    # Shop payment preferences
    payment_policy = Column(
        String,
        nullable=False,
        default="none",
    )

    # Shop payment processing through Stripe Connect
    stripe_connect_account_id = Column(
        String,
        nullable=True,
        unique=True,
        index=True,
    )


class User(Base):
    __tablename__ = "users"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )
    shop_id = Column(
        String,
        nullable=True,
    )
    shop_slug = Column(
        String,
        nullable=True,
    )
    name = Column(
        String,
        nullable=False,
    )
    email = Column(
        String,
        nullable=False,
        unique=True,
    )
    password_hash = Column(
        String,
        nullable=False,
    )
    role = Column(
        String,
        nullable=False,
        default="owner",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at = Column(
        DateTime,
        server_default=func.now(),
    )


class Barber(Base):
    __tablename__ = "barbers"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )
    shop_slug = Column(
        String,
        nullable=True,
    )
    name = Column(
        String,
        nullable=False,
    )
    shop_name = Column(
        String,
        nullable=False,
    )
    phone = Column(
        String,
        nullable=True,
    )
    timezone = Column(
        String,
        nullable=False,
        default="America/New_York",
    )


class ServiceCatalog(Base):
    __tablename__ = "service_catalog"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )
    shop_slug = Column(
        String,
        nullable=False,
        index=True,
    )
    name = Column(
        String,
        nullable=False,
    )


class Service(Base):
    __tablename__ = "services"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )
    shop_slug = Column(
        String,
        nullable=True,
    )
    barber_id = Column(
        String,
        nullable=True,
    )
    name = Column(
        String,
        nullable=False,
    )
    duration_minutes = Column(
        Integer,
        nullable=False,
    )
    price = Column(
        Numeric(10, 2),
        nullable=False,
    )


class ShopAvailabilityRule(Base):
    __tablename__ = "shop_availability_rules"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )
    shop_slug = Column(
        String,
        nullable=False,
        index=True,
    )
    weekday = Column(
        Integer,
        nullable=False,
    )
    start_time = Column(
        Time,
        nullable=False,
    )
    end_time = Column(
        Time,
        nullable=False,
    )


class ShopBlockedTime(Base):
    __tablename__ = "shop_blocked_times"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )
    shop_slug = Column(
        String,
        nullable=False,
        index=True,
    )
    reason = Column(
        String,
        nullable=False,
    )
    start_datetime = Column(
        DateTime,
        nullable=False,
    )
    end_datetime = Column(
        DateTime,
        nullable=False,
    )
    series_id = Column(
        String,
        nullable=True,
        index=True,
    )


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )
    shop_slug = Column(
        String,
        nullable=True,
    )
    barber_id = Column(
        String,
        nullable=False,
    )
    weekday = Column(
        Integer,
        nullable=False,
    )
    start_time = Column(
        Time,
        nullable=False,
    )
    end_time = Column(
        Time,
        nullable=False,
    )


class BlockedTime(Base):
    __tablename__ = "blocked_times"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )
    shop_slug = Column(
        String,
        nullable=True,
    )
    barber_id = Column(
        String,
        nullable=False,
    )
    reason = Column(
        String,
        nullable=False,
    )
    start_datetime = Column(
        DateTime,
        nullable=False,
    )
    end_datetime = Column(
        DateTime,
        nullable=False,
    )
    series_id = Column(
        String,
        nullable=True,
        index=True,
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(
        String,
        primary_key=True,
        default=generate_uuid,
    )
    shop_slug = Column(
        String,
        nullable=True,
    )
    barber_id = Column(
        String,
        nullable=False,
    )
    service_id = Column(
        String,
        nullable=False,
    )
    customer_name = Column(
        String,
        nullable=False,
    )
    customer_phone = Column(
        String,
        nullable=False,
    )
    customer_tags = Column(
        String,
        nullable=True,
    )
    customer_notes = Column(
        Text,
        nullable=True,
    )
    notes = Column(
        String,
        nullable=True,
    )
    start_datetime = Column(
        DateTime,
        nullable=False,
    )
    end_datetime = Column(
        DateTime,
        nullable=False,
    )
    status = Column(
        String,
        nullable=False,
        default="confirmed",
    )
    reminder_sent = Column(
        Boolean,
        nullable=False,
        default=False,
    )
    reminder_sent_at = Column(
        DateTime,
        nullable=True,
    )

    # Stripe card-on-file information for this reservation.
    #
    # stripe_customer_id identifies the customer inside
    # this shop's Stripe connected account.
    #
    # stripe_setup_intent_id proves which SetupIntent
    # verified the card for this reservation.
    #
    # stripe_payment_method_id identifies the verified
    # card/payment method attached to that Stripe customer.
    stripe_customer_id = Column(
        String,
        nullable=True,
        index=True,
    )
    stripe_setup_intent_id = Column(
        String,
        nullable=True,
        index=True,
    )
    stripe_payment_method_id = Column(
        String,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        server_default=func.now(),
    )
