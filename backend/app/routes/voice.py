from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Barber, Service
from app.scheduling import generate_available_slots


router = APIRouter()


class VoiceAvailabilityRequest(BaseModel):
    shop_slug: str
    service_name: str
    target_date: date
    barber_name: str | None = None


def get_voice_availability(
    shop_slug: str,
    service_name: str,
    target_date: date,
    barber_name: str | None,
    db: Session,
):
    """
    Shared availability logic for both GET and POST requests.
    """

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

    cleaned_barber_name = (
        barber_name.strip()
        if barber_name and barber_name.strip()
        else None
    )

    no_preference_values = {
        "any",
        "anyone",
        "any barber",
        "anyone available",
        "no preference",
        "whoever",
        "whoever is available",
    }

    if (
        cleaned_barber_name
        and cleaned_barber_name.lower() in no_preference_values
    ):
        cleaned_barber_name = None

    if cleaned_barber_name:
        barber = (
            db.query(Barber)
            .filter(
                Barber.shop_slug == shop_slug,
                Barber.name.ilike(cleaned_barber_name),
            )
            .first()
        )

        if not barber:
            raise HTTPException(
                status_code=404,
                detail=f"Barber '{cleaned_barber_name}' not found",
            )

    elif service.barber_id:
        barber = (
            db.query(Barber)
            .filter(
                Barber.id == service.barber_id,
                Barber.shop_slug == shop_slug,
            )
            .first()
        )

    else:
        barber = (
            db.query(Barber)
            .filter(Barber.shop_slug == shop_slug)
            .order_by(Barber.name)
            .first()
        )

    if not barber:
        raise HTTPException(
            status_code=404,
            detail="No barber is available for this shop",
        )

    if service.barber_id and service.barber_id != barber.id:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Service '{service_name}' is not available "
                f"with {barber.name}"
            ),
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


@router.get("/voice/availability")
def voice_availability_get(
    shop_slug: str,
    barber_name: str,
    service_name: str,
    target_date: date,
    db: Session = Depends(get_db),
):
    """
    Existing GET endpoint retained for compatibility and testing.
    """

    return get_voice_availability(
        shop_slug=shop_slug,
        barber_name=barber_name,
        service_name=service_name,
        target_date=target_date,
        db=db,
    )


@router.post("/voice/availability")
def voice_availability_post(
    payload: VoiceAvailabilityRequest,
    db: Session = Depends(get_db),
):
    """
    Voice AI availability endpoint for HighLevel.

    Accepts a JSON request body such as:

    {
        "shop_slug": "joebarber",
        "service_name": "Haircut",
        "target_date": "2026-08-21",
        "barber_name": "Barber 1"
    }

    barber_name may be omitted when the caller has no preference.
    """

    return get_voice_availability(
        shop_slug=payload.shop_slug,
        barber_name=payload.barber_name,
        service_name=payload.service_name,
        target_date=payload.target_date,
        db=db,
    )
