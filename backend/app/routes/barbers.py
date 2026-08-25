from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Appointment,
    AvailabilityRule,
    Barber,
    BlockedTime,
    Service,
)
from app.schemas import BarberCreate, BarberUpdate


router = APIRouter()


@router.post("/barbers")
def create_barber(
    payload: BarberCreate,
    db: Session = Depends(get_db),
):
    barber = Barber(
        **payload.model_dump()
    )

    db.add(barber)
    db.commit()
    db.refresh(barber)

    return barber


@router.get("/barbers")
def list_barbers(
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Barber)

    if shop_slug:
        query = query.filter(
            Barber.shop_slug == shop_slug
        )

    return query.all()


@router.delete("/barbers/{barber_id}")
def delete_barber(
    barber_id: str,
    db: Session = Depends(get_db),
):
    barber = (
        db.query(Barber)
        .filter(
            Barber.id == barber_id
        )
        .first()
    )

    if not barber:
        raise HTTPException(
            status_code=404,
            detail="Staff member not found",
        )

    #
    # Preserve appointment history.
    #
    appointment_count = (
        db.query(Appointment)
        .filter(
            Appointment.barber_id == barber_id
        )
        .count()
    )

    if appointment_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{barber.name} cannot be deleted because "
                f"{appointment_count} appointment"
                f"{'' if appointment_count == 1 else 's'} "
                "are associated with this staff member."
            ),
        )

    try:
        #
        # Remove staff-specific configuration first.
        #
        db.query(Service).filter(
            Service.barber_id == barber_id
        ).delete(
            synchronize_session=False
        )

        db.query(AvailabilityRule).filter(
            AvailabilityRule.barber_id == barber_id
        ).delete(
            synchronize_session=False
        )

        db.query(BlockedTime).filter(
            BlockedTime.barber_id == barber_id
        ).delete(
            synchronize_session=False
        )

        #
        # Now the staff member can safely be removed.
        #
        db.delete(barber)
        db.commit()

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                f"{barber.name} could not be deleted."
            ),
        )

    return {
        "message": (
            f"{barber.name} deleted"
        ),
    }


@router.patch("/barbers/{barber_id}")
def update_barber(
    barber_id: str,
    payload: BarberUpdate,
    db: Session = Depends(get_db),
):
    barber = (
        db.query(Barber)
        .filter(
            Barber.id == barber_id
        )
        .first()
    )

    if not barber:
        raise HTTPException(
            status_code=404,
            detail="Staff member not found",
        )

    updates = payload.model_dump(
        exclude_unset=True
    )

    for key, value in updates.items():
        setattr(
            barber,
            key,
            value,
        )

    db.commit()
    db.refresh(barber)

    return barber
