from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, Barber, BlockedTime, Service, User
from app.routes.auth import get_current_user
from app.routes.reminders import send_highlevel_sms
from app.schemas import AppointmentCreate
from app.scheduling import has_overlap


router = APIRouter()

ALLOWED_APPOINTMENT_STATUSES = {
    "confirmed",
    "completed",
    "no_show",
    "canceled",
}


def require_user_shop_slug(current_user: User) -> str:
    shop_slug = str(current_user.shop_slug or "").strip().lower()

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not assigned to a business.",
        )

    return shop_slug


def find_shop_appointment(
    db: Session,
    appointment_id: str,
    shop_slug: str,
) -> Appointment:
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.shop_slug == shop_slug,
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    return appointment


@router.post("/appointments")
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
):
    shop_slug = str(payload.shop_slug or "").strip().lower()

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business is required.",
        )

    service = (
        db.query(Service)
        .filter(
            Service.id == payload.service_id,
            Service.shop_slug == shop_slug,
        )
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found.",
        )

    barber = (
        db.query(Barber)
        .filter(
            Barber.id == payload.barber_id,
            Barber.shop_slug == shop_slug,
        )
        .first()
    )

    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found.",
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
            status_code=status.HTTP_409_CONFLICT,
            detail="Time slot already booked.",
        )

    blocked_conflict = (
        db.query(BlockedTime)
        .filter(
            BlockedTime.shop_slug == shop_slug,
            BlockedTime.barber_id == payload.barber_id,
            BlockedTime.start_datetime < end_datetime,
            BlockedTime.end_datetime > payload.start_datetime,
        )
        .first()
    )

    if blocked_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That time is blocked.",
        )

    appointment = Appointment(
        shop_slug=shop_slug,
        barber_id=payload.barber_id,
        service_id=payload.service_id,
        customer_name=payload.customer_name.strip(),
        customer_phone=payload.customer_phone.strip(),
        customer_tags=payload.customer_tags,
        customer_notes=payload.customer_notes,
        notes=payload.notes,
        start_datetime=payload.start_datetime,
        end_datetime=end_datetime,
    )

    db.add(appointment)

    try:
        db.commit()
        db.refresh(appointment)
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The appointment could not be created.",
        )

    confirmation_message = (
        f"You're booked with {barber.name} "
        f"on {appointment.start_datetime.strftime('%A, %B %d at %I:%M %p')}. "
        "Reply STOP to unsubscribe."
    )

    try:
        send_highlevel_sms(
            appointment.customer_phone,
            confirmation_message,
        )
    except Exception as error:
        print(f"Confirmation SMS failed: {error}")

    return appointment


# Temporary legacy endpoint.
# This remains available until Calendar and Customers are migrated.
@router.get("/appointments")
def list_appointments(
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Appointment)

    if shop_slug:
        clean_shop_slug = shop_slug.strip().lower()

        query = query.filter(
            Appointment.shop_slug == clean_shop_slug
        )

    return query.order_by(
        Appointment.start_datetime.asc()
    ).all()


# Secure endpoint used by authenticated admin pages.
@router.get("/admin/appointments")
def list_admin_appointments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop_slug = require_user_shop_slug(current_user)

    return (
        db.query(Appointment)
        .filter(Appointment.shop_slug == shop_slug)
        .order_by(Appointment.start_datetime.asc())
        .all()
    )


# Temporary legacy endpoint.
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    appointment.status = "canceled"

    db.commit()
    db.refresh(appointment)

    return appointment


# Temporary legacy endpoint.
@router.patch("/appointments/{appointment_id}/status")
def update_appointment_status(
    appointment_id: str,
    status: str,
    db: Session = Depends(get_db),
):
    if status not in ALLOWED_APPOINTMENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid appointment status.",
        )

    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    appointment.status = status

    db.commit()
    db.refresh(appointment)

    return appointment


# Secure endpoint used by the authenticated Daily Agenda.
@router.patch("/admin/appointments/{appointment_id}/status")
def update_admin_appointment_status(
    appointment_id: str,
    appointment_status: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if appointment_status not in ALLOWED_APPOINTMENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid appointment status.",
        )

    shop_slug = require_user_shop_slug(current_user)

    appointment = find_shop_appointment(
        db,
        appointment_id,
        shop_slug,
    )

    appointment.status = appointment_status

    try:
        db.commit()
        db.refresh(appointment)
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The appointment status could not be updated.",
        )

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    service = (
        db.query(Service)
        .filter(Service.id == appointment.service_id)
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found.",
        )

    try:
        new_start = datetime.fromisoformat(new_start_datetime)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid appointment date and time.",
        )

    new_end = new_start + timedelta(
        minutes=service.duration_minutes
    )

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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That time is already booked.",
        )

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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That time is blocked.",
        )

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    appointment.notes = notes

    db.commit()
    db.refresh(appointment)

    return appointment