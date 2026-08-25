from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    AvailabilityRule,
    BlockedTime,
    Service,
    ShopAvailabilityRule,
    ShopBlockedTime,
)


def normalize_time(value):
    if isinstance(value, str):
        return datetime.strptime(
            value,
            "%H:%M:%S",
        ).time()

    return value


def is_within_shop_hours(
    db: Session,
    shop_slug: str,
    requested_start: datetime,
    requested_end: datetime,
) -> bool:
    weekday = requested_start.date().weekday()

    rules = (
        db.query(ShopAvailabilityRule)
        .filter(
            ShopAvailabilityRule.shop_slug
            == shop_slug,
            ShopAvailabilityRule.weekday
            == weekday,
        )
        .all()
    )

    #
    # Important compatibility behavior:
    #
    # Until a shop has actually configured any shop-hours
    # records, preserve the existing ChairTime behavior.
    #
    any_shop_rules = (
        db.query(ShopAvailabilityRule)
        .filter(
            ShopAvailabilityRule.shop_slug
            == shop_slug
        )
        .first()
    )

    if not any_shop_rules:
        return True

    #
    # Once shop hours have been configured, having no rule
    # for a weekday means the shop is closed that day.
    #
    if not rules:
        return False

    for rule in rules:
        rule_start = datetime.combine(
            requested_start.date(),
            normalize_time(rule.start_time),
        )

        rule_end = datetime.combine(
            requested_start.date(),
            normalize_time(rule.end_time),
        )

        if (
            requested_start >= rule_start
            and requested_end <= rule_end
        ):
            return True

    return False


def has_overlap(
    db: Session,
    barber_id: str,
    requested_start: datetime,
    requested_end: datetime,
    shop_slug: str | None = None,
) -> bool:
    appointment_query = db.query(
        Appointment
    ).filter(
        Appointment.barber_id == barber_id,
        Appointment.status != "canceled",
        Appointment.start_datetime
        < requested_end,
        Appointment.end_datetime
        > requested_start,
    )

    if shop_slug:
        appointment_query = (
            appointment_query.filter(
                Appointment.shop_slug
                == shop_slug
            )
        )

    appointment_conflict = (
        appointment_query.first()
    )

    blocked_query = db.query(
        BlockedTime
    ).filter(
        BlockedTime.barber_id == barber_id,
        BlockedTime.start_datetime
        < requested_end,
        BlockedTime.end_datetime
        > requested_start,
    )

    if shop_slug:
        blocked_query = blocked_query.filter(
            BlockedTime.shop_slug
            == shop_slug
        )

    blocked_conflict = blocked_query.first()

    shop_blocked_conflict = None

    if shop_slug:
        shop_blocked_conflict = (
            db.query(ShopBlockedTime)
            .filter(
                ShopBlockedTime.shop_slug
                == shop_slug,
                ShopBlockedTime.start_datetime
                < requested_end,
                ShopBlockedTime.end_datetime
                > requested_start,
            )
            .first()
        )

    return (
        appointment_conflict is not None
        or blocked_conflict is not None
        or shop_blocked_conflict is not None
    )


def generate_available_slots(
    db: Session,
    barber_id: str,
    service_id: str,
    target_date,
):
    service = (
        db.query(Service)
        .filter(
            Service.id == service_id,
            Service.barber_id == barber_id,
        )
        .first()
    )

    if not service:
        return []

    shop_slug = str(
        service.shop_slug or ""
    ).strip().lower()

    weekday = target_date.weekday()

    rules_query = db.query(
        AvailabilityRule
    ).filter(
        AvailabilityRule.barber_id
        == barber_id,
        AvailabilityRule.weekday
        == weekday,
    )

    if shop_slug:
        rules_query = rules_query.filter(
            AvailabilityRule.shop_slug
            == shop_slug
        )

    rules = rules_query.all()

    slots = []

    for rule in rules:
        start_time = normalize_time(
            rule.start_time
        )

        end_time = normalize_time(
            rule.end_time
        )

        current_start = datetime.combine(
            target_date,
            start_time,
        )

        day_end = datetime.combine(
            target_date,
            end_time,
        )

        while (
            current_start
            + timedelta(
                minutes=service.duration_minutes
            )
            <= day_end
        ):
            current_end = (
                current_start
                + timedelta(
                    minutes=service.duration_minutes
                )
            )

            within_shop_hours = True

            if shop_slug:
                within_shop_hours = (
                    is_within_shop_hours(
                        db,
                        shop_slug,
                        current_start,
                        current_end,
                    )
                )

            if (
                within_shop_hours
                and not has_overlap(
                    db,
                    barber_id,
                    current_start,
                    current_end,
                    shop_slug=shop_slug,
                )
            ):
                slots.append(
                    current_start.isoformat()
                )

            current_start = (
                current_start
                + timedelta(minutes=15)
            )

    return slots
