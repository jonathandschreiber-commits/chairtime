import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, Barber, Service, Shop
from app.routes.reminders import send_highlevel_sms


router = APIRouter()


CODE_LIFETIME_SECONDS = 10 * 60
VERIFIED_SESSION_SECONDS = 30 * 60
REQUEST_COOLDOWN_SECONDS = 60
MAX_VERIFY_ATTEMPTS = 5


@dataclass
class VerificationChallenge:
    shop_slug: str
    normalized_phone: str
    code_hash: str
    expires_at: float
    attempts_remaining: int


@dataclass
class VerifiedSession:
    shop_slug: str
    normalized_phone: str
    expires_at: float


verification_challenges: dict[
    str,
    VerificationChallenge,
] = {}

verified_sessions: dict[
    str,
    VerifiedSession,
] = {}

last_code_request: dict[
    str,
    float,
] = {}


class VerificationRequest(BaseModel):
    shop_slug: str
    customer_phone: str


class VerificationConfirm(BaseModel):
    shop_slug: str
    customer_phone: str
    code: str


class VerificationSessionRequest(BaseModel):
    shop_slug: str
    verification_token: str


def normalize_phone(
    phone: str | None,
) -> str:
    if not phone:
        return ""

    digits = "".join(
        character
        for character in str(phone)
        if character.isdigit()
    )

    if (
        len(digits) == 11
        and digits.startswith("1")
    ):
        digits = digits[1:]

    return digits


def challenge_key(
    shop_slug: str,
    normalized_phone: str,
) -> str:
    return (
        f"{shop_slug}:"
        f"{normalized_phone}"
    )


def verification_secret() -> str:
    secret = os.getenv(
        "CUSTOMER_VERIFICATION_SECRET"
    )

    if secret:
        return secret

    stripe_secret = os.getenv(
        "STRIPE_SECRET_KEY"
    )

    if stripe_secret:
        return stripe_secret

    raise RuntimeError(
        "CUSTOMER_VERIFICATION_SECRET or "
        "STRIPE_SECRET_KEY is required."
    )


def hash_code(
    shop_slug: str,
    normalized_phone: str,
    code: str,
) -> str:
    message = (
        f"{shop_slug}:"
        f"{normalized_phone}:"
        f"{code}"
    ).encode("utf-8")

    return hmac.new(
        verification_secret().encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def cleanup_expired_records():
    now = time.time()

    expired_challenges = [
        key
        for key, challenge
        in verification_challenges.items()
        if challenge.expires_at <= now
    ]

    for key in expired_challenges:
        verification_challenges.pop(
            key,
            None,
        )

    expired_sessions = [
        token
        for token, session
        in verified_sessions.items()
        if session.expires_at <= now
    ]

    for token in expired_sessions:
        verified_sessions.pop(
            token,
            None,
        )

    expired_request_keys = [
        key
        for key, requested_at
        in last_code_request.items()
        if requested_at
        <= now - CODE_LIFETIME_SECONDS
    ]

    for key in expired_request_keys:
        last_code_request.pop(
            key,
            None,
        )


def find_returning_appointments(
    db: Session,
    shop_slug: str,
    normalized_phone: str,
):
    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.shop_slug
            == shop_slug
        )
        .order_by(
            Appointment.created_at.desc()
        )
        .all()
    )

    return [
        appointment
        for appointment in appointments
        if normalize_phone(
            appointment.customer_phone
        )
        == normalized_phone
    ]


def get_shop(
    db: Session,
    shop_slug: str,
) -> Shop:
    shop = (
        db.query(Shop)
        .filter(
            Shop.slug == shop_slug
        )
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found.",
        )

    return shop


def get_verified_session(
    shop_slug: str,
    verification_token: str,
) -> VerifiedSession:
    cleanup_expired_records()

    token = str(
        verification_token or ""
    ).strip()

    session = verified_sessions.get(
        token
    )

    if (
        not session
        or session.shop_slug != shop_slug
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Customer verification has expired. "
                "Please verify your phone again."
            ),
        )

    return session


def get_stripe_value(
    obj,
    key,
    default=None,
):
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(
            key,
            default,
        )

    return getattr(
        obj,
        key,
        default,
    )


def get_stripe_id(
    value,
):
    if value is None:
        return None

    if isinstance(value, str):
        return value

    return get_stripe_value(
        value,
        "id",
    )


def find_verified_saved_card(
    shop: Shop,
    appointments: list[Appointment],
):
    if (
        shop.payment_policy
        != "card_required"
    ):
        return None

    if not shop.stripe_connect_account_id:
        return None

    stripe_secret = os.getenv(
        "STRIPE_SECRET_KEY"
    )

    if not stripe_secret:
        raise RuntimeError(
            "STRIPE_SECRET_KEY environment "
            "variable is missing."
        )

    stripe.api_key = stripe_secret

    for appointment in appointments:
        stripe_customer_id = str(
            appointment.stripe_customer_id
            or ""
        ).strip()

        payment_method_id = str(
            appointment.stripe_payment_method_id
            or ""
        ).strip()

        if (
            not stripe_customer_id
            or not payment_method_id
        ):
            continue

        try:
            payment_method = (
                stripe.PaymentMethod.retrieve(
                    payment_method_id,
                    stripe_account=(
                        shop.stripe_connect_account_id
                    ),
                )
            )

            payment_customer_id = (
                get_stripe_id(
                    get_stripe_value(
                        payment_method,
                        "customer",
                    )
                )
            )

            if (
                payment_customer_id
                != stripe_customer_id
            ):
                continue

            card = get_stripe_value(
                payment_method,
                "card",
            )

            if not card:
                continue

            return {
                "brand": get_stripe_value(
                    card,
                    "brand",
                ),
                "last4": get_stripe_value(
                    card,
                    "last4",
                ),
            }

        except stripe.StripeError:
            continue

    return None

def build_customer_profile(
    db: Session,
    shop: Shop,
    normalized_phone: str,
):
    appointments = (
        find_returning_appointments(
            db=db,
            shop_slug=shop.slug,
            normalized_phone=(
                normalized_phone
            ),
        )
    )

    if not appointments:
        return {
            "returning_customer": False,
            "customer": None,
            "saved_card": None,
        }

    latest = appointments[0]

    barber = None
    service = None

    if latest.barber_id:
        barber = (
            db.query(Barber)
            .filter(
                Barber.id
                == latest.barber_id
            )
            .first()
        )

    if latest.service_id:
        service = (
            db.query(Service)
            .filter(
                Service.id
                == latest.service_id
            )
            .first()
        )

    saved_card = (
        find_verified_saved_card(
            shop=shop,
            appointments=appointments,
        )
    )

    return {
        "returning_customer": True,
        "customer": {
            "name": (
                latest.customer_name
                or ""
            ),
            "phone": (
                latest.customer_phone
                or ""
            ),
            "last_barber_id": (
                latest.barber_id
            ),
            "last_barber_name": (
                barber.name
                if barber
                else None
            ),
            "last_service_id": (
                latest.service_id
            ),
            "last_service_name": (
                service.name
                if service
                else None
            ),
        },
        "saved_card": saved_card,
    }


@router.post("/request")
def request_verification_code(
    payload: VerificationRequest,
    db: Session = Depends(get_db),
):
    cleanup_expired_records()

    shop_slug = str(
        payload.shop_slug or ""
    ).strip().lower()

    normalized_phone = normalize_phone(
        payload.customer_phone
    )

    if len(normalized_phone) != 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Please enter a valid "
                "10-digit phone number."
            ),
        )

    shop = get_shop(
        db=db,
        shop_slug=shop_slug,
    )

    appointments = (
        find_returning_appointments(
            db=db,
            shop_slug=shop.slug,
            normalized_phone=(
                normalized_phone
            ),
        )
    )

    #
    # Do not reveal whether a phone number
    # belongs to an existing customer.
    #
    if not appointments:
        return {
            "success": True,
            "verification_required": False,
            "returning_customer": False,
        }

    key = challenge_key(
        shop.slug,
        normalized_phone,
    )

    now = time.time()

    previous_request = (
        last_code_request.get(key)
    )

    if (
        previous_request
        and now - previous_request
        < REQUEST_COOLDOWN_SECONDS
    ):
        seconds_remaining = int(
            REQUEST_COOLDOWN_SECONDS
            - (now - previous_request)
        )

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Please wait "
                f"{max(seconds_remaining, 1)} "
                "seconds before requesting "
                "another code."
            ),
        )

    code = (
        f"{secrets.randbelow(1000000):06d}"
    )

    verification_challenges[key] = (
        VerificationChallenge(
            shop_slug=shop.slug,
            normalized_phone=(
                normalized_phone
            ),
            code_hash=hash_code(
                shop.slug,
                normalized_phone,
                code,
            ),
            expires_at=(
                now
                + CODE_LIFETIME_SECONDS
            ),
            attempts_remaining=(
                MAX_VERIFY_ATTEMPTS
            ),
        )
    )

    last_code_request[key] = now

    message = (
        f"Your {shop.name} verification "
        f"code is {code}. "
        "It expires in 10 minutes. "
        "Do not share this code."
    )

    sms_result = send_highlevel_sms(
        normalized_phone,
        message,
    )

    if not sms_result.get("success"):
        verification_challenges.pop(
            key,
            None,
        )

        last_code_request.pop(
            key,
            None,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "We couldn't send the "
                "verification text. "
                "Please try again."
            ),
        )

    return {
        "success": True,
        "verification_required": True,
        "returning_customer": True,
        "expires_in_seconds": (
            CODE_LIFETIME_SECONDS
        ),
    }


@router.post("/confirm")
def confirm_verification_code(
    payload: VerificationConfirm,
    db: Session = Depends(get_db),
):
    cleanup_expired_records()

    shop_slug = str(
        payload.shop_slug or ""
    ).strip().lower()

    normalized_phone = normalize_phone(
        payload.customer_phone
    )

    code = str(
        payload.code or ""
    ).strip()

    if (
        len(normalized_phone) != 10
        or len(code) != 6
        or not code.isdigit()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code.",
        )

    shop = get_shop(
        db=db,
        shop_slug=shop_slug,
    )

    key = challenge_key(
        shop.slug,
        normalized_phone,
    )

    challenge = (
        verification_challenges.get(key)
    )

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "The verification code has "
                "expired. Please request "
                "a new code."
            ),
        )

    expected_hash = hash_code(
        shop.slug,
        normalized_phone,
        code,
    )

    if not hmac.compare_digest(
        challenge.code_hash,
        expected_hash,
    ):
        challenge.attempts_remaining -= 1

        if (
            challenge.attempts_remaining
            <= 0
        ):
            verification_challenges.pop(
                key,
                None,
            )

            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail=(
                    "Too many incorrect "
                    "attempts. Please request "
                    "a new code."
                ),
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "That code is incorrect. "
                "Please try again."
            ),
        )

    verification_challenges.pop(
        key,
        None,
    )

    token = secrets.token_urlsafe(32)

    verified_sessions[token] = (
        VerifiedSession(
            shop_slug=shop.slug,
            normalized_phone=(
                normalized_phone
            ),
            expires_at=(
                time.time()
                + VERIFIED_SESSION_SECONDS
            ),
        )
    )

    profile = build_customer_profile(
        db=db,
        shop=shop,
        normalized_phone=(
            normalized_phone
        ),
    )

    return {
        "success": True,
        "verified": True,
        "verification_token": token,
        "expires_in_seconds": (
            VERIFIED_SESSION_SECONDS
        ),
        **profile,
    }


@router.post("/session")
def get_verified_customer_session(
    payload: VerificationSessionRequest,
    db: Session = Depends(get_db),
):
    shop_slug = str(
        payload.shop_slug or ""
    ).strip().lower()

    shop = get_shop(
        db=db,
        shop_slug=shop_slug,
    )

    session = get_verified_session(
        shop_slug=shop.slug,
        verification_token=(
            payload.verification_token
        ),
    )

    profile = build_customer_profile(
        db=db,
        shop=shop,
        normalized_phone=(
            session.normalized_phone
        ),
    )

    return {
        "success": True,
        "verified": True,
        "expires_in_seconds": max(
            0,
            int(
                session.expires_at
                - time.time()
            ),
        ),
        **profile,
    }
