"""Persist received voicemail events for idempotency; no SMS is sent here."""

from sqlalchemy import Boolean, Column, DateTime, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class DayTelloVoicemailEvent(Base):
    __tablename__ = "daytello_voicemail_events"

    location_id = Column(String(128), primary_key=True)
    message_id = Column(String(128), primary_key=True)
    shop_id = Column(String(128), nullable=False, index=True)
    receiving_number = Column(String(20), nullable=False)
    notification_status = Column(
        String(24), nullable=False, default="disabled"
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class DayTelloVoicemailShopSettings(Base):
    """Explicit per-shop routing and owner preferences.

    Provisioning binds the receiving number. Owners may only edit their
    notification preference and phone, never another tenant's routing.
    """
    __tablename__ = "daytello_voicemail_shop_settings"
    __table_args__ = (
        UniqueConstraint(
            "location_id", "receiving_number",
            name="uq_daytello_voicemail_location_number",
        ),
    )

    shop_id = Column(String(128), primary_key=True)
    location_id = Column(String(128), nullable=False)
    receiving_number = Column(String(20), nullable=False)
    owner_phone = Column(String(20), nullable=True)
    notifications_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
