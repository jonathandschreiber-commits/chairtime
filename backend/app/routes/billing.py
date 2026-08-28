import os
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.routes.auth import get_current_user


router = APIRouter()


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
