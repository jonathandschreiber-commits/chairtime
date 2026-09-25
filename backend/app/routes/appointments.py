
import os
from datetime import datetime, timedelta

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.booking_lock import lock_booking_provider
from app.database import get_db
from app.models import (
    Appointment,
    Barber,
    BlockedTime,
    Service,
    Shop,
    User,
)
from app.routes.auth import get_current_user
from app.routes.reminders import send_highlevel_sms
from app.schemas import AppointmentCreate


router = APIRouter()

ALLOWED_APPOINTMENT_STATUSES = {
    "confirmed",
    "completed",
    "no_show",
    "canceled",
}


def get_stripe_secret_key() -> str:
    secret_key = os.getenv("STRIPE_SECRET_KEY")

    if not secret_key:
        raise RuntimeError(
            "STRIPE_SECRET_KEY environment variable is missing."
        )

    return secret_key


def get_stripe_id(value) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        clean_value = value.strip()
        return clean_value or None

    object_id = getattr(
        value,
        "id",
        None,
    )

    if object_id:
        clean_value = str(
            object_id
        ).strip()

        return clean_value or None

    return None


def require_user_shop_slug(current_user: User) -> str:
    shop_slug = str(
        current_user.shop_slug or ""
    ).strip().lower()

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your account is not assigned "
                "to a business."
            ),
        )

    return shop_slug


def find_shop_appointment(
    db: Session,
    appointment_id: str,
    shop_slug: str,
) -> Appointment:
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.shop_slug == shop_slug,
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    return appointment


def find_shop(
    db: Session,
    shop_slug: str,
) -> Shop:
    shop = (
        db.query(Shop)
        .filter(
            Shop.slug == shop_slug,
        )
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found.",
        )

    return shop


def find_appointment_barber(
    db: Session,
    appointment: Appointment,
    shop_slug: str,
) -> Barber:
    barber = (
        db.query(Barber)
        .filter(
            Barber.id == appointment.barber_id,
            Barber.shop_slug == shop_slug,
        )
        .first()
    )

    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found.",
        )

    return barber


def find_appointment_service(
    db: Session,
    appointment: Appointment,
    shop_slug: str,
) -> Service:
    service = (
        db.query(Service)
        .filter(
            Service.id == appointment.service_id,
            Service.shop_slug == shop_slug,
            Service.barber_id == appointment.barber_id,
        )
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Service is not available for "
                "this staff member."
            ),
        )

    return service


def find_service_for_barber(
    db: Session,
    service_id: str,
    barber_id: str,
    shop_slug: str,
) -> Service:
    """
    Return a service only when it belongs to the
    authenticated/requested business AND is assigned
    to the selected staff member.

    This prevents a caller from combining a valid
    service ID with a different provider's ID by
    bypassing the ChairTime frontend.
    """

    service = (
        db.query(Service)
        .filter(
            Service.id == service_id,
            Service.shop_slug == shop_slug,
            Service.barber_id == barber_id,
            Service.is_active.is_(True),
        )
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The selected service is not offered "
                "by this staff member."
            ),
        )

    return service


def staff_can_manage_other_staff_appointments(
    db: Session,
    shop_slug: str,
) -> bool:
    shop = find_shop(
        db,
        shop_slug,
    )

    return bool(
        shop.staff_can_manage_other_staff_appointments
    )


def require_appointment_modify_permission(
    db: Session,
    current_user: User,
    appointment: Appointment,
    shop_slug: str,
) -> None:
    role = str(
        current_user.role or ""
    ).strip().lower()

    if role == "owner":
        return

    if role != "staff":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not have permission "
                "to modify appointments."
            ),
        )

    if staff_can_manage_other_staff_appointments(
        db,
        shop_slug,
    ):
        return

    barber_id = str(
        current_user.barber_id or ""
    ).strip()

    if not barber_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your staff login is not linked "
                "to a service provider."
            ),
        )

    if str(appointment.barber_id) != barber_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Employees may modify only their "
                "own appointments."
            ),
        )


def require_appointment_create_permission(
    db: Session,
    current_user: User,
    barber_id: str,
    shop_slug: str,
) -> None:
    role = str(
        current_user.role or ""
    ).strip().lower()

    if role == "owner":
        return

    if role != "staff":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not have permission "
                "to create appointments."
            ),
        )

    if staff_can_manage_other_staff_appointments(
        db,
        shop_slug,
    ):
        return

    current_user_barber_id = str(
        current_user.barber_id or ""
    ).strip()

    if not current_user_barber_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your staff login is not linked "
                "to a service provider."
            ),
        )

    if (
        str(barber_id or "").strip()
        != current_user_barber_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Employees may create appointments "
                "only for themselves."
            ),
        )


def parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid appointment date and time.",
        )


def calculate_appointment_end(
    start_datetime: datetime,
    service: Service,
) -> datetime:
    return start_datetime + timedelta(
        minutes=service.duration_minutes
    )


def verify_no_reschedule_conflict(
    db: Session,
    appointment: Appointment,
    new_start: datetime,
    new_end: datetime,
    shop_slug: str,
) -> None:
    appointment_conflict = (
        db.query(Appointment)
        .filter(
            Appointment.shop_slug == shop_slug,
            Appointment.barber_id
            == appointment.barber_id,
            Appointment.id != appointment.id,
            Appointment.status != "canceled",
            Appointment.start_datetime < new_end,
            Appointment.end_datetime > new_start,
        )
        .first()
    )

    if appointment_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That time is already booked.",
        )

    blocked_conflict = (
        db.query(BlockedTime)
        .filter(
            BlockedTime.shop_slug == shop_slug,
            BlockedTime.barber_id
            == appointment.barber_id,
            BlockedTime.start_datetime < new_end,
            BlockedTime.end_datetime > new_start,
        )
        .first()
    )

    if blocked_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That time is blocked.",
        )


def send_customer_sms(
    customer_phone: str,
    message: str,
    message_type: str,
) -> None:
    clean_phone = str(
        customer_phone or ""
    ).strip()

    if not clean_phone:
        return

    sms_result = send_highlevel_sms(
        clean_phone,
        message,
    )

    if not sms_result.get("success"):
        print(
            f"{message_type} SMS first attempt failed:",
            sms_result,
        )

        sms_result = send_highlevel_sms(
            clean_phone,
            message,
        )

        if not sms_result.get("success"):
            print(
                f"{message_type} SMS retry failed:",
                sms_result,
            )


def format_appointment_datetime(
    appointment: Appointment,
) -> str:
    return appointment.start_datetime.strftime(
        "%A, %B %d at %I:%M %p"
    )


def send_appointment_confirmation(
    appointment: Appointment,
    shop: Shop,
    barber: Barber,
    service: Service,
) -> None:
    message = (
        f"{shop.name}: Your {service.name} appointment "
        f"with {barber.name} is confirmed for "
        f"{format_appointment_datetime(appointment)}. "
        "Reply STOP to unsubscribe."
    )

    send_customer_sms(
        appointment.customer_phone,
        message,
        "Appointment confirmation",
    )


def send_reschedule_confirmation(
    appointment: Appointment,
    shop: Shop,
    barber: Barber,
    service: Service,
) -> None:
    message = (
        f"{shop.name}: Your {service.name} appointment "
        f"with {barber.name} has been rescheduled to "
        f"{format_appointment_datetime(appointment)}. "
        "Reply STOP to unsubscribe."
    )

    send_customer_sms(
        appointment.customer_phone,
        message,
        "Appointment reschedule",
    )


def send_cancellation_confirmation(
    appointment: Appointment,
    shop: Shop,
    barber: Barber,
    service: Service,
) -> None:
    message = (
        f"{shop.name}: Your {service.name} appointment "
        f"with {barber.name} for "
        f"{format_appointment_datetime(appointment)} "
        "has been canceled. "
        "Reply STOP to unsubscribe."
    )

    send_customer_sms(
        appointment.customer_phone,
        message,
        "Appointment cancellation",
    )


def apply_reschedule(
    db: Session,
    appointment: Appointment,
    new_start: datetime,
    new_end: datetime,
    shop: Shop,
    barber: Barber,
    service: Service,
) -> Appointment:
    appointment.start_datetime = new_start
    appointment.end_datetime = new_end
    appointment.status = "confirmed"
    appointment.reminder_sent = False
    appointment.reminder_sent_at = None

    try:
        db.commit()
        db.refresh(appointment)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The appointment could not be moved."
            ),
        )

    send_reschedule_confirmation(
        appointment,
        shop,
        barber,
        service,
    )

    return appointment


def verify_booking_setup_intent(
    shop: Shop,
    setup_intent_id: str | None,
) -> tuple[
    str | None,
    str | None,
    str | None,
]:
    """
    Verify the Stripe SetupIntent for a shop that
    requires a card to reserve an appointment.

    Stripe Customer and PaymentMethod IDs are obtained
    directly from Stripe rather than trusted from the
    browser.

    Older SetupIntents created before Stripe Customer
    support may legitimately have no customer. Those
    remain valid during the frontend transition.
    """

    if shop.payment_policy != "card_required":
        return None, None, None

    clean_setup_intent_id = str(
        setup_intent_id or ""
    ).strip()

    if not clean_setup_intent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A verified card is required "
                "to reserve this appointment."
            ),
        )

    if not shop.stripe_connect_account_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "This business cannot accept "
                "card reservations right now."
            ),
        )

    try:
        stripe.api_key = get_stripe_secret_key()

        setup_intent = stripe.SetupIntent.retrieve(
            clean_setup_intent_id,
            stripe_account=(
                shop.stripe_connect_account_id
            ),
        )

    except RuntimeError as error:
        print(
            "Stripe configuration error:",
            error,
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Card verification is temporarily "
                "unavailable."
            ),
        )

    except stripe.StripeError as error:
        print(
            "Stripe SetupIntent retrieval failed:",
            error,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The card verification could "
                "not be confirmed."
            ),
        )

    if setup_intent.status != "succeeded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The card has not been "
                "successfully verified."
            ),
        )

    metadata = (
        setup_intent.metadata.to_dict()
        if setup_intent.metadata
        else {}
    )

    metadata_shop_id = str(
        metadata.get("shop_id") or ""
    ).strip()

    metadata_shop_slug = str(
        metadata.get("shop_slug") or ""
    ).strip().lower()

    if (
        metadata_shop_id != str(shop.id)
        or metadata_shop_slug != shop.slug.lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The card verification does not "
                "belong to this business."
            ),
        )

    payment_method_id = get_stripe_id(
        setup_intent.payment_method
    )

    if not payment_method_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No verified payment method "
                "was found."
            ),
        )

    stripe_customer_id = get_stripe_id(
        setup_intent.customer
    )

    metadata_customer_id = str(
        metadata.get("stripe_customer_id") or ""
    ).strip()

    if (
        stripe_customer_id
        and metadata_customer_id
        and stripe_customer_id
        != metadata_customer_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The verified customer information "
                "does not match this reservation."
            ),
        )

    if (
        not stripe_customer_id
        and metadata_customer_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The verified customer information "
                "is incomplete."
            ),
        )

    return (
        stripe_customer_id,
        clean_setup_intent_id,
        payment_method_id,
    )


def verify_new_appointment_conflicts(
    db: Session,
    shop_slug: str,
    barber_id: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> None:
    appointment_conflict = (
        db.query(Appointment)
        .filter(
            Appointment.shop_slug == shop_slug,
            Appointment.barber_id == barber_id,
            Appointment.status != "canceled",
            Appointment.start_datetime < end_datetime,
            Appointment.end_datetime > start_datetime,
        )
        .first()
    )

    if appointment_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That time is already booked.",
        )

    blocked_conflict = (
        db.query(BlockedTime)
        .filter(
            BlockedTime.shop_slug == shop_slug,
            BlockedTime.barber_id == barber_id,
            BlockedTime.start_datetime < end_datetime,
            BlockedTime.end_datetime > start_datetime,
        )
        .first()
    )

    if blocked_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That time is blocked.",
        )


def save_new_appointment(
    db: Session,
    shop: Shop,
    shop_slug: str,
    barber: Barber,
    service: Service,
    payload: AppointmentCreate,
    stripe_customer_id: str | None = None,
    stripe_setup_intent_id: str | None = None,
    stripe_payment_method_id: str | None = None,
) -> Appointment:
    customer_name = str(
        payload.customer_name or ""
    ).strip()

    customer_phone = str(
        payload.customer_phone or ""
    ).strip()

    if not customer_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer name is required.",
        )

    if not customer_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer phone number is required.",
        )

    end_datetime = calculate_appointment_end(
        payload.start_datetime,
        service,
    )

    # Lock the provider before checking conflicts.
    # PostgreSQL holds this lock through db.commit().

    lock_booking_provider(
        db=db,
        shop_slug=shop_slug,
        barber_id=str(barber.id),
    )

    verify_new_appointment_conflicts(
        db,
        shop_slug,
        str(barber.id),
        payload.start_datetime,
        end_datetime,
    )

    appointment = Appointment(
        shop_slug=shop_slug,
        barber_id=barber.id,
        service_id=service.id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_tags=payload.customer_tags,
        customer_notes=payload.customer_notes,
        notes=payload.notes,
        start_datetime=payload.start_datetime,
        end_datetime=end_datetime,
        stripe_customer_id=stripe_customer_id,
        stripe_setup_intent_id=stripe_setup_intent_id,
        stripe_payment_method_id=stripe_payment_method_id,
    )

    db.add(appointment)

    try:
        db.commit()
        db.refresh(appointment)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The appointment could not "
                "be created."
            ),
        )

    send_appointment_confirmation(
        appointment,
        shop,
        barber,
        service,
    )

    return appointment


@router.post("/appointments")
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
):
    """
    Public customer-booking endpoint.

    This route intentionally does not require an
    authenticated ChairTime owner/staff account.
    """

    shop_slug = str(
        payload.shop_slug or ""
    ).strip().lower()

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business is required.",
        )

    shop = find_shop(
        db,
        shop_slug,
    )

    barber_id = str(
        payload.barber_id or ""
    ).strip()

    if not barber_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff member is required.",
        )

    barber = (
        db.query(Barber)
        .filter(
            Barber.id == barber_id,
            Barber.shop_slug == shop_slug,
        )
        .first()
    )

    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found.",
        )

    service_id = str(
        payload.service_id or ""
    ).strip()

    if not service_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service is required.",
        )

    service = find_service_for_barber(
        db,
        service_id,
        barber_id,
        shop_slug,
    )

    (
        stripe_customer_id,
        stripe_setup_intent_id,
        stripe_payment_method_id,
    ) = verify_booking_setup_intent(
        shop,
        payload.stripe_setup_intent_id,
    )

    return save_new_appointment(
        db=db,
        shop=shop,
        shop_slug=shop_slug,
        barber=barber,
        service=service,
        payload=payload,
        stripe_customer_id=stripe_customer_id,
        stripe_setup_intent_id=stripe_setup_intent_id,
        stripe_payment_method_id=stripe_payment_method_id,
    )


@router.post("/admin/appointments")
def create_admin_appointment(
    payload: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create an appointment from the ChairTime admin UI.

    The logged-in user's shop determines the tenant.
    Owners may create appointments for any provider.
    Staff permissions are governed by the shop's
    staff appointment-management setting.
    """

    shop_slug = require_user_shop_slug(
        current_user
    )

    shop = find_shop(
        db,
        shop_slug,
    )

    barber_id = str(
        payload.barber_id or ""
    ).strip()

    if not barber_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff member is required.",
        )

    require_appointment_create_permission(
        db,
        current_user,
        barber_id,
        shop_slug,
    )

    barber = (
        db.query(Barber)
        .filter(
            Barber.id == barber_id,
            Barber.shop_slug == shop_slug,
        )
        .first()
    )

    if not barber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found.",
        )

    service_id = str(
        payload.service_id or ""
    ).strip()

    if not service_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service is required.",
        )

    service = find_service_for_barber(
        db,
        service_id,
        barber_id,
        shop_slug,
    )

    return save_new_appointment(
        db=db,
        shop=shop,
        shop_slug=shop_slug,
        barber=barber,
        service=service,
        payload=payload,
    )


@router.get("/admin/appointments")
def list_admin_appointments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return appointments for the authenticated user's shop.
    Staff may view the entire shop schedule.
    """

    shop_slug = require_user_shop_slug(current_user)

    return (
        db.query(Appointment)
        .filter(Appointment.shop_slug == shop_slug)
        .order_by(Appointment.start_datetime.asc())
        .all()
    )


@router.patch("/admin/appointments/{appointment_id}/cancel")
def cancel_admin_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancel an appointment and notify the customer.
    """

    shop_slug = require_user_shop_slug(current_user)

    appointment = find_shop_appointment(
        db,
        appointment_id,
        shop_slug,
    )

    require_appointment_modify_permission(
        db,
        current_user,
        appointment,
        shop_slug,
    )

    old_status = str(
        appointment.status or ""
    ).strip().lower()

    shop = None
    barber = None
    service = None

    if old_status != "canceled":
        shop = find_shop(db, shop_slug)

        barber = find_appointment_barber(
            db,
            appointment,
            shop_slug,
        )

        service = find_appointment_service(
            db,
            appointment,
            shop_slug,
        )

    appointment.status = "canceled"

    try:
        db.commit()
        db.refresh(appointment)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The appointment could not be canceled.",
        )

    if (
        old_status != "canceled"
        and shop is not None
        and barber is not None
        and service is not None
    ):
        send_cancellation_confirmation(
            appointment,
            shop,
            barber,
            service,
        )

    return appointment


@router.patch("/admin/appointments/{appointment_id}/status")
def update_admin_appointment_status(
    appointment_id: str,
    appointment_status: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update appointment status.

    Before restoring a canceled appointment, lock its
    provider and verify that the original time has not
    been booked by another customer.
    """

    if appointment_status not in ALLOWED_APPOINTMENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid appointment status.",
        )

    shop_slug = require_user_shop_slug(current_user)

    appointment = find_shop_appointment(
        db,
        appointment_id,
        shop_slug,
    )

    require_appointment_modify_permission(
        db,
        current_user,
        appointment,
        shop_slug,
    )

    if appointment_status != "canceled":
        lock_booking_provider(
            db=db,
            shop_slug=shop_slug,
            barber_id=str(appointment.barber_id),
        )

        # Refresh after acquiring the lock so we do not
        # make a decision using stale appointment data.
        db.refresh(appointment)

    old_status = str(
        appointment.status or ""
    ).strip().lower()

    if (
        old_status == "canceled"
        and appointment_status != "canceled"
    ):
        verify_no_reschedule_conflict(
            db,
            appointment,
            appointment.start_datetime,
            appointment.end_datetime,
            shop_slug,
        )

    shop = None
    barber = None
    service = None

    if (
        appointment_status == "canceled"
        and old_status != "canceled"
    ):
        shop = find_shop(db, shop_slug)

        barber = find_appointment_barber(
            db,
            appointment,
            shop_slug,
        )

        service = find_appointment_service(
            db,
            appointment,
            shop_slug,
        )

    appointment.status = appointment_status

    try:
        db.commit()
        db.refresh(appointment)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The appointment status could not be updated.",
        )

    if (
        appointment_status == "canceled"
        and old_status != "canceled"
        and shop is not None
        and barber is not None
        and service is not None
    ):
        send_cancellation_confirmation(
            appointment,
            shop,
            barber,
            service,
        )

    return appointment


@router.patch("/admin/appointments/{appointment_id}/reschedule")
def reschedule_admin_appointment(
    appointment_id: str,
    new_start_datetime: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reschedule an appointment.

    Lock the provider before checking conflicts so
    another request cannot book the same time while
    this appointment is being moved.
    """

    shop_slug = require_user_shop_slug(current_user)

    appointment = find_shop_appointment(
        db,
        appointment_id,
        shop_slug,
    )

    require_appointment_modify_permission(
        db,
        current_user,
        appointment,
        shop_slug,
    )

    shop = find_shop(db, shop_slug)

    barber = find_appointment_barber(
        db,
        appointment,
        shop_slug,
    )

    service = find_appointment_service(
        db,
        appointment,
        shop_slug,
    )

    new_start = parse_datetime(new_start_datetime)

    new_end = calculate_appointment_end(
        new_start,
        service,
    )

    lock_booking_provider(
        db=db,
        shop_slug=shop_slug,
        barber_id=str(appointment.barber_id),
    )

    verify_no_reschedule_conflict(
        db,
        appointment,
        new_start,
        new_end,
        shop_slug,
    )

    return apply_reschedule(
        db,
        appointment,
        new_start,
        new_end,
        shop,
        barber,
        service,
    )


@router.patch("/admin/appointments/{appointment_id}/notes")
def update_admin_appointment_notes(
    appointment_id: str,
    notes: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update appointment notes.
    """

    shop_slug = require_user_shop_slug(current_user)

    appointment = find_shop_appointment(
        db,
        appointment_id,
        shop_slug,
    )

    require_appointment_modify_permission(
        db,
        current_user,
        appointment,
        shop_slug,
    )

    appointment.notes = notes

    try:
        db.commit()
        db.refresh(appointment)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The appointment notes could not be updated.",
        )

    return appointment


# ---------------------------------------------------------
# Authenticated compatibility routes
# ---------------------------------------------------------
#
# These routes preserve older ChairTime endpoint paths.
# All operations require authentication and are scoped
# to the logged-in user's business.
#
# New frontend code should use /admin/appointments.
# ---------------------------------------------------------


@router.get("/appointments")
def list_appointments_compatibility(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Legacy appointment-list endpoint.

    Staff may view the entire shop schedule.
    """

    shop_slug = require_user_shop_slug(current_user)

    return (
        db.query(Appointment)
        .filter(Appointment.shop_slug == shop_slug)
        .order_by(Appointment.start_datetime.asc())
        .all()
    )


@router.patch("/appointments/{appointment_id}/cancel")
def cancel_appointment_compatibility(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Legacy cancellation endpoint with authentication,
    tenant isolation, staff permissions, and SMS.
    """

    shop_slug = require_user_shop_slug(current_user)

    appointment = find_shop_appointment(
        db,
        appointment_id,
        shop_slug,
    )

    require_appointment_modify_permission(
        db,
        current_user,
        appointment,
        shop_slug,
    )

    old_status = str(
        appointment.status or ""
    ).strip().lower()

    shop = None
    barber = None
    service = None

    if old_status != "canceled":
        shop = find_shop(db, shop_slug)

        barber = find_appointment_barber(
            db,
            appointment,
            shop_slug,
        )

        service = find_appointment_service(
            db,
            appointment,
            shop_slug,
        )

    appointment.status = "canceled"

    try:
        db.commit()
        db.refresh(appointment)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The appointment could not be canceled.",
        )

    if (
        old_status != "canceled"
        and shop is not None
        and barber is not None
        and service is not None
    ):
        send_cancellation_confirmation(
            appointment,
            shop,
            barber,
            service,
        )

    return appointment


@router.patch("/appointments/{appointment_id}/status")
def update_appointment_status_compatibility(
    appointment_id: str,
    status_value: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Legacy status endpoint.

    Restoring a canceled appointment requires a
    provider lock and a fresh conflict check.
    """

    if status_value not in ALLOWED_APPOINTMENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid appointment status.",
        )

    shop_slug = require_user_shop_slug(current_user)

    appointment = find_shop_appointment(
        db,
        appointment_id,
        shop_slug,
    )

    require_appointment_modify_permission(
        db,
        current_user,
        appointment,
        shop_slug,
    )

    if status_value != "canceled":
        lock_booking_provider(
            db=db,
            shop_slug=shop_slug,
            barber_id=str(appointment.barber_id),
        )

        # Re-read the appointment after acquiring
        # the provider lock.
        db.refresh(appointment)

    old_status = str(
        appointment.status or ""
    ).strip().lower()

    if (
        old_status == "canceled"
        and status_value != "canceled"
    ):
        verify_no_reschedule_conflict(
            db,
            appointment,
            appointment.start_datetime,
            appointment.end_datetime,
            shop_slug,
        )

    shop = None
    barber = None
    service = None

    if (
        status_value == "canceled"
        and old_status != "canceled"
    ):
        shop = find_shop(db, shop_slug)

        barber = find_appointment_barber(
            db,
            appointment,
            shop_slug,
        )

        service = find_appointment_service(
            db,
            appointment,
            shop_slug,
        )

    appointment.status = status_value

    try:
        db.commit()
        db.refresh(appointment)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The appointment status could not be updated.",
        )

    if (
        status_value == "canceled"
        and old_status != "canceled"
        and shop is not None
        and barber is not None
        and service is not None
    ):
        send_cancellation_confirmation(
            appointment,
            shop,
            barber,
            service,
        )

    return appointment


@router.patch("/appointments/{appointment_id}/reschedule")
def reschedule_appointment_compatibility(
    appointment_id: str,
    new_start_datetime: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Legacy rescheduling endpoint.

    Lock the provider before checking for conflicts.
    The lock remains held until the appointment
    changes are committed.
    """

    shop_slug = require_user_shop_slug(current_user)

    appointment = find_shop_appointment(
        db,
        appointment_id,
        shop_slug,
    )

    require_appointment_modify_permission(
        db,
        current_user,
        appointment,
        shop_slug,
    )

    shop = find_shop(db, shop_slug)

    barber = find_appointment_barber(
        db,
        appointment,
        shop_slug,
    )

    service = find_appointment_service(
        db,
        appointment,
        shop_slug,
    )

    new_start = parse_datetime(new_start_datetime)

    new_end = calculate_appointment_end(
        new_start,
        service,
    )

    lock_booking_provider(
        db=db,
        shop_slug=shop_slug,
        barber_id=str(appointment.barber_id),
    )

    verify_no_reschedule_conflict(
        db,
        appointment,
        new_start,
        new_end,
        shop_slug,
    )

    return apply_reschedule(
        db,
        appointment,
        new_start,
        new_end,
        shop,
        barber,
        service,
    )


@router.patch("/appointments/{appointment_id}/notes")
def update_appointment_notes_compatibility(
    appointment_id: str,
    notes: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Legacy appointment-notes endpoint with
    authentication and staff permissions.
    """

    shop_slug = require_user_shop_slug(current_user)

    appointment = find_shop_appointment(
        db,
        appointment_id,
        shop_slug,
    )

    require_appointment_modify_permission(
        db,
        current_user,
        appointment,
        shop_slug,
    )

    appointment.notes = notes

    try:
        db.commit()
        db.refresh(appointment)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The appointment notes could not be updated.",
        )

    return appointment
