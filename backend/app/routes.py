from datetime import timedelta, date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Barber, Service, AvailabilityRule, Appointment
from app.schemas import (
    BarberCreate,
    ServiceCreate,
    AvailabilityCreate,
    AppointmentCreate,
)
from app.scheduling import has_overlap, generate_available_slots

router = APIRouter()


@router.post("/barbers")
def create_barber(payload: BarberCreate, db: Session = Depends(get_db)):
    barber = Barber(**payload.model_dump())

    db.add(barber)
    db.commit()
    db.refresh(barber)

    return barber


@router.get("/barbers")
def list_barbers(db: Session = Depends(get_db)):
    return db.query(Barber).all()


@router.post("/services")
def create_service(payload: ServiceCreate, db: Session = Depends(get_db)):
    service = Service(**payload.model_dump())

    db.add(service)
    db.commit()
    db.refresh(service)

    return service


@router.get("/services")
def list_services(db: Session = Depends(get_db)):
    return db.query(Service).all()


@router.post("/availability-rules")
def create_availability_rule(
    payload: AvailabilityCreate,
    db: Session = Depends(get_db)
):
    rule = AvailabilityRule(**payload.model_dump())

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return rule


@router.get("/availability")
def get_availability(
    barber_id: str,
    service_id: str,
    target_date: date,
    db: Session = Depends(get_db),
):
    slots = generate_available_slots(
        db,
        barber_id,
        service_id,
        target_date,
    )

    return {"slots": slots}


@router.post("/appointments")
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
):
    service = db.query(Service).filter(
        Service.id == payload.service_id
    ).first()

    if not service:
        raise HTTPException(
            status_code=404,
            detail="Service not found",
        )

    end_datetime = payload.start_datetime + timedelta(
        minutes=service.duration_minutes
    )

    overlap = has_overlap(
        db,
        payload.barber_id,
        payload.start_datetime,
        end_datetime,
    )

    if overlap:
        raise HTTPException(
            status_code=409,
            detail="Time slot already booked",
        )

    appointment = Appointment(
        barber_id=payload.barber_id,
        service_id=payload.service_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        start_datetime=payload.start_datetime,
        end_datetime=end_datetime,
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return appointment


@router.get("/appointments")
def list_appointments(db: Session = Depends(get_db)):
    return db.query(Appointment).all()

@router.patch("/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: str,
    db: Session = Depends(get_db),
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id
    ).first()

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    appointment.status = "cancelled"

    db.commit()
    db.refresh(appointment)

    return appointment