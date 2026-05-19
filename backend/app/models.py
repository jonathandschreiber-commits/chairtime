import uuid
from sqlalchemy import Column, String, Integer, DateTime, Time, ForeignKey
from app.database import Base


class Barber(Base):
    __tablename__ = "barbers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    shop_name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    timezone = Column(String, nullable=False)


class Service(Base):
    __tablename__ = "services"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    barber_id = Column(String, ForeignKey("barbers.id"), nullable=False)
    name = Column(String, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    price = Column(Integer, nullable=True)


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    barber_id = Column(String, ForeignKey("barbers.id"), nullable=False)
    weekday = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    barber_id = Column(String, ForeignKey("barbers.id"), nullable=False)
    service_id = Column(String, ForeignKey("services.id"), nullable=False)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    status = Column(String, default="confirmed")

class Shop(Base):
    __tablename__ = "shops"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    business_type = Column(String, nullable=False, default="barbershop")
    phone = Column(String, nullable=True)
    timezone = Column(String, nullable=False, default="America/New_York")

    accepts_cards = Column(Integer, default=0)
    requires_deposit = Column(Integer, default=0)
    deposit_amount = Column(Integer, nullable=True)
    no_show_fee = Column(Integer, nullable=True)