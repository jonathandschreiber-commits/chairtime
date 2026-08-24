from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AvailabilityRule
from app.schemas import AvailabilityCreate
from app.scheduling import generate_available_slots

router = APIRouter()


@router.post("/availability-rules")
def create_availability_rule(
    payload: AvailabilityCreate,
    db: Session = Depends(get_db),
):
    existing_rule = (
        db.query(AvailabilityRule)
        .filter(
            AvailabilityRule.barber_id == payload.barber_id,
            AvailabilityRule.weekday == payload.weekday,
            AvailabilityRule.start_time == payload.start_time,
            AvailabilityRule.end_time == payload.end_time,
        )
        .first()
    )

    if existing_rule:
        return existing_rule

    rule = AvailabilityRule(**payload.model_dump())

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return rule


@router.get("/availability-rules")
def list_availability_rules(
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(AvailabilityRule)

    if shop_slug:
        query = query.filter(AvailabilityRule.shop_slug == shop_slug)

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
    db: Session = Depends(get_db),
):
    rules = (
        db.query(AvailabilityRule)
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
        (
            db.query(AvailabilityRule)
            .filter(AvailabilityRule.id.in_(duplicate_ids))
            .delete(synchronize_session=False)
        )

        db.commit()

    return {
        "success": True,
        "duplicates_removed": len(duplicate_ids),
        "remaining_rules": len(seen),
    }


@router.delete("/availability-rules/{rule_id}")
def delete_availability_rule(
    rule_id: str,
    db: Session = Depends(get_db),
):
    rule = (
        db.query(AvailabilityRule)
        .filter(AvailabilityRule.id == rule_id)
        .first()
    )

    if not rule:
        raise HTTPException(
            status_code=404,
            detail="Availability rule not found",
        )

    db.delete(rule)
    db.commit()

    return {
        "message": "Availability rule deleted",
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
