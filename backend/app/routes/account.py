import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Literal

from app.database import get_db
from app.models import Shop, User
from app.routes.auth import get_current_user
from app.routes.billing import (
    get_frontend_url,
    get_object_value,
    get_stripe_secret_key,
    sync_subscription_to_shop,
    timestamp_to_datetime,
)


router = APIRouter()


class PaymentPolicyUpdate(BaseModel):
    payment_policy: Literal[
        "none",
        "accept_cards",
        "card_required",
    ]


def get_owner_shop(
    current_user: User,
    db: Session,
) -> Shop:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the business owner can manage the account.",
        )

    if not current_user.shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account does not have a business assigned.",
        )

    shop = (
        db.query(Shop)
        .filter(
            Shop.id == current_user.shop_id
        )
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found.",
        )

    return shop


def stripe_error_message(
    exc,
    fallback: str,
) -> str:
    message = getattr(
        exc,
        "user_message",
        None,
    )

    return message or fallback


def iso_from_timestamp(
    timestamp,
):
    if not timestamp:
        return None

    value = timestamp_to_datetime(
        timestamp
    )

    if not value:
        return None

    return value.isoformat()


@router.get("/summary")
def get_account_summary(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    shop = get_owner_shop(
        current_user=current_user,
        db=db,
    )

    subscription_status = (
        shop.subscription_status
    )

    trial_ends_at = (
        shop.trial_ends_at.isoformat()
        if shop.trial_ends_at
        else None
    )

    current_period_ends_at = None
    cancel_at_period_end = False

    connected_account_exists = bool(
        shop.stripe_connect_account_id
    )

    details_submitted = False
    charges_enabled = False
    payouts_enabled = False

    try:
        stripe.api_key = (
            get_stripe_secret_key()
        )

        if shop.stripe_subscription_id:
            subscription = (
                stripe.Subscription.retrieve(
                    shop.stripe_subscription_id
                )
            )

            subscription_status = (
                get_object_value(
                    subscription,
                    "status",
                    subscription_status,
                )
            )

            cancel_at_period_end = bool(
                get_object_value(
                    subscription,
                    "cancel_at_period_end",
                    False,
                )
            )

            current_period_end = (
                get_object_value(
                    subscription,
                    "current_period_end",
                )
            )

            stripe_trial_end = (
                get_object_value(
                    subscription,
                    "trial_end",
                )
            )

            current_period_ends_at = (
                iso_from_timestamp(
                    current_period_end
                )
            )

            if stripe_trial_end:
                trial_ends_at = (
                    iso_from_timestamp(
                        stripe_trial_end
                    )
                )

            sync_subscription_to_shop(
                subscription,
                db,
            )

        if shop.stripe_connect_account_id:
            account = (
                stripe.Account.retrieve(
                    shop.stripe_connect_account_id
                )
            )

            details_submitted = bool(
                get_object_value(
                    account,
                    "details_submitted",
                    False,
                )
            )

            charges_enabled = bool(
                get_object_value(
                    account,
                    "charges_enabled",
                    False,
                )
            )

            payouts_enabled = bool(
                get_object_value(
                    account,
                    "payouts_enabled",
                    False,
                )
            )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=stripe_error_message(
                exc,
                "Unable to load account information.",
            ),
        )

    return {
        "success": True,

        "business": {
            "name": shop.name,
            "slug": shop.slug,
        },

        "subscription": {
            "plan_name":
                "ChairTime Scheduling",

            "monthly_price": 49.00,

            "status":
                subscription_status,

            "trial_ends_at":
                trial_ends_at,

            "current_period_ends_at":
                current_period_ends_at,

            "cancel_at_period_end":
                cancel_at_period_end,

            "has_subscription": bool(
                shop.stripe_subscription_id
            ),
        },

        "customer_payments": {
            "payment_policy":
                shop.payment_policy
                or "none",

            "connected_account_exists":
                connected_account_exists,

            "details_submitted":
                details_submitted,

            "charges_enabled":
                charges_enabled,

            "payouts_enabled":
                payouts_enabled,
        },
    }


@router.post("/billing-portal")
def create_billing_portal(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    shop = get_owner_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This business does not "
                "have a ChairTime billing "
                "account yet."
            ),
        )

    try:
        stripe.api_key = (
            get_stripe_secret_key()
        )

        frontend_url = (
            get_frontend_url()
        )

        portal_session = (
            stripe.billing_portal.Session.create(
                customer=(
                    shop.stripe_customer_id
                ),
                return_url=(
                    frontend_url
                    + f"/{shop.slug}"
                    + "/admin/account"
                ),
            )
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=stripe_error_message(
                exc,
                "Unable to open subscription billing.",
            ),
        )

    return {
        "success": True,
        "portal_url":
            portal_session.url,
    }


@router.post("/cancel-subscription")
def cancel_subscription(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    shop = get_owner_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No ChairTime subscription "
                "was found."
            ),
        )

    try:
        stripe.api_key = (
            get_stripe_secret_key()
        )

        subscription = (
            stripe.Subscription.modify(
                shop.stripe_subscription_id,
                cancel_at_period_end=True,
            )
        )

        sync_subscription_to_shop(
            subscription,
            db,
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=stripe_error_message(
                exc,
                "Unable to cancel the subscription.",
            ),
        )

    return {
        "success": True,

        "cancel_at_period_end": True,

        "message": (
            "Your subscription will remain "
            "active until the end of the "
            "current billing period."
        ),
    }


@router.post("/reactivate-subscription")
def reactivate_subscription(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    shop = get_owner_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No ChairTime subscription "
                "was found."
            ),
        )

    try:
        stripe.api_key = (
            get_stripe_secret_key()
        )

        subscription = (
            stripe.Subscription.modify(
                shop.stripe_subscription_id,
                cancel_at_period_end=False,
            )
        )

        sync_subscription_to_shop(
            subscription,
            db,
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=stripe_error_message(
                exc,
                "Unable to reactivate the subscription.",
            ),
        )

    return {
        "success": True,

        "cancel_at_period_end": False,

        "message": (
            "Your ChairTime subscription "
            "will continue normally."
        ),
    }

@router.get("/invoices")
def get_invoices(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    shop = get_owner_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.stripe_customer_id:
        return {
            "success": True,
            "invoices": [],
        }

    try:
        stripe.api_key = (
            get_stripe_secret_key()
        )

        invoice_list = (
            stripe.Invoice.list(
                customer=(
                    shop.stripe_customer_id
                ),
                limit=24,
            )
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=stripe_error_message(
                exc,
                "Unable to load payment history.",
            ),
        )

    invoices = []

    for invoice in get_object_value(
        invoice_list,
        "data",
        [],
    ):
        created = get_object_value(
            invoice,
            "created",
        )

        invoices.append(
            {
                "id":
                    get_object_value(
                        invoice,
                        "id",
                    ),

                "number":
                    get_object_value(
                        invoice,
                        "number",
                    ),

                "status":
                    get_object_value(
                        invoice,
                        "status",
                    ),

                "paid":
                    bool(
                        get_object_value(
                            invoice,
                            "paid",
                            False,
                        )
                    ),

                "amount_due":
                    (
                        get_object_value(
                            invoice,
                            "amount_due",
                            0,
                        )
                        or 0
                    ),

                "amount_paid":
                    (
                        get_object_value(
                            invoice,
                            "amount_paid",
                            0,
                        )
                        or 0
                    ),

                "currency":
                    get_object_value(
                        invoice,
                        "currency",
                        "usd",
                    ),

                "created_at":
                    (
                        iso_from_timestamp(
                            created
                        )
                        if created
                        else None
                    ),

                "hosted_invoice_url":
                    get_object_value(
                        invoice,
                        "hosted_invoice_url",
                    ),

                "invoice_pdf":
                    get_object_value(
                        invoice,
                        "invoice_pdf",
                    ),
            }
        )

    return {
        "success": True,
        "invoices": invoices,
    }


@router.patch("/payment-policy")
def update_payment_policy(
    payload: PaymentPolicyUpdate,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(get_db),
):
    shop = get_owner_shop(
        current_user=current_user,
        db=db,
    )

    new_policy = (
        payload.payment_policy
    )

    if new_policy == "none":
        shop.payment_policy = "none"

        try:
            db.commit()
            db.refresh(shop)

        except Exception:
            db.rollback()

            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=(
                    "Unable to save "
                    "payment settings."
                ),
            )

        return {
            "success": True,
            "payment_policy":
                shop.payment_policy,
        }

    if not shop.stripe_connect_account_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Connect Stripe before "
                "enabling customer card "
                "payments."
            ),
        )

    try:
        stripe.api_key = (
            get_stripe_secret_key()
        )

        account = (
            stripe.Account.retrieve(
                shop.stripe_connect_account_id
            )
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
                    "Finish Stripe setup "
                    "before enabling customer "
                    "card payments."
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=stripe_error_message(
                exc,
                "Unable to verify Stripe payment setup.",
            ),
        )

    shop.payment_policy = new_policy

    try:
        db.commit()
        db.refresh(shop)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Unable to save "
                "payment settings."
            ),
        )

    return {
        "success": True,
        "payment_policy":
            shop.payment_policy,
    }


@router.post("/stripe-dashboard")
def open_stripe_dashboard(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    shop = get_owner_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.stripe_connect_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This business has not "
                "connected a Stripe payment "
                "account yet."
            ),
        )

    try:
        stripe.api_key = (
            get_stripe_secret_key()
        )

        login_link = (
            stripe.Account.create_login_link(
                shop.stripe_connect_account_id
            )
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=stripe_error_message(
                exc,
                "Unable to open the Stripe dashboard.",
            ),
        )

    return {
        "success": True,
        "dashboard_url":
            login_link.url,
    }
