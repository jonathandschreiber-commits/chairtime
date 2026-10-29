"""Exclusive tenant binding for an independently provisioned voice relay DID."""
from sqlalchemy import Boolean, Column, String, UniqueConstraint
from app.database import Base


class DayTelloVoiceRelayAssignment(Base):
    __tablename__ = "daytello_voice_relay_assignments"
    __table_args__ = (UniqueConstraint("relay_number", name="uq_voice_relay_number"),)
    shop_id = Column(String(128), primary_key=True)
    relay_number = Column(String(20), nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=False)
