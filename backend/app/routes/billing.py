import os
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, Shop, User
from app.routes.auth import get_current_user
from app.routes.customer_verification import (
    validate_verified_customer_session,
)


router = APIRouter()


class BookingSetupIntentCreate(BaseModel):
    shop_slug: str
    customer_name: str | None = None
    customer_phone: str | None = None
    use_saved_card: bool = False
    verification_token: str | None = None


def get_stripe_secret_key() -> str:
    secret_key = os.getenv("STRIPE_SECRET_KEY")

    if not secret_key:
        raise RuntimeError(
            "STRIPE_SECRET_KEY environment variable is missing."
        )

    return secret_key


def get_stripe_webhook_secret() -> str:
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    if not webhook_secret:
        raise RuntimeError(
            "STRIPE_WEBHOOK_SECRET environment variable is missing."
        )

    return webhook_secret


def get_scheduling_price_id() -> str:
    price_id = os.getenv("STRIPE_SCHEDULING_PRICE_ID")

    if not price_id:
        raise RuntimeError(
            "STRIPE_SCHEDULING_PRICE_ID environment variable is missing."
        )

    return price_id


def get_frontend_url() -> str:
    frontend_url = os.getenv("CHAIRTIME_FRONTEND_URL")

    if not frontend_url:
        raise RuntimeError(
            "CHAIRTIME_FRONTEND_URL environment variable is missing."
        )

    return frontend_url.rstrip("/")


def get_current_shop(
    current_user: User,
    db: Session,
) -> Shop:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the business owner can manage billing.",
        )

    if not current_user.shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account does not have a business assigned.",
        )

    shop = (
        db.query(Shop)
        .filter(Shop.id == current_user.shop_id)
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found.",
        )

    return shop


def get_object_value(obj, key, default=None):
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


def get_stripe_id(value):
    if value is None:
        return None

    if isinstance(value, str):
        return value

    return get_object_value(value, "id")


def timestamp_to_datetime(timestamp):
    if not timestamp:
        return None

    return (
        datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )
        .replace(tzinfo=None)
    )


def normalize_customer_phone(phone: str | None) -> str:
    if not phone:
        return ""

    return "".join(
        character
        for character in str(phone)
        if character.isdigit()
    )


def find_existing_stripe_customer_id(
    db: Session,
    shop_slug: str,
    customer_phone: str,
) -> str | None:
    normalized_phone = normalize_customer_phone(
        customer_phone
    )

    if not normalized_phone:
        return None

    prior_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.shop_slug == shop_slug,
            Appointment.stripe_customer_id.isnot(None),
        )
        .order_by(
            Appointment.created_at.desc()
        )
        .all()
    )

    for appointment in prior_appointments:
        appointment_phone = normalize_customer_phone(
            appointment.customer_phone
        )

        if (
            appointment_phone == normalized_phone
            and appointment.stripe_customer_id
        ):
            return str(
                appointment.stripe_customer_id
            ).strip()

    return None


def find_existing_saved_card(
    db: Session,
    shop: Shop,
    customer_phone: str,
):
    normalized_phone = normalize_customer_phone(
        customer_phone
    )

    if not normalized_phone:
        return None

    prior_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.shop_slug == shop.slug,
            Appointment.stripe_customer_id.isnot(None),
            Appointment.stripe_payment_method_id.isnot(None),
        )
        .order_by(
            Appointment.created_at.desc()
        )
        .all()
    )

    for appointment in prior_appointments:
        if (
            normalize_customer_phone(
                appointment.customer_phone
            )
            != normalized_phone
        ):
            continue

        stripe_customer_id = str(
            appointment.stripe_customer_id or ""
        ).strip()

        payment_method_id = str(
            appointment.stripe_payment_method_id or ""
        ).strip()

        if (
            not stripe_customer_id
            or not payment_method_id
        ):
            continue

        try:
            stripe.api_key = get_stripe_secret_key()

            customer = stripe.Customer.retrieve(
                stripe_customer_id,
                stripe_account=(
                    shop.stripe_connect_account_id
                ),
            )

            if bool(
                get_object_value(
                    customer,
                    "deleted",
                    False,
                )
            ):
                continue

            payment_method = (
                stripe.PaymentMethod.retrieve(
                    payment_method_id,
                    stripe_account=(
                        shop.stripe_connect_account_id
                    ),
                )
            )

            payment_method_customer_id = (
                get_stripe_id(
                    get_object_value(
                        payment_method,
                        "customer",
                    )
                )
            )

            if (
                payment_method_customer_id
                != stripe_customer_id
            ):
                continue

            card = get_object_value(
                payment_method,
                "card",
            )

            last4 = get_object_value(
                card,
                "last4",
            )

            brand = get_object_value(
                card,
                "brand",
            )

            return {
                "stripe_customer_id":
                    stripe_customer_id,
                "stripe_payment_method_id":
                    payment_method_id,
                "last4": last4,
                "brand": brand,
            }

        except stripe.StripeError:
            continue

    return None


def get_or_create_booking_customer(
    db: Session,
    shop: Shop,
    customer_name: str,
    customer_phone: str,
) -> str:
    stripe.api_key = get_stripe_secret_key()

    if not shop.stripe_connect_account_id:
        raise RuntimeError(
            "This business does not have a Stripe connected account."
        )

    clean_name = str(
        customer_name or ""
    ).strip()

    clean_phone = str(
        customer_phone or ""
    ).strip()

    normalized_phone = normalize_customer_phone(
        clean_phone
    )

    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer name is required.",
        )

    if not normalized_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer phone number is required.",
        )

    existing_customer_id = (
        find_existing_stripe_customer_id(
            db=db,
            shop_slug=shop.slug,
            customer_phone=clean_phone,
        )
    )

    if existing_customer_id:
        try:
            customer = stripe.Customer.retrieve(
                existing_customer_id,
                stripe_account=(
                    shop.stripe_connect_account_id
                ),
            )

            if not bool(
                get_object_value(
                    customer,
                    "deleted",
                    False,
                )
            ):
                return existing_customer_id

        except stripe.StripeError:
            pass

    customer = stripe.Customer.create(
        name=clean_name,
        phone=clean_phone,
        metadata={
            "shop_id": str(shop.id),
            "shop_slug": shop.slug,
            "chairtime_customer_phone": (
                normalized_phone
            ),
        },
        stripe_account=(
            shop.stripe_connect_account_id
        ),
    )

    return customer.id


def find_shop_for_subscription(
    subscription,
    db: Session,
):
    metadata = get_object_value(
        subscription,
        "metadata",
        {},
    )

    shop_id = get_object_value(
        metadata,
        "shop_id",
    )

    if shop_id:
        shop = (
            db.query(Shop)
            .filter(Shop.id == shop_id)
            .first()
        )

        if shop:
            return shop

    customer_id = get_stripe_id(
        get_object_value(
            subscription,
            "customer",
        )
    )

    if customer_id:
        shop = (
            db.query(Shop)
            .filter(
                Shop.stripe_customer_id == customer_id
            )
            .first()
        )

        if shop:
            return shop

    return None


def sync_subscription_to_shop(
    subscription,
    db: Session,
):
    shop = find_shop_for_subscription(
        subscription,
        db,
    )

    if not shop:
        return None

    subscription_id = get_stripe_id(
        get_object_value(
            subscription,
            "id",
        )
    )

    customer_id = get_stripe_id(
        get_object_value(
            subscription,
            "customer",
        )
    )

    subscription_status = get_object_value(
        subscription,
        "status",
    )

    trial_end = get_object_value(
        subscription,
        "trial_end",
    )

    if customer_id:
        shop.stripe_customer_id = customer_id

    if subscription_id:
        shop.stripe_subscription_id = subscription_id

    shop.subscription_status = subscription_status

    shop.trial_ends_at = timestamp_to_datetime(
        trial_end
    )

    db.commit()
    db.refresh(shop)

    return shop


def create_connected_account(
    shop: Shop,
    current_user: User,
    db: Session,
):
    stripe.api_key = get_stripe_secret_key()

    if shop.stripe_connect_account_id:
        return stripe.Account.retrieve(
            shop.stripe_connect_account_id
        )

    account = stripe.Account.create(
        type="express",
        country="US",
        email=current_user.email,
        business_profile={
            "name": shop.name,
            "product_description": (
                "Appointment-based services offered "
                "by this business."
            ),
        },
        capabilities={
            "card_payments": {
                "requested": True,
            },
            "transfers": {
                "requested": True,
            },
        },
        metadata={
            "shop_id": str(shop.id),
            "shop_slug": shop.slug,
            "owner_user_id": str(current_user.id),
        },
    )

    shop.stripe_connect_account_id = account.id

    try:
        db.commit()
        db.refresh(shop)

    except Exception:
        db.rollback()
        raise

    return account


def create_connect_onboarding_link(
    shop: Shop,
):
    stripe.api_key = get_stripe_secret_key()

    if not shop.stripe_connect_account_id:
        raise RuntimeError(
            "This business does not have a Stripe connected account."
        )

    frontend_url = get_frontend_url()

    return stripe.AccountLink.create(
        account=shop.stripe_connect_account_id,
        refresh_url=(
            frontend_url
            + f"/{shop.slug}/onboarding"
            + "?stripe_connect=refresh"
        ),
        return_url=(
            frontend_url
            + f"/{shop.slug}/onboarding"
            + "?stripe_connect=return"
        ),
        type="account_onboarding",
    )


@router.post("/create-checkout-session")
def create_checkout_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        stripe.api_key = get_stripe_secret_key()

        scheduling_price_id = get_scheduling_price_id()
        frontend_url = get_frontend_url()

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    try:
        if not shop.stripe_customer_id:
            customer = stripe.Customer.create(
                name=shop.name,
                email=current_user.email,
                phone=shop.phone or None,
                metadata={
                    "shop_id": str(shop.id),
                    "shop_slug": shop.slug,
                    "owner_user_id": str(current_user.id),
                },
            )

            shop.stripe_customer_id = customer.id

            db.commit()
            db.refresh(shop)

        checkout_session = stripe.checkout.Session.create(
            mode="subscription",
            customer=shop.stripe_customer_id,
            payment_method_collection="always",
            line_items=[
                {
                    "price": scheduling_price_id,
                    "quantity": 1,
                }
            ],
            subscription_data={
                "trial_period_days": 30,
                "metadata": {
                    "shop_id": str(shop.id),
                    "shop_slug": shop.slug,
                    "owner_user_id": str(current_user.id),
                },
            },
            client_reference_id=str(shop.id),
            metadata={
                "shop_id": str(shop.id),
                "shop_slug": shop.slug,
                "owner_user_id": str(current_user.id),
            },
            success_url=(
                frontend_url
                + "/signup/payment-success"
                + "?session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=(
                frontend_url
                + "/signup/payment"
            ),
        )

    except Exception as exc:
        db.rollback()

        message = getattr(
            exc,
            "user_message",
            None,
        )

        if message:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=message,
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to start checkout.",
        )

    return {
        "success": True,
        "checkout_url": checkout_session.url,
        "checkout_session_id": checkout_session.id,
    }

@router.post("/connect/start")
def start_connect_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if shop.payment_policy == "none":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Credit card payments are not enabled "
                "for this business."
            ),
        )

    try:
        create_connected_account(
            shop=shop,
            current_user=current_user,
            db=db,
        )

        account_link = create_connect_onboarding_link(
            shop=shop,
        )

    except RuntimeError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    except stripe.StripeError as exc:
        db.rollback()

        message = getattr(
            exc,
            "user_message",
            None,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                message
                or "Unable to start Stripe payment setup."
            ),
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to start Stripe payment setup.",
        )

    return {
        "success": True,
        "stripe_connect_account_id": (
            shop.stripe_connect_account_id
        ),
        "onboarding_url": account_link.url,
    }


@router.get("/connect/status")
def get_connect_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.stripe_connect_account_id:
        return {
            "connected_account_exists": False,
            "details_submitted": False,
            "charges_enabled": False,
            "payouts_enabled": False,
            "stripe_connect_account_id": None,
        }

    try:
        stripe.api_key = get_stripe_secret_key()

        account = stripe.Account.retrieve(
            shop.stripe_connect_account_id
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    except stripe.StripeError as exc:
        message = getattr(
            exc,
            "user_message",
            None,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                message
                or "Unable to check Stripe payment setup."
            ),
        )

    return {
        "connected_account_exists": True,
        "details_submitted": bool(
            get_object_value(
                account,
                "details_submitted",
                False,
            )
        ),
        "charges_enabled": bool(
            get_object_value(
                account,
                "charges_enabled",
                False,
            )
        ),
        "payouts_enabled": bool(
            get_object_value(
                account,
                "payouts_enabled",
                False,
            )
        ),
        "stripe_connect_account_id": account.id,
    }


@router.post("/connect/dashboard")
def create_connect_dashboard_link(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.stripe_connect_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This business has not connected "
                "a Stripe payment account yet."
            ),
        )

    try:
        stripe.api_key = get_stripe_secret_key()

        login_link = stripe.Account.create_login_link(
            shop.stripe_connect_account_id
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    except stripe.StripeError as exc:
        message = getattr(
            exc,
            "user_message",
            None,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                message
                or "Unable to open the Stripe dashboard."
            ),
        )

    return {
        "success": True,
        "dashboard_url": login_link.url,
    }


@router.get("/booking/saved-card")
def get_booking_saved_card(
    shop_slug: str,
    customer_phone: str,
    verification_token: str,
    db: Session = Depends(get_db),
):
    clean_slug = str(
        shop_slug or ""
    ).strip().lower()

    clean_phone = str(
        customer_phone or ""
    ).strip()

    shop = (
        db.query(Shop)
        .filter(Shop.slug == clean_slug)
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found.",
        )

    if (
        shop.payment_policy != "card_required"
        or not shop.stripe_connect_account_id
    ):
        return {
            "has_saved_card": False,
        }

    validate_verified_customer_session(
        shop_slug=shop.slug,
        customer_phone=clean_phone,
        verification_token=verification_token,
    )

    try:
        saved_card = find_existing_saved_card(
            db=db,
            shop=shop,
            customer_phone=clean_phone,
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    if not saved_card:
        return {
            "has_saved_card": False,
        }

    return {
        "has_saved_card": True,
        "brand": saved_card.get("brand"),
        "last4": saved_card.get("last4"),
    }


@router.post("/booking/setup-intent")
def create_booking_setup_intent(
    payload: BookingSetupIntentCreate,
    db: Session = Depends(get_db),
):
    clean_slug = payload.shop_slug.strip().lower()

    shop = (
        db.query(Shop)
        .filter(Shop.slug == clean_slug)
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found.",
        )

    if shop.payment_policy != "card_required":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This business does not require a card "
                "to reserve an appointment."
            ),
        )

    if not shop.stripe_connect_account_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This business has not finished "
                "setting up card reservations."
            ),
        )

    try:
        stripe.api_key = get_stripe_secret_key()

        account = stripe.Account.retrieve(
            shop.stripe_connect_account_id
        )

        charges_enabled = bool(
            get_object_value(
                account,
                "charges_enabled",
                False,
            )
        )

        if not charges_enabled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This business is not yet ready "
                    "to accept customer cards."
                ),
            )

        clean_customer_name = str(
            payload.customer_name or ""
        ).strip()

        clean_customer_phone = str(
            payload.customer_phone or ""
        ).strip()

        stripe_customer_id = None
        saved_card = None

        if payload.use_saved_card:
            if not clean_customer_phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Customer phone number is required "
                        "to use a saved card."
                    ),
                )

            verification_token = str(
                payload.verification_token or ""
            ).strip()

            if not verification_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=(
                        "Phone verification is required "
                        "to use the saved card."
                    ),
                )

            validate_verified_customer_session(
                shop_slug=shop.slug,
                customer_phone=clean_customer_phone,
                verification_token=verification_token,
            )

            saved_card = find_existing_saved_card(
                db=db,
                shop=shop,
                customer_phone=clean_customer_phone,
            )

            if not saved_card:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "No saved card is available "
                        "for this customer."
                    ),
                )

            stripe_customer_id = saved_card[
                "stripe_customer_id"
            ]

        if (
            not stripe_customer_id
            and clean_customer_name
            and clean_customer_phone
        ):
            stripe_customer_id = (
                get_or_create_booking_customer(
                    db=db,
                    shop=shop,
                    customer_name=clean_customer_name,
                    customer_phone=clean_customer_phone,
                )
            )

        setup_intent_parameters = {
            "payment_method_types": ["card"],
            "usage": "off_session",
            "metadata": {
                "shop_id": str(shop.id),
                "shop_slug": shop.slug,
                "purpose": "appointment_reservation",
            },
            "stripe_account": (
                shop.stripe_connect_account_id
            ),
        }

        if stripe_customer_id:
            setup_intent_parameters[
                "customer"
            ] = stripe_customer_id

            setup_intent_parameters[
                "metadata"
            ][
                "stripe_customer_id"
            ] = stripe_customer_id

        if saved_card:
            setup_intent_parameters[
                "payment_method"
            ] = saved_card[
                "stripe_payment_method_id"
            ]

            setup_intent_parameters[
                "confirm"
            ] = True

        setup_intent = stripe.SetupIntent.create(
            **setup_intent_parameters
        )

        if (
            saved_card
            and setup_intent.status
            != "succeeded"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The saved card could not be "
                    "verified automatically. Please "
                    "enter the card again."
                ),
            )

    except HTTPException:
        raise

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    except stripe.StripeError as exc:
        message = getattr(
            exc,
            "user_message",
            None,
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                message
                or "Unable to prepare secure card entry."
            ),
        )

    except Exception as exc:
        print(
            "Booking SetupIntent creation failed:",
            exc,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to prepare secure card entry.",
        )

    return {
        "success": True,
        "client_secret": setup_intent.client_secret,
        "setup_intent_id": setup_intent.id,
        "stripe_customer_id": stripe_customer_id,
        "used_saved_card": bool(saved_card),
        "stripe_connect_account_id": (
            shop.stripe_connect_account_id
        ),
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        stripe.api_key = get_stripe_secret_key()
        webhook_secret = get_stripe_webhook_secret()

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    payload = await request.body()

    stripe_signature = request.headers.get(
        "stripe-signature"
    )

    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature.",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=webhook_secret,
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook.",
        )

    event_type = get_object_value(
        event,
        "type",
    )

    event_data = get_object_value(
        event,
        "data",
        {},
    )

    stripe_object = get_object_value(
        event_data,
        "object",
    )

    try:
        if event_type == "checkout.session.completed":
            subscription_id = get_stripe_id(
                get_object_value(
                    stripe_object,
                    "subscription",
                )
            )

            if subscription_id:
                subscription = stripe.Subscription.retrieve(
                    subscription_id
                )

                sync_subscription_to_shop(
                    subscription,
                    db,
                )

        elif event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            sync_subscription_to_shop(
                stripe_object,
                db,
            )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process Stripe webhook.",
        )

    return {
        "received": True,
        "event_type": event_type,
    }
