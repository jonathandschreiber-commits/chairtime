from datetime import date, datetime, timedelta
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, Barber, Service
from app.scheduling import generate_available_slots


router = APIRouter()


class VoiceAvailabilityRequest(BaseModel):
    shop_slug: str
    service_name: str
    target_date: date
    barber_name: str | None = None


class VoiceBookingRequest(BaseModel):
    shop_slug: str
    service_name: str
    target_date: date
    start_time: str
    customer_name: str
    customer_phone: str
    barber_name: str | None = None


NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
}


def normalize_spoken_barber_name(barber_name: str | None):
    """
    Normalize natural speech versions of staff names.

    Examples:
    "Barber One" -> "Barber 1"
    "barber two" -> "barber 2"
    "Barber number three" -> "Barber 3"
    """

    if not barber_name:
        return None

    cleaned = " ".join(barber_name.strip().split())

    if not cleaned:
        return None

    cleaned = re.sub(
        r"\bnumber\s+(?=(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\b)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    for word, digit in NUMBER_WORDS.items():
        cleaned = re.sub(
            rf"\b{word}\b",
            digit,
            cleaned,
            flags=re.IGNORECASE,
        )

    return " ".join(cleaned.split())


def clean_barber_name(barber_name: str | None):
    if not barber_name:
        return None

    cleaned = barber_name.strip()

    if not cleaned:
        return None

    no_preference_values = {
        "any",
        "anyone",
        "any barber",
        "anyone available",
        "no preference",
        "whoever",
        "whoever is available",
    }

    if cleaned.lower() in no_preference_values:
        return None

    return cleaned


def find_service(
    db: Session,
    shop_slug: str,
    service_name: str,
):
    cleaned_service_name = service_name.strip()

    service = (
        db.query(Service)
        .filter(
            Service.shop_slug == shop_slug,
            Service.name.ilike(cleaned_service_name),
        )
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{service_name}' not found",
        )

    return service


def find_barber(
    db: Session,
    shop_slug: str,
    service: Service,
    barber_name: str | None,
):
    cleaned_barber_name = clean_barber_name(barber_name)

    if cleaned_barber_name:
        # First try exactly what the voice system supplied.
        barber = (
            db.query(Barber)
            .filter(
                Barber.shop_slug == shop_slug,
                Barber.name.ilike(cleaned_barber_name),
            )
            .first()
        )

        # If that fails, normalize spoken numbers:
        # "Barber One" -> "Barber 1"
        if not barber:
            normalized_barber_name = normalize_spoken_barber_name(
                cleaned_barber_name
            )

            if normalized_barber_name:
                barber = (
                    db.query(Barber)
                    .filter(
                        Barber.shop_slug == shop_slug,
                        Barber.name.ilike(normalized_barber_name),
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
            .filter(
                Barber.shop_slug == shop_slug,
            )
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
                f"Service '{service.name}' is not available "
                f"with {barber.name}"
            ),
        )

    return barber


def parse_start_time(start_time_text: str):
    cleaned = start_time_text.strip()

    formats = [
        "%H:%M",
        "%H:%M:%S",
        "%I:%M %p",
        "%I:%M%p",
        "%I %p",
        "%I%p",
    ]

    for format_string in formats:
        try:
            parsed = datetime.strptime(
                cleaned,
                format_string,
            )
            return parsed.time()
        except ValueError:
            continue

    raise HTTPException(
        status_code=400,
        detail=(
            "Invalid start_time. Use a time such as "
            "'13:30' or '1:30 PM'."
        ),
    )


def get_voice_availability(
    shop_slug: str,
    service_name: str,
    target_date: date,
    barber_name: str | None,
    db: Session,
):
    service = find_service(
        db=db,
        shop_slug=shop_slug,
        service_name=service_name,
    )

    barber = find_barber(
        db=db,
        shop_slug=shop_slug,
        service=service,
        barber_name=barber_name,
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
    return get_voice_availability(
        shop_slug=payload.shop_slug,
        barber_name=payload.barber_name,
        service_name=payload.service_name,
        target_date=payload.target_date,
        db=db,
    )


@router.post("/voice/book")
def voice_book_appointment(
    payload: VoiceBookingRequest,
    db: Session = Depends(get_db),
):
    customer_name = payload.customer_name.strip()
    customer_phone = payload.customer_phone.strip()

    if not customer_name:
        raise HTTPException(
            status_code=400,
            detail="Customer name is required",
        )

    if not customer_phone:
        raise HTTPException(
            status_code=400,
            detail="Customer phone number is required",
        )

    service = find_service(
        db=db,
        shop_slug=payload.shop_slug,
        service_name=payload.service_name,
    )

    barber = find_barber(
        db=db,
        shop_slug=payload.shop_slug,
        service=service,
        barber_name=payload.barber_name,
    )

    requested_time = parse_start_time(
        payload.start_time
    )

    requested_start = datetime.combine(
        payload.target_date,
        requested_time,
    )

    try:
        available_slots = generate_available_slots(
            db,
            barber.id,
            service.id,
            payload.target_date,
        )
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    available_datetimes = []

    for slot in available_slots:
        if isinstance(slot, datetime):
            available_datetimes.append(slot)
            continue

        try:
            available_datetimes.append(
                datetime.fromisoformat(str(slot))
            )
        except ValueError:
            continue

    if requested_start not in available_datetimes:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "The requested appointment time "
                    "is no longer available"
                ),
                "requested_time": requested_start.isoformat(),
                "available_slots": [
                    slot.isoformat()
                    for slot in available_datetimes
                ],
            },
        )

    requested_end = requested_start + timedelta(
        minutes=service.duration_minutes
    )

    appointment = Appointment(
        shop_slug=payload.shop_slug,
        barber_id=barber.id,
        service_id=service.id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        start_datetime=requested_start,
        end_datetime=requested_end,
        status="confirmed",
        reminder_sent=False,
    )

    try:
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="The appointment could not be created",
        )

    return {
        "success": True,
        "message": "Appointment successfully created",
        "appointment_id": appointment.id,
        "shop_slug": payload.shop_slug,
        "barber": barber.name,
        "service": service.name,
        "customer_name": appointment.customer_name,
        "customer_phone": appointment.customer_phone,
        "start_datetime": appointment.start_datetime.isoformat(),
        "end_datetime": appointment.end_datetime.isoformat(),
        "status": appointment.status,
        "reminder_sent": appointment.reminder_sent,
    }
