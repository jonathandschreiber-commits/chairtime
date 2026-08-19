from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Barber, Service
from app.scheduling import generate_available_slots


router = APIRouter()


@router.get("/voice/availability")
def voice_availability(
    shop_slug: str,
    barber_name: str,
    service_name: str,
    target_date: date,
    db: Session = Depends(get_db),
):
    """
    Voice-friendly availability endpoint.

    Allows the AI receptionist to use ordinary names such as
    "Mike" and "Haircut" instead of ChairTime's internal IDs.
    """

    barber = (
        db.query(Barber)
        .filter(
            Barber.shop_slug == shop_slug,
            Barber.name.ilike(barber_name),
        )
        .first()
    )

    if not barber:
        raise HTTPException(
            status_code=404,
            detail=f"Barber '{barber_name}' not found",
        )

    service = (
        db.query(Service)
        .filter(
            Service.shop_slug == shop_slug,
            Service.name.ilike(service_name),
        )
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{service_name}' not found",
        )

    if service.barber_id and service.barber_id != barber.id:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{service_name}' is not available with {barber_name}",
        )

    try:
        slots = generate_available_slots(
            db,
            barber.id,
            service.id,
            target_date,
        )
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    return {
        "success": True,
        "shop_slug": shop_slug,
        "barber": barber.name,
        "service": service.name,
        "target_date": str(target_date),
        "barber_id": barber.id,
        "service_id": service.id,
        "slots": slots,
    }
