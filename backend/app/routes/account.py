import stripe
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Literal

from app.database import get_db
from app.models import Shop, User
from app.routes.auth import get_current_user
from app.routes.billing import (
    get_ai_voice_price_id,
    get_scheduling_price_id,
    get_stripe_id,
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

        "ai_voice_enabled": bool(
            shop.ai_voice_enabled
        ),

        "subscription": {
            "plan_name": (
                "ChairTime Scheduling + AI Receptionist"
                if shop.ai_voice_enabled
                else "ChairTime Scheduling"
            ),

            "monthly_price": (
                198.00
                if shop.ai_voice_enabled
                else 49.00
            ),

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

    # Save the owner's preference before Stripe onboarding, just as the
    # shop onboarding endpoint does. Payment and reservation endpoints
    # independently verify Stripe readiness and the saved card.
    new_policy = payload.payment_policy

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


class AIUpgradeConfirm(BaseModel):
    confirm: Literal[True]
    expected_shop_slug: str
    expected_addon_amount: int
    expected_total_amount: int
    expected_currency: str


def ai_upgrade_details(shop):
    """Read and validate this owner's existing subscription and configured prices."""
    if not shop.stripe_subscription_id or not shop.stripe_customer_id:
        raise HTTPException(status_code=409, detail="Start your scheduling subscription before upgrading.")
    stripe.api_key = get_stripe_secret_key()
    subscription = stripe.Subscription.retrieve(shop.stripe_subscription_id)
    if get_stripe_id(get_object_value(subscription, "customer")) != shop.stripe_customer_id:
        raise HTTPException(status_code=409, detail="The subscription does not match this shop.")
    if get_object_value(subscription, "status") not in {"active", "trialing"}:
        raise HTTPException(status_code=409, detail="Resolve your subscription billing before upgrading.")
    if any(get_object_value(subscription, field) for field in (
        "cancel_at_period_end", "cancel_at", "schedule", "pending_update", "pause_collection"
    )):
        raise HTTPException(status_code=409, detail="Resolve the scheduled subscription change before upgrading.")
    core_id, ai_id = get_scheduling_price_id(), get_ai_voice_price_id()
    items_object = get_object_value(subscription, "items", {})
    items = get_object_value(items_object, "data", [])
    ids = [get_stripe_id(get_object_value(item, "price")) for item in items]
    if (get_object_value(items_object, "has_more", False) or ids.count(core_id) != 1
        or ids.count(ai_id) > 1 or any(price_id not in {core_id, ai_id} for price_id in ids)
        or any(get_object_value(item, "quantity") != 1 for item in items)):
        raise HTTPException(status_code=409, detail="This subscription needs a billing review before upgrading.")
    ai_price = stripe.Price.retrieve(ai_id)
    core_price = get_object_value(next(item for item in items
        if get_stripe_id(get_object_value(item, "price")) == core_id), "price")
    for price in (core_price, ai_price):
        recurring = get_object_value(price, "recurring", {})
        if (get_object_value(price, "unit_amount") is None
            or get_object_value(price, "billing_scheme") != "per_unit"
            or get_object_value(recurring, "interval") != "month"
            or get_object_value(recurring, "interval_count", 1) != 1
            or get_object_value(recurring, "usage_type") != "licensed"):
            raise HTTPException(status_code=409, detail="The upgrade requires monthly fixed-price plans.")
    if get_object_value(core_price, "currency") != get_object_value(ai_price, "currency"):
        raise HTTPException(status_code=409, detail="The plan currencies do not match.")
    if ai_id not in ids and not get_object_value(ai_price, "active"):
        raise HTTPException(status_code=409, detail="The AI Receptionist plan is not currently available.")
    amount = get_object_value(ai_price, "unit_amount")
    core_amount = get_object_value(core_price, "unit_amount")
    return subscription, {
        "success": True, "shop_slug": shop.slug,
        "already_upgraded": ai_id in ids,
        "addon_amount": amount, "total_amount": core_amount + amount,
        "currency": get_object_value(ai_price, "currency"),
        "trial_ends_at": iso_from_timestamp(get_object_value(subscription, "trial_end")),
        "billing_note": "Your existing billing date and trial stay the same. Any prorated add-on charge is included on your next invoice. Taxes and existing discounts may affect the invoice total.",
        "setup_url": f"/{shop.slug}/onboarding?setup=ai",
    }


@router.get("/ai-upgrade")
def get_ai_upgrade(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    shop = get_owner_shop(current_user, db)
    try:
        subscription, details = ai_upgrade_details(shop)
        sync_subscription_to_shop(subscription, db)
        return details
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except stripe.StripeError as exc:
        raise HTTPException(status_code=502, detail=stripe_error_message(exc, "Could not check the AI upgrade. Please try again."))


@router.post("/ai-upgrade")
def confirm_ai_upgrade(payload: AIUpgradeConfirm, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owner_shop = get_owner_shop(current_user, db)
    if payload.expected_shop_slug != owner_shop.slug:
        raise HTTPException(status_code=403, detail="Please sign in to the shop you chose to upgrade.")
    # Serialize confirmations for one shop; retries never append a second add-on.
    shop = db.query(Shop).filter(Shop.id == owner_shop.id).populate_existing().with_for_update().first()
    try:
        subscription, details = ai_upgrade_details(shop)
        if not details["already_upgraded"]:
            if (payload.expected_addon_amount != details["addon_amount"]
                or payload.expected_total_amount != details["total_amount"]
                or payload.expected_currency != details["currency"]):
                raise HTTPException(status_code=409, detail="The price changed. Review the upgrade price again before confirming.")
            # Reuse the same Stripe mutation on a network retry, even if its outcome
            # is initially unknown. Preserve all existing items and the trial.
            fingerprint = json.dumps({
                "subscription": shop.stripe_subscription_id,
                "items": [get_object_value(item, "id") for item in
                    get_object_value(get_object_value(subscription, "items", {}), "data", [])],
                "price": get_ai_voice_price_id(),
            }, sort_keys=True)
            key = "ai-upgrade-" + hashlib.sha256(fingerprint.encode()).hexdigest()
            stripe.Subscription.modify(
                shop.stripe_subscription_id,
                items=[{"price": get_ai_voice_price_id(), "quantity": 1}],
                proration_behavior="create_prorations",
                payment_behavior="error_if_incomplete",
                idempotency_key=key,
            )
            # Re-read Stripe instead of treating a redirect or click as an entitlement.
            subscription, details = ai_upgrade_details(shop)
        sync_subscription_to_shop(subscription, db)
        if not shop.ai_voice_enabled or not details["already_upgraded"]:
            raise HTTPException(status_code=409, detail="The upgrade is not yet verified. Check again before continuing.")
        return details
    except HTTPException:
        db.rollback()
        raise
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc))
    except stripe.StripeError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=stripe_error_message(exc, "Could not verify the upgrade. Check again; do not start another subscription."))
