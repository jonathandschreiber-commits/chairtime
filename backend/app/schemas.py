from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel


class ShopCreate(BaseModel):
    slug: Optional[str] = None
    name: str
    phone: Optional[str] = None
    timezone: str = "America/New_York"


class UserCreate(BaseModel):
    shop_id: Optional[str] = None
    shop_slug: Optional[str] = None
    name: str
    email: str
    password: str
    role: str = "owner"


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    shop_id: Optional[str] = None
    shop_slug: Optional[str] = None
    name: str
    email: str
    role: str
    is_active: bool


class BarberCreate(BaseModel):
    shop_slug: Optional[str] = None
    name: str
    shop_name: str
    phone: Optional[str] = None
    timezone: str = "America/New_York"


class BarberUpdate(BaseModel):
    shop_slug: Optional[str] = None
    name: Optional[str] = None
    shop_name: Optional[str] = None
    phone: Optional[str] = None
    timezone: Optional[str] = None


class ServiceCreate(BaseModel):
    shop_slug: Optional[str] = None
    barber_id: Optional[str] = None
    name: str
    duration_minutes: int
    price: float


class ServiceUpdate(BaseModel):
    shop_slug: Optional[str] = None
    barber_id: Optional[str] = None
    name: Optional[str] = None
    duration_minutes: Optional[int] = None
    price: Optional[float] = None


class AvailabilityCreate(BaseModel):
    shop_slug: Optional[str] = None
    barber_id: str
    weekday: int
    start_time: time
    end_time: time


class AvailabilityRuleCreate(BaseModel):
    shop_slug: Optional[str] = None
    barber_id: str
    weekday: int
    start_time: time
    end_time: time


class BlockedTimeCreate(BaseModel):
    shop_slug: Optional[str] = None
    barber_id: str
    reason: str
    start_datetime: datetime
    end_datetime: datetime


class AppointmentCreate(BaseModel):
    shop_slug: Optional[str] = None
    barber_id: str
    service_id: str
    customer_name: str
    customer_phone: str
    customer_tags: Optional[str] = None
    customer_notes: Optional[str] = None
    notes: Optional[str] = None
    start_datetime: datetime


class AppointmentUpdate(BaseModel):
    shop_slug: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_tags: Optional[str] = None
    customer_notes: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    start_datetime: Optional[datetime] = None