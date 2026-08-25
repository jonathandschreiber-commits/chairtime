import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, ShopBlockedTime
from app.schemas import (
    ShopBlockedTimeCreate,
    ShopRecurringBlockedTimeCreate,
)


router = APIRouter()

MAX_RECURRENCE_DAYS = 366


def clean_shop_slug(value: str) -> str:
    shop_slug = str(value or "").strip().lower()

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shop is required.",
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


def has_shop_appointment_conflict(
    db: Session,
    shop_slug: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> bool:
    conflict = (
        db.query(Appointment)
        .filter(
            Appointment.shop_slug == shop_slug,
            Appointment.status != "canceled",
            Appointment.start_datetime < end_datetime,
            Appointment.end_datetime > start_datetime,
        )
        .first()
    )

    return conflict is not None


def has_shop_block_conflict(
    db: Session,
    shop_slug: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> bool:
    conflict = (
        db.query(ShopBlockedTime)
        .filter(
            ShopBlockedTime.shop_slug == shop_slug,
            ShopBlockedTime.start_datetime < end_datetime,
            ShopBlockedTime.end_datetime > start_datetime,
        )
        .first()
    )

    return conflict is not None


def find_shop_blocked_time(
    db: Session,
    blocked_time_id: str,
    shop_slug: str | None = None,
) -> ShopBlockedTime:
    query = db.query(ShopBlockedTime).filter(
        ShopBlockedTime.id == blocked_time_id
    )

    if shop_slug:
        query = query.filter(
            ShopBlockedTime.shop_slug == shop_slug
        )

    blocked_time = query.first()

    if not blocked_time:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop blocked time not found.",
        )

    return blocked_time


@router.get("/shop-blocked-times")
def list_shop_blocked_times(
    shop_slug: str,
    db: Session = Depends(get_db),
):
    normalized_shop_slug = clean_shop_slug(shop_slug)

    return (
        db.query(ShopBlockedTime)
        .filter(
            ShopBlockedTime.shop_slug == normalized_shop_slug
        )
        .order_by(
            ShopBlockedTime.start_datetime.asc()
        )
        .all()
    )


@router.post("/shop-blocked-times")
def create_shop_blocked_time(
    payload: ShopBlockedTimeCreate,
    db: Session = Depends(get_db),
):
    shop_slug = clean_shop_slug(
        payload.shop_slug
    )

    clean_reason = validate_reason(
        payload.reason
    )

    validate_datetime_range(
        payload.start_datetime,
        payload.end_datetime,
    )

    if has_shop_appointment_conflict(
        db,
        shop_slug,
        payload.start_datetime,
        payload.end_datetime,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The shop already has an appointment during "
                "this time. Reschedule or cancel the appointment "
                "before closing the shop."
            ),
        )

    if has_shop_block_conflict(
        db,
        shop_slug,
        payload.start_datetime,
        payload.end_datetime,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The shop is already blocked during "
                "part or all of this time."
            ),
        )

    blocked_time = ShopBlockedTime(
        shop_slug=shop_slug,
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
            detail="Shop blocked time could not be created.",
        )

    return blocked_time


@router.post("/shop-blocked-times/recurring")
def create_recurring_shop_blocked_time(
    payload: ShopRecurringBlockedTimeCreate,
    db: Session = Depends(get_db),
):
    shop_slug = clean_shop_slug(
        payload.shop_slug
    )

    clean_reason = validate_reason(
        payload.reason
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
            detail=(
                "Recurring shop blocked time cannot "
                "exceed one year."
            ),
        )

    weekdays = set(
        payload.weekdays
    )

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

        current_date += timedelta(
            days=1
        )

    if not occurrences:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No matching dates were found "
                "for the selected weekdays."
            ),
        )

    for (
        start_datetime,
        end_datetime,
    ) in occurrences:
        if has_shop_appointment_conflict(
            db,
            shop_slug,
            start_datetime,
            end_datetime,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A shop-wide block conflicts with an "
                    f"appointment on {start_datetime:%B %d, %Y}."
                ),
            )

        if has_shop_block_conflict(
            db,
            shop_slug,
            start_datetime,
            end_datetime,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The shop is already blocked during the "
                    f"selected time on {start_datetime:%B %d, %Y}."
                ),
            )

    series_id = str(
        uuid.uuid4()
    )

    blocked_times = [
        ShopBlockedTime(
            shop_slug=shop_slug,
            reason=clean_reason,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            series_id=series_id,
        )
        for (
            start_datetime,
            end_datetime,
        ) in occurrences
    ]

    db.add_all(
        blocked_times
    )

    try:
        db.commit()

        for blocked_time in blocked_times:
            db.refresh(
                blocked_time
            )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Recurring shop blocked time "
                "could not be created."
            ),
        )

    return {
        "success": True,
        "series_id": series_id,
        "occurrences_created": len(
            blocked_times
        ),
        "blocked_times": blocked_times,
    }


@router.delete("/shop-blocked-times/{blocked_time_id}")
def delete_shop_blocked_time(
    blocked_time_id: str,
    db: Session = Depends(get_db),
):
    blocked_time = find_shop_blocked_time(
        db,
        blocked_time_id,
    )

    db.delete(
        blocked_time
    )

    try:
        db.commit()

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Shop blocked time could not be deleted."
            ),
        )

    return {
        "message": "Shop blocked time deleted.",
    }


@router.delete("/shop-blocked-time-series/{series_id}")
def delete_shop_blocked_time_series(
    series_id: str,
    shop_slug: str,
    db: Session = Depends(get_db),
):
    normalized_shop_slug = clean_shop_slug(
        shop_slug
    )

    blocked_times = (
        db.query(ShopBlockedTime)
        .filter(
            ShopBlockedTime.shop_slug
            == normalized_shop_slug,
            ShopBlockedTime.series_id
            == series_id,
        )
        .all()
    )

    if not blocked_times:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop blocked-time series not found.",
        )

    deleted_count = len(
        blocked_times
    )

    for blocked_time in blocked_times:
        db.delete(
            blocked_time
        )

    try:
        db.commit()

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Shop blocked-time series "
                "could not be deleted."
            ),
        )

    return {
        "success": True,
        "occurrences_deleted": deleted_count,
    }
