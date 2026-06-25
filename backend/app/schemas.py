from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel

class ShopCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    timezone: str = "America/New_York"

class BarberCreate(BaseModel):
    name: str
    shop_name: str
    phone: Optional[str] = None
    timezone: str = "America/New_York"

class BarberUpdate(BaseModel):
    name: Optional[str] = None
    shop_name: Optional[str] = None
    phone: Optional[str] = None
    timezone: Optional[str] = None

class ServiceCreate(BaseModel):
    barber_id: Optional[str] = None
    name: str
    duration_minutes: int
    price: float

class ServiceUpdate(BaseModel):
    barber_id: Optional[str] = None
    name: Optional[str] = None
    duration_minutes: Optional[int] = None
    price: Optional[float] = None

class AvailabilityCreate(BaseModel):
    barber_id: str
    weekday: int
    start_time: time
    end_time: time

class AvailabilityRuleCreate(BaseModel):
    barber_id: str
    weekday: int
    start_time: time
    end_time: time

class BlockedTimeCreate(BaseModel):
    barber_id: str
    reason: str
    start_datetime: datetime
    end_datetime: datetime

class AppointmentCreate(BaseModel):
    barber_id: str
    service_id: str
    customer_name: str
    customer_phone: str
    customer_tags: Optional[str] = None
    notes: Optional[str] = None
    start_datetime: datetime

class AppointmentUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_tags: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    start_datetime: Optional[datetime] = None
