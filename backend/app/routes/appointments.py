from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, Barber, BlockedTime, Service
from app.routes.reminders import send_highlevel_sms
from app.schemas import AppointmentCreate
from app.scheduling import has_overlap

router = APIRouter()


@router.post("/appointments")
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
):
    service = db.query(Service).filter(Service.id == payload.service_id).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

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
        raise HTTPException(status_code=409, detail="Time slot already booked")

    appointment = Appointment(
        shop_slug=payload.shop_slug,
        barber_id=payload.barber_id,
        service_id=payload.service_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_tags=payload.customer_tags,
        customer_notes=payload.customer_notes,
        notes=payload.notes,
        start_datetime=payload.start_datetime,
        end_datetime=end_datetime,
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    barber = db.query(Barber).filter(Barber.id == appointment.barber_id).first()

    confirmation_message = (
        f"You're booked with {barber.name if barber else 'your barber'} "
        f"on {appointment.start_datetime.strftime('%A, %B %d at %I:%M %p')}. "
        "Reply STOP to unsubscribe."
    )

    send_highlevel_sms(appointment.customer_phone, confirmation_message)

    return appointment


@router.get("/appointments")
def list_appointments(
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Appointment)

    if shop_slug:
        query = query.filter(Appointment.shop_slug == shop_slug)

    return query.all()


@router.patch("/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: str,
    db: Session = Depends(get_db),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.status = "canceled"

    db.commit()
    db.refresh(appointment)

    return appointment


@router.patch("/appointments/{appointment_id}/status")
def update_appointment_status(
    appointment_id: str,
    status: str,
    db: Session = Depends(get_db),
):
    allowed_statuses = ["confirmed", "completed", "no_show", "canceled"]

    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Invalid appointment status")

    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.status = status

    db.commit()
    db.refresh(appointment)

    return appointment


@router.patch("/appointments/{appointment_id}/reschedule")
def reschedule_appointment(
    appointment_id: str,
    new_start_datetime: str,
    db: Session = Depends(get_db),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    service = db.query(Service).filter(Service.id == appointment.service_id).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    new_start = datetime.fromisoformat(new_start_datetime)
    new_end = new_start + timedelta(minutes=service.duration_minutes)

    conflict = (
        db.query(Appointment)
        .filter(
            Appointment.barber_id == appointment.barber_id,
            Appointment.id != appointment.id,
            Appointment.status != "canceled",
            Appointment.start_datetime < new_end,
            Appointment.end_datetime > new_start,
        )
        .first()
    )

    if conflict:
        raise HTTPException(status_code=409, detail="That time is already booked")

    blocked_conflict = (
        db.query(BlockedTime)
        .filter(
            BlockedTime.barber_id == appointment.barber_id,
            BlockedTime.start_datetime < new_end,
            BlockedTime.end_datetime > new_start,
        )
        .first()
    )

    if blocked_conflict:
        raise HTTPException(status_code=409, detail="That time is blocked")

    appointment.start_datetime = new_start
    appointment.end_datetime = new_end
    appointment.status = "confirmed"
    appointment.reminder_sent = False
    appointment.reminder_sent_at = None

    db.commit()
    db.refresh(appointment)

    return appointment


@router.patch("/appointments/{appointment_id}/notes")
def update_appointment_notes(
    appointment_id: str,
    notes: str,
    db: Session = Depends(get_db),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.notes = notes

    db.commit()
    db.refresh(appointment)

    return appointment