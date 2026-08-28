import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
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
                f"{frontend_url}/signup/payment-success"
                "?session_id={CHECKOUT_SESSION_ID}"
            ).replace(
                "{CHECKOUT_SESSION_ID}",
                "{CHECKOUT_SESSION_ID}",
            ),
            cancel_url=f"{frontend_url}/signup/payment",
        )

    except Exception as exc:
        db.rollback()

        stripe_error = getattr(stripe, "StripeError", None)

        if stripe_error and isinstance(exc, stripe_error):
            message = (
                getattr(exc, "user_message", None)
                or "Stripe could not start the checkout process."
            )

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
