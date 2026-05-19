from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Appointment, AvailabilityRule, Service, BlockedTime, BlockedTime


SLOT_INCREMENT_MINUTES = 15


def has_overlap(db: Session, barber_id: str, requested_start: datetime, requested_end: datetime) -> bool:
    appointment_conflict = db.query(Appointment).filter(
        Appointment.barber_id == barber_id,
        Appointment.status == "confirmed",
        Appointment.start_datetime < requested_end,
        Appointment.end_datetime > requested_start,
    ).first()

    blocked_conflict = db.query(BlockedTime).filter(
        BlockedTime.barber_id == barber_id,
        BlockedTime.start_datetime < requested_end,
        BlockedTime.end_datetime > requested_start,
    ).first()

    return appointment_conflict is not None or blocked_conflict is not None


def generate_available_slots(db: Session, barber_id: str, service_id: str, target_date):
    weekday = target_date.weekday()

    rule = db.query(AvailabilityRule).filter(
        AvailabilityRule.barber_id == barber_id,
        AvailabilityRule.weekday == weekday,
    ).first()

    if not rule:
        return []

    service = db.query(Service).filter(
        Service.id == service_id
    ).first()

    if not service:
        return []

    service_duration = timedelta(minutes=service.duration_minutes)

    workday_start = datetime.combine(target_date, rule.start_time)
    workday_end = datetime.combine(target_date, rule.end_time)

    slots = []
    current = workday_start

    while current + service_duration <= workday_end:
        requested_end = current + service_duration

        if not has_overlap(db, barber_id, current, requested_end):
            slots.append(current)

        current += timedelta(minutes=SLOT_INCREMENT_MINUTES)

    return slots