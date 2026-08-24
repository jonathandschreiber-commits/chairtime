from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, Barber, Service
from app.routes.reminders import send_highlevel_sms
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
    "won": "1",
    "juan": "1",
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


NO_PREFERENCE_VALUES = {
    "any",
    "anyone",
    "any barber",
    "anyone available",
    "no preference",
    "whoever",
    "whoever is available",
}


def clean_text(value: str | None):
    if not value:
        return None

    cleaned = " ".join(value.strip().split())

    if not cleaned:
        return None

    return cleaned


def normalize_staff_name(value: str | None):
    """
    Convert a spoken or transcribed staff name into a comparison-friendly
    form.

    Examples:
        Barber One      -> barber 1
        Barbara One     -> barber 1
        Barbara Juan    -> barber 1
        Barber Juan     -> barber 1
        Barber number 1 -> barber 1

    This function is used only for matching. The canonical staff name
    stored in ChairTime is returned to the caller.
    """

    cleaned = clean_text(value)

    if not cleaned:
        return None

    cleaned = cleaned.lower()

    cleaned = re.sub(
        r"[^a-z0-9\s]",
        " ",
        cleaned,
    )

    cleaned = " ".join(cleaned.split())

    if cleaned.startswith("barbara "):
        cleaned = "barber " + cleaned[len("barbara "):]

    if cleaned == "barbara":
        cleaned = "barber"

    cleaned = re.sub(
        r"\bnumber\s+",
        "",
        cleaned,
    )

    words = cleaned.split()
    normalized_words = []

    for word in words:
        replacement = NUMBER_WORDS.get(word)

        if replacement is not None:
            normalized_words.append(replacement)
        else:
            normalized_words.append(word)

    cleaned = " ".join(normalized_words)

    words = cleaned.split()

    number_index = None

    for index, word in enumerate(words):
        if word.isdigit():
            number_index = index
            break

    if number_index is not None:
        meaningful_words = words[: number_index + 1]
        trailing_words = words[number_index + 1 :]

        if trailing_words and all(
            len(word) == 1 and word.isalpha()
            for word in trailing_words
        ):
            words = meaningful_words

    return " ".join(words)


def clean_barber_name(barber_name: str | None):
    cleaned = clean_text(barber_name)

    if not cleaned:
        return None

    if cleaned.lower() in NO_PREFERENCE_VALUES:
        return None

    return cleaned


def similarity_score(first: str, second: str):
    return SequenceMatcher(
        None,
        first,
        second,
    ).ratio()


def find_service(
    db: Session,
    shop_slug: str,
    service_name: str,
):
    cleaned_service_name = clean_text(service_name)

    if not cleaned_service_name:
        raise HTTPException(
            status_code=400,
            detail="Service name is required",
        )

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


def resolve_barber_from_roster(
    db: Session,
    shop_slug: str,
    spoken_name: str,
):
    """
    Resolve a possibly imperfect voice transcription against the actual
    ChairTime barber roster for this shop.

    Matching order:
    1. Exact database match.
    2. Exact normalized match.
    3. Strong fuzzy match, only when sufficiently unambiguous.
    """

    barbers = (
        db.query(Barber)
        .filter(
            Barber.shop_slug == shop_slug,
        )
        .order_by(Barber.name)
        .all()
    )

    if not barbers:
        raise HTTPException(
            status_code=404,
            detail="No barbers are configured for this shop",
        )

    exact_barber = (
        db.query(Barber)
        .filter(
            Barber.shop_slug == shop_slug,
            Barber.name.ilike(spoken_name),
        )
        .first()
    )

    if exact_barber:
        return exact_barber

    normalized_input = normalize_staff_name(spoken_name)

    if not normalized_input:
        raise HTTPException(
            status_code=404,
            detail=f"Barber '{spoken_name}' not found",
        )

    normalized_matches = []

    for barber in barbers:
        normalized_candidate = normalize_staff_name(
            barber.name
        )

        if normalized_candidate == normalized_input:
            normalized_matches.append(barber)

    if len(normalized_matches) == 1:
        return normalized_matches[0]

    if len(normalized_matches) > 1:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "The barber name is ambiguous. "
                    "Please ask the caller which staff member they mean."
                ),
                "heard_name": spoken_name,
                "possible_barbers": [
                    barber.name
                    for barber in normalized_matches
                ],
            },
        )

    scored_matches = []

    for barber in barbers:
        normalized_candidate = normalize_staff_name(
            barber.name
        )

        if not normalized_candidate:
            continue

        score = similarity_score(
            normalized_input,
            normalized_candidate,
        )

        scored_matches.append(
            (
                score,
                barber,
            )
        )

    scored_matches.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    if not scored_matches:
        raise HTTPException(
            status_code=404,
            detail=f"Barber '{spoken_name}' not found",
        )

    best_score, best_barber = scored_matches[0]

    second_best_score = (
        scored_matches[1][0]
        if len(scored_matches) > 1
        else 0.0
    )

    minimum_score = 0.78
    minimum_margin = 0.10

    if best_score < minimum_score:
        raise HTTPException(
            status_code=404,
            detail={
                "message": (
                    "The barber name could not be matched confidently."
                ),
                "heard_name": spoken_name,
                "available_barbers": [
                    barber.name
                    for barber in barbers
                ],
            },
        )

    if (
        len(scored_matches) > 1
        and best_score - second_best_score < minimum_margin
    ):
        likely_matches = [
            barber.name
            for score, barber in scored_matches
            if best_score - score < minimum_margin
        ]

        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "The barber name is ambiguous. "
                    "Please ask the caller to clarify."
                ),
                "heard_name": spoken_name,
                "possible_barbers": likely_matches,
            },
        )

    return best_barber


def find_barber(
    db: Session,
    shop_slug: str,
    service: Service,
    barber_name: str | None,
):
    cleaned_barber_name = clean_barber_name(
        barber_name
    )

    if cleaned_barber_name:
        barber = resolve_barber_from_roster(
            db=db,
            shop_slug=shop_slug,
            spoken_name=cleaned_barber_name,
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

    if (
        service.barber_id
        and service.barber_id != barber.id
    ):
        raise HTTPException(
            status_code=404,
            detail=(
                f"Service '{service.name}' is not available "
                f"with {barber.name}"
            ),
        )

    return barber


def parse_start_time(
    start_time_text: str,
):
    cleaned = clean_text(
        start_time_text
    )

    if not cleaned:
        raise HTTPException(
            status_code=400,
            detail="Appointment start time is required",
        )

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


def build_confirmation_message(
    service_name: str,
    barber_name: str,
    start_datetime: datetime,
):
    """
    Build the immediate SMS sent after a successful booking.
    """

    date_text = start_datetime.strftime(
        "%A, %B %d"
    ).replace(
        " 0",
        " ",
    )

    time_text = start_datetime.strftime(
        "%I:%M %p"
    ).lstrip("0")

    return (
        f"Joe's Barbershop: Your {service_name.lower()} with "
        f"{barber_name} is confirmed for {date_text} at {time_text}. "
        "You'll receive a reminder before your appointment. "
        "Reply STOP to unsubscribe."
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
    customer_name = clean_text(
        payload.customer_name
    )

    customer_phone = clean_text(
        payload.customer_phone
    )

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
        if isinstance(
            slot,
            datetime,
        ):
            available_datetimes.append(
                slot
            )
            continue

        try:
            available_datetimes.append(
                datetime.fromisoformat(
                    str(slot)
                )
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
                "requested_time": (
                    requested_start.isoformat()
                ),
                "available_slots": [
                    slot.isoformat()
                    for slot in available_datetimes
                ],
            },
        )

    requested_end = (
        requested_start
        + timedelta(
            minutes=service.duration_minutes
        )
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
        db.add(
            appointment
        )

        db.commit()

        db.refresh(
            appointment
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="The appointment could not be created",
        )

    #
    # The appointment has already been committed successfully.
    # SMS failure must never undo or invalidate the booking.
    #

    confirmation_message = build_confirmation_message(
        service_name=service.name,
        barber_name=barber.name,
        start_datetime=appointment.start_datetime,
    )

    confirmation_sms_sent = False
    confirmation_sms_error = None

    try:
        sms_result = send_highlevel_sms(
            appointment.customer_phone,
            confirmation_message,
        )

        confirmation_sms_sent = bool(
            sms_result.get("success")
        )

        if not confirmation_sms_sent:
            confirmation_sms_error = (
                sms_result.get("error")
                or "Confirmation SMS could not be sent"
            )

    except Exception as sms_error:
        confirmation_sms_sent = False
        confirmation_sms_error = str(
            sms_error
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
        "start_datetime": (
            appointment.start_datetime.isoformat()
        ),
        "end_datetime": (
            appointment.end_datetime.isoformat()
        ),
        "status": appointment.status,
        "confirmation_sms_sent": confirmation_sms_sent,
        "confirmation_sms_error": confirmation_sms_error,
        "reminder_scheduled": True,
        "reminder_sent": appointment.reminder_sent,
    }
