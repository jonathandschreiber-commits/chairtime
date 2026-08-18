import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, Barber, BlockedTime, User
from app.routes.auth import get_current_user
from app.schemas import (
    BlockedTimeCreate,
    RecurringBlockedTimeCreate,
)


router = APIRouter()

MAX_RECURRENCE_DAYS = 366


def require_user_shop_slug(current_user: User) -> str:
    shop_slug = str(
        current_user.shop_slug or ""
    ).strip().lower()

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not assigned to a business.",
        )

    return shop_slug


def validate_reason(reason: str) -> str:
    clean_reason = str(reason or "").strip()

    if not clean_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A reason is required.",
        )

    return clean_reason


def validate_datetime_range(
    start_datetime: datetime,
    end_datetime: datetime,
) -> None:
    if end_datetime <= start_datetime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End time must be after start time.",
        )


def require_shop_barber(
    db: Session,
    barber_id: str,
    shop_slug: str,
) -> Barber:
    barber = (
        db.query(Barber)
        .filter(
            Barber.id == barber_id,
            Barber.shop_slug == shop_slug,
        )
        .first()
    )

    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found.",
        )

    return barber


def find_shop_blocked_time(
    db: Session,
    blocked_time_id: str,
    shop_slug: str,
) -> BlockedTime:
    blocked_time = (
        db.query(BlockedTime)
        .filter(
            BlockedTime.id == blocked_time_id,
            BlockedTime.shop_slug == shop_slug,
        )
        .first()
    )

    if not blocked_time:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blocked time not found.",
        )

    return blocked_time


def has_appointment_conflict(
    db: Session,
    shop_slug: str,
    barber_id: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> bool:
    conflict = (
        db.query(Appointment)
        .filter(
            Appointment.shop_slug == shop_slug,
            Appointment.barber_id == barber_id,
            Appointment.status != "canceled",
            Appointment.start_datetime < end_datetime,
            Appointment.end_datetime > start_datetime,
        )
        .first()
    )

    return conflict is not None


def has_blocked_time_conflict(
    db: Session,
    shop_slug: str,
    barber_id: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> bool:
    conflict = (
        db.query(BlockedTime)
        .filter(
            BlockedTime.shop_slug == shop_slug,
            BlockedTime.barber_id == barber_id,
            BlockedTime.start_datetime < end_datetime,
            BlockedTime.end_datetime > start_datetime,
        )
        .first()
    )

    return conflict is not None


def validate_no_conflict(
    db: Session,
    shop_slug: str,
    barber_id: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> None:
    if has_appointment_conflict(
        db,
        shop_slug,
        barber_id,
        start_datetime,
        end_datetime,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That time already has an appointment.",
        )

    if has_blocked_time_conflict(
        db,
        shop_slug,
        barber_id,
        start_datetime,
        end_datetime,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That time is already blocked.",
        )


@router.post("/blocked-times")
def create_blocked_time(
    payload: BlockedTimeCreate,
    db: Session = Depends(get_db),
):
    clean_reason = validate_reason(payload.reason)

    validate_datetime_range(
        payload.start_datetime,
        payload.end_datetime,
    )

    blocked_time = BlockedTime(
        shop_slug=payload.shop_slug,
        barber_id=payload.barber_id,
        reason=clean_reason,
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        series_id=None,
    )

    db.add(blocked_time)

    try:
        db.commit()
        db.refresh(blocked_time)
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Blocked time could not be created.",
        )

    return blocked_time


@router.get("/blocked-times")
def list_blocked_times(
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(BlockedTime)

    if shop_slug:
        clean_shop_slug = shop_slug.strip().lower()

        query = query.filter(
            BlockedTime.shop_slug == clean_shop_slug
        )

    return query.order_by(
        BlockedTime.start_datetime.asc()
    ).all()


@router.delete("/blocked-times/{blocked_time_id}")
def delete_blocked_time(
    blocked_time_id: str,
    db: Session = Depends(get_db),
):
    blocked_time = (
        db.query(BlockedTime)
        .filter(
            BlockedTime.id == blocked_time_id
        )
        .first()
    )

    if not blocked_time:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blocked time not found.",
        )

    db.delete(blocked_time)

    try:
        db.commit()
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Blocked time could not be deleted.",
        )

    return {
        "message": "Blocked time deleted.",
    }


@router.get("/admin/blocked-times")
def list_admin_blocked_times(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop_slug = require_user_shop_slug(current_user)

    return (
        db.query(BlockedTime)
        .filter(
            BlockedTime.shop_slug == shop_slug
        )
        .order_by(
            BlockedTime.start_datetime.asc()
        )
        .all()
    )


@router.post("/admin/blocked-times")
def create_admin_blocked_time(
    payload: BlockedTimeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop_slug = require_user_shop_slug(current_user)
    clean_reason = validate_reason(payload.reason)

    require_shop_barber(
        db,
        payload.barber_id,
        shop_slug,
    )

    validate_datetime_range(
        payload.start_datetime,
        payload.end_datetime,
    )

    validate_no_conflict(
        db,
        shop_slug,
        payload.barber_id,
        payload.start_datetime,
        payload.end_datetime,
    )

    blocked_time = BlockedTime(
        shop_slug=shop_slug,
        barber_id=payload.barber_id,
        reason=clean_reason,
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        series_id=None,
    )

    db.add(blocked_time)

    try:
        db.commit()
        db.refresh(blocked_time)
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Blocked time could not be created.",
        )

    return blocked_time


@router.post("/admin/blocked-times/recurring")
def create_recurring_admin_blocked_time(
    payload: RecurringBlockedTimeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop_slug = require_user_shop_slug(current_user)
    clean_reason = validate_reason(payload.reason)

    require_shop_barber(
        db,
        payload.barber_id,
        shop_slug,
    )

    if payload.end_date < payload.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be on or after start date.",
        )

    recurrence_days = (
        payload.end_date - payload.start_date
    ).days

    if recurrence_days > MAX_RECURRENCE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recurring blocked time cannot exceed one year.",
        )

    weekdays = set(payload.weekdays)

    if any(
        weekday < 0 or weekday > 6
        for weekday in weekdays
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Weekdays must be between 0 and 6.",
        )

    if payload.end_time <= payload.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End time must be after start time.",
        )

    occurrences = []
    current_date = payload.start_date

    while current_date <= payload.end_date:
        if current_date.weekday() in weekdays:
            start_datetime = datetime.combine(
                current_date,
                payload.start_time,
            )

            end_datetime = datetime.combine(
                current_date,
                payload.end_time,
            )

            occurrences.append(
                (
                    start_datetime,
                    end_datetime,
                )
            )

        current_date += timedelta(days=1)

    if not occurrences:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No matching dates were found for the selected weekdays.",
        )

    for start_datetime, end_datetime in occurrences:
        if has_appointment_conflict(
            db,
            shop_slug,
            payload.barber_id,
            start_datetime,
            end_datetime,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A selected recurring time conflicts with "
                    f"an appointment on {start_datetime:%B %d, %Y}."
                ),
            )

        if has_blocked_time_conflict(
            db,
            shop_slug,
            payload.barber_id,
            start_datetime,
            end_datetime,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A selected recurring time is already blocked on "
                    f"{start_datetime:%B %d, %Y}."
                ),
            )

    series_id = str(uuid.uuid4())

    blocked_times = [
        BlockedTime(
            shop_slug=shop_slug,
            barber_id=payload.barber_id,
            reason=clean_reason,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            series_id=series_id,
        )
        for start_datetime, end_datetime in occurrences
    ]

    db.add_all(blocked_times)

    try:
        db.commit()

        for blocked_time in blocked_times:
            db.refresh(blocked_time)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recurring blocked time could not be created.",
        )

    return {
        "success": True,
        "series_id": series_id,
        "occurrences_created": len(blocked_times),
        "blocked_times": blocked_times,
    }


@router.delete("/admin/blocked-times/{blocked_time_id}")
def delete_admin_blocked_time(
    blocked_time_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop_slug = require_user_shop_slug(current_user)

    blocked_time = find_shop_blocked_time(
        db,
        blocked_time_id,
        shop_slug,
    )

    db.delete(blocked_time)

    try:
        db.commit()
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Blocked time could not be deleted.",
        )

    return {
        "message": "Blocked time deleted.",
    }


@router.delete("/admin/blocked-time-series/{series_id}")
def delete_admin_blocked_time_series(
    series_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop_slug = require_user_shop_slug(current_user)

    blocked_times = (
        db.query(BlockedTime)
        .filter(
            BlockedTime.shop_slug == shop_slug,
            BlockedTime.series_id == series_id,
        )
        .all()
    )

    if not blocked_times:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blocked-time series not found.",
        )

    deleted_count = len(blocked_times)

    for blocked_time in blocked_times:
        db.delete(blocked_time)

    try:
        db.commit()
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Blocked-time series could not be deleted.",
        )

    return {
        "success": True,
        "occurrences_deleted": deleted_count,
    }