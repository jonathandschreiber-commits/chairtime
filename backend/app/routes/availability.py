from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AvailabilityRule, Barber, User
from app.routes.auth import get_current_user
from app.schemas import AvailabilityCreate
from app.scheduling import generate_available_slots

router = APIRouter()


def clean_shop_slug(value: str) -> str:
    shop_slug = str(value or "").strip().lower()

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shop is required.",
        )

    return shop_slug


def require_owner_shop_slug(
    current_user: User,
) -> str:
    shop_slug = str(
        current_user.shop_slug or ""
    ).strip().lower()

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not assigned to a business.",
        )

    role = str(
        current_user.role or ""
    ).strip().lower()

    if role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the business owner can manage staff availability.",
        )

    return shop_slug


@router.post("/availability-rules")
def create_availability_rule(
    payload: AvailabilityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_shop_slug = require_owner_shop_slug(
        current_user
    )

    requested_shop_slug = clean_shop_slug(
        payload.shop_slug
    )

    if requested_shop_slug != owner_shop_slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot manage another business's staff availability.",
        )

    barber = (
        db.query(Barber)
        .filter(
            Barber.id == payload.barber_id,
            Barber.shop_slug == owner_shop_slug,
        )
        .first()
    )

    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found.",
        )

    if payload.weekday < 0 or payload.weekday > 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Weekday must be between 0 and 6.",
        )

    if payload.end_time <= payload.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End time must be after start time.",
        )

    existing_rule = (
        db.query(AvailabilityRule)
        .filter(
            AvailabilityRule.shop_slug
            == owner_shop_slug,
            AvailabilityRule.barber_id
            == payload.barber_id,
            AvailabilityRule.weekday
            == payload.weekday,
            AvailabilityRule.start_time
            == payload.start_time,
            AvailabilityRule.end_time
            == payload.end_time,
        )
        .first()
    )

    if existing_rule:
        return existing_rule

    rule = AvailabilityRule(
        shop_slug=owner_shop_slug,
        barber_id=payload.barber_id,
        weekday=payload.weekday,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )

    db.add(rule)

    try:
        db.commit()
        db.refresh(rule)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Staff availability could not be saved.",
        )

    return rule


@router.get("/availability-rules")
def list_availability_rules(
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(AvailabilityRule)

    if shop_slug:
        query = query.filter(
            AvailabilityRule.shop_slug
            == clean_shop_slug(shop_slug)
        )

    return (
        query.order_by(
            AvailabilityRule.barber_id,
            AvailabilityRule.weekday,
            AvailabilityRule.start_time,
        )
        .all()
    )


@router.post("/availability-rules/remove-duplicates")
def remove_duplicate_availability_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_shop_slug = require_owner_shop_slug(
        current_user
    )

    rules = (
        db.query(AvailabilityRule)
        .filter(
            AvailabilityRule.shop_slug
            == owner_shop_slug
        )
        .order_by(
            AvailabilityRule.barber_id,
            AvailabilityRule.weekday,
            AvailabilityRule.start_time,
            AvailabilityRule.end_time,
        )
        .all()
    )

    seen = set()
    duplicate_ids = []

    for rule in rules:
        key = (
            rule.barber_id,
            rule.weekday,
            str(rule.start_time),
            str(rule.end_time),
        )

        if key in seen:
            duplicate_ids.append(rule.id)
        else:
            seen.add(key)

    if duplicate_ids:
        try:
            (
                db.query(AvailabilityRule)
                .filter(
                    AvailabilityRule.shop_slug
                    == owner_shop_slug,
                    AvailabilityRule.id.in_(
                        duplicate_ids
                    ),
                )
                .delete(
                    synchronize_session=False
                )
            )

            db.commit()

        except Exception:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Duplicate availability rules could not be removed.",
            )

    return {
        "success": True,
        "duplicates_removed": len(
            duplicate_ids
        ),
        "remaining_rules": len(seen),
    }


@router.delete("/availability-rules/{rule_id}")
def delete_availability_rule(
    rule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_shop_slug = require_owner_shop_slug(
        current_user
    )

    rule = (
        db.query(AvailabilityRule)
        .filter(
            AvailabilityRule.id == rule_id,
            AvailabilityRule.shop_slug
            == owner_shop_slug,
        )
        .first()
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability rule not found.",
        )

    db.delete(rule)

    try:
        db.commit()

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Staff availability could not be deleted.",
        )

    return {
        "message": "Availability rule deleted.",
    }


@router.get("/availability")
def get_availability(
    barber_id: str,
    service_id: str,
    target_date: date,
    db: Session = Depends(get_db),
):
    try:
        slots = generate_available_slots(
            db,
            barber_id,
            service_id,
            target_date,
        )

        return {"slots": slots}

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
