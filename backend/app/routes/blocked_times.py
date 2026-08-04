from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BlockedTime, User
from app.routes.auth import get_current_user
from app.schemas import BlockedTimeCreate


router = APIRouter()


def require_user_shop_slug(current_user: User) -> str:
    shop_slug = str(current_user.shop_slug or "").strip().lower()

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not assigned to a business.",
        )

    return shop_slug


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


def validate_blocked_time(
    payload: BlockedTimeCreate,
) -> None:
    if payload.end_datetime <= payload.start_datetime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End time must be after start time.",
        )

    if not str(payload.reason or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A reason is required.",
        )


# Temporary compatibility endpoint used by existing pages.
@router.post("/blocked-times")
def create_blocked_time(
    payload: BlockedTimeCreate,
    db: Session = Depends(get_db),
):
    validate_blocked_time(payload)

    blocked_time = BlockedTime(
        **payload.model_dump()
    )

    blocked_time.reason = blocked_time.reason.strip()

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


# Temporary compatibility endpoint used by existing pages.
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


# Temporary compatibility endpoint used by existing pages.
@router.delete("/blocked-times/{blocked_time_id}")
def delete_blocked_time(
    blocked_time_id: str,
    db: Session = Depends(get_db),
):
    blocked_time = (
        db.query(BlockedTime)
        .filter(BlockedTime.id == blocked_time_id)
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
        .filter(BlockedTime.shop_slug == shop_slug)
        .order_by(BlockedTime.start_datetime.asc())
        .all()
    )


@router.post("/admin/blocked-times")
def create_admin_blocked_time(
    payload: BlockedTimeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    validate_blocked_time(payload)

    shop_slug = require_user_shop_slug(current_user)

    blocked_time = BlockedTime(
        shop_slug=shop_slug,
        barber_id=payload.barber_id,
        reason=payload.reason.strip(),
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
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