from datetime import datetime, time
from pydantic import BaseModel


class BarberCreate(BaseModel):
    name: str
    shop_name: str
    phone: str | None = None
    timezone: str = "America/New_York"


class ServiceCreate(BaseModel):
    barber_id: str
    name: str
    duration_minutes: int
    price: int | None = None


class AvailabilityCreate(BaseModel):
    barber_id: str
    weekday: int
    start_time: time
    end_time: time


class AppointmentCreate(BaseModel):
    barber_id: str
    service_id: str
    customer_name: str
    customer_phone: str
    start_datetime: datetime

class ShopCreate(BaseModel):
    name: str
    business_type: str
    phone: str | None = None
    timezone: str = "America/New_York"

    accepts_cards: int = 0
    requires_deposit: int = 0
    deposit_amount: int | None = None
    no_show_fee: int | None = None

class BlockedTimeCreate(BaseModel):
    barber_id: str
    start_datetime: datetime
    end_datetime: datetime
    reason: str | None = None

class BarberUpdate(BaseModel):
    name: str | None = None


class ServiceUpdate(BaseModel):
    name: str | None = None
    duration_minutes: int | None = None
    price: int | None = None