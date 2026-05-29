from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Appointment, AvailabilityRule, BlockedTime, Service


def has_overlap(
    db: Session,
    barber_id: str,
    requested_start: datetime,
    requested_end: datetime,
) -> bool:
    appointment_conflict = db.query(Appointment).filter(
        Appointment.barber_id == barber_id,
        Appointment.status != "canceled",
        Appointment.start_datetime < requested_end,
        Appointment.end_datetime > requested_start,
    ).first()

    blocked_conflict = db.query(BlockedTime).filter(
        BlockedTime.barber_id == barber_id,
        BlockedTime.start_datetime < requested_end,
        BlockedTime.end_datetime > requested_start,
    ).first()

    return appointment_conflict is not None or blocked_conflict is not None


def normalize_time(value):
    if isinstance(value, str):
        return datetime.strptime(value, "%H:%M:%S").time()

    return value


def generate_available_slots(
    db: Session,
    barber_id: str,
    service_id: str,
    target_date,
):
    service = db.query(Service).filter(Service.id == service_id).first()

    if not service:
        return []

    weekday = target_date.weekday()
    slots = []

    rules = db.query(AvailabilityRule).filter(
        AvailabilityRule.barber_id == barber_id,
        AvailabilityRule.weekday == weekday,
    ).all()

    for rule in rules:
        start_time = normalize_time(rule.start_time)
        end_time = normalize_time(rule.end_time)

        current_start = datetime.combine(target_date, start_time)
        day_end = datetime.combine(target_date, end_time)

        while current_start + timedelta(minutes=service.duration_minutes) <= day_end:
            current_end = current_start + timedelta(
                minutes=service.duration_minutes
            )

            if not has_overlap(db, barber_id, current_start, current_end):
                slots.append(current_start.isoformat())

            current_start = current_start + timedelta(minutes=15)

    return slots