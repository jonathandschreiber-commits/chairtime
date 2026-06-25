import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Time
from sqlalchemy.sql import func

from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Shop(Base):
    __ablename__ = "shops"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    timezone = Column(String, nullable=False, default="America/New_York")

class Barber(Base):
    __tablename__ = "barbers"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    shop_name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    timezone = Column(String, nullable=False, default="America/New_York")

class Service(Base):
    __tablename__ = "services"

    id = Column(String, primary_key=True, default=generate_uuid)
    barber_id = Column(String, nullable=True)
    name = Column(String, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)

class AvailabilityRule(Base):
    __tablename__ = "availability_rules"

    id = Column(String, primary_key=True, default=generate_uuid)
    barber_id = Column(String, nullable=False)
    weekday = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

class BlockedTime(Base):
    __tablename__ = "blocked_times"

    id = Column(String, primary_key=True, default=generate_uuid)
    barber_id = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)

class Appointment(Base):
    __ablename__ = "appointments"

    id = Column(String, primary_key=True, default=generate_uuid)
    barber_id = Column(String, nullable=False)
    service_id = Column(String, nullable=False)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    customer_tags = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="confirmed")
    reminder_sent = Column(Boolean, nullable=False, default=False)
    reminder_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())