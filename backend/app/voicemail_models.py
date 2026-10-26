"""Persist received voicemail events for idempotency; no SMS is sent here."""

from sqlalchemy import Column, DateTime, String
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
