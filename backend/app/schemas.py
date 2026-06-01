from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel


class BarberCreate(BaseModel):
    name: str
    shop_name: str
    phone: Optional[str] = None
    timezone: str = "America/New_York"


class BarberResponse(BaseModel):
    id: str
    name: str
    shop_name: str
    phone: Optional[str] = None
    timezone: str

    class Config:
        from_attributes = True


class ServiceCreate(BaseModel):
    barber_id: Optional[str] = None
    name: str
    duration_minutes: int
    price: float


class ServiceResponse(BaseModel):
    id: str
    barber_id: Optional[str] = None
    name: str
    duration_minutes: int
    price: float

    class Config:
        from_attributes = True


class AvailabilityRuleCreate(BaseModel):
    barber_id: str
    weekday: int
    start_time: time
    end_time: time


class AvailabilityRuleResponse(BaseModel):
    id: str
    barber_id: str
    weekday: int
    start_time: time
    end_time: time

    class Config:
        from_attributes = True


class BlockedTimeCreate(BaseModel):
    barber_id: str
    reason: str
    start_datetime: datetime
    end_datetime: datetime


class BlockedTimeResponse(BaseModel):
    id: str
    barber_id: str
    reason: str
    start_datetime: datetime
    end_datetime: datetime

    class Config:
        from_attributes = True


class AppointmentCreate(BaseModel):
    barber_id: str
    service_id: str
    customer_name: str
    customer_phone: str
    notes: Optional[str] = None
    start_datetime: datetime


class AppointmentResponse(BaseModel):
    id: str
    barber_id: str
    service_id: str
    customer_name: str
    customer_phone: str
    notes: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    status: str

    class Config:
        from_attributes = True