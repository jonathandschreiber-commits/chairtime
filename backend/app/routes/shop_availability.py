from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ShopAvailabilityRule
from app.schemas import ShopAvailabilityRuleCreate


router = APIRouter()


def clean_shop_slug(value: str) -> str:
    shop_slug = str(value or "").strip().lower()

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shop is required.",
        )

    return shop_slug


@router.get("/shop-availability-rules")
def list_shop_availability_rules(
    shop_slug: str,
    db: Session = Depends(get_db),
):
    normalized_shop_slug = clean_shop_slug(
        shop_slug
    )

    return (
        db.query(ShopAvailabilityRule)
        .filter(
            ShopAvailabilityRule.shop_slug
            == normalized_shop_slug
        )
        .order_by(
            ShopAvailabilityRule.weekday.asc(),
            ShopAvailabilityRule.start_time.asc(),
        )
        .all()
    )


@router.post("/shop-availability-rules")
def create_shop_availability_rule(
    payload: ShopAvailabilityRuleCreate,
    db: Session = Depends(get_db),
):
    shop_slug = clean_shop_slug(
        payload.shop_slug
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

    existing = (
        db.query(ShopAvailabilityRule)
        .filter(
            ShopAvailabilityRule.shop_slug
            == shop_slug,
            ShopAvailabilityRule.weekday
            == payload.weekday,
            ShopAvailabilityRule.start_time
            == payload.start_time,
            ShopAvailabilityRule.end_time
            == payload.end_time,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Those shop hours already exist.",
        )

    rule = ShopAvailabilityRule(
        shop_slug=shop_slug,
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
            detail="Shop hours could not be saved.",
        )

    return rule


@router.delete("/shop-availability-rules/{rule_id}")
def delete_shop_availability_rule(
    rule_id: str,
    db: Session = Depends(get_db),
):
    rule = (
        db.query(ShopAvailabilityRule)
        .filter(
            ShopAvailabilityRule.id == rule_id
        )
        .first()
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop-hours rule not found.",
        )

    db.delete(rule)

    try:
        db.commit()

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Shop hours could not be deleted.",
        )

    return {
        "message": "Shop hours deleted.",
    }
