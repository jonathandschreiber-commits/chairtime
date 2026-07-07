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

    return query.all()


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
        raise HTTPException(status_code=400, detail=str(error))