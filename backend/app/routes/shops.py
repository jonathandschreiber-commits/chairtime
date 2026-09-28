import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.routes.auth import get_current_user
from app.schemas import (
    ShopCreate,
    ShopPaymentPolicyUpdate,
    ShopStaffAppointmentPermissionUpdate,
)


router = APIRouter()


def normalize_slug(value: str) -> str:
    slug = str(value or "").strip().lower()
    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        slug,
    )
    slug = slug.strip("-")

    return slug


def require_public_shop_slug(
    value: str,
) -> str:
    clean_slug = normalize_slug(
        value
    )

    if not clean_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business is required.",
        )

    return clean_slug


def require_shop_access(
    shop_slug: str,
    current_user: User,
) -> str:
    clean_slug = normalize_slug(
        shop_slug
    )

    current_user_shop_slug = normalize_slug(
        str(
            current_user.shop_slug or ""
        )
    )

    if not current_user_shop_slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your account is not assigned "
                "to a business."
            ),
        )

    if current_user_shop_slug != clean_slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not have access "
                "to this business."
            ),
        )

    role = str(
        current_user.role or ""
    ).strip().lower()

    if role not in {
        "owner",
        "staff",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not have access "
                "to this business."
            ),
        )

    return clean_slug


def require_owner_for_shop(
    shop_slug: str,
    current_user: User,
) -> str:
    clean_slug = require_shop_access(
        shop_slug,
        current_user,
    )

    role = str(
        current_user.role or ""
    ).strip().lower()

    if role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access is required.",
        )

    return clean_slug


def public_shop_response(
    shop: Shop,
) -> dict:
    """
    Return only information that is safe and
    necessary for the public booking experience.

    Internal billing, Stripe, HighLevel,
    subscription, AI receptionist, and other
    administrative configuration must not be
    exposed through the public shop endpoint.
    """

    return {
        "id": str(shop.id),
        "slug": shop.slug,
        "name": shop.name,
        "business_type": shop.business_type,
        "phone": shop.phone,
        "timezone": shop.timezone,
        "payment_policy": shop.payment_policy,
    }


@router.post("/shops")
def create_shop(
    payload: ShopCreate,
    db: Session = Depends(get_db),
):
    clean_name = str(
        payload.name or ""
    ).strip()

    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business name is required.",
        )

    requested_slug = (
        payload.slug
        or clean_name
    )

    clean_slug = normalize_slug(
        requested_slug
    )

    if not clean_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A valid business slug "
                "is required."
            ),
        )

    clean_business_type = str(
        payload.business_type or ""
    ).strip().lower()

    if not clean_business_type:
        clean_business_type = (
            "service_business"
        )

    existing_shop = (
        db.query(Shop)
        .filter(
            Shop.slug == clean_slug
        )
        .first()
    )

    if existing_shop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "That business URL is "
                "already in use."
            ),
        )

    shop = Shop(
        slug=clean_slug,
        name=clean_name,
        business_type=clean_business_type,
        phone=payload.phone,
        timezone=payload.timezone,
    )

    db.add(shop)

    try:
        db.commit()
        db.refresh(shop)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The business could not be "
                "created because one of its "
                "values is already in use."
            ),
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The business could not "
                "be created."
            ),
        )

    return shop


@router.get("/shops")
def list_shops(
    shop_slug: str,
    db: Session = Depends(get_db),
):
    """
    Public booking lookup for one specific
    business.

    shop_slug is required so an unscoped
    request can never return every ChairTime
    business.

    Only fields needed by the public booking
    experience are returned.
    """

    clean_slug = require_public_shop_slug(
        shop_slug
    )

    shop = (
        db.query(Shop)
        .filter(
            Shop.slug == clean_slug
        )
        .first()
    )

    if not shop:
        return []

    return [
        public_shop_response(
            shop
        )
    ]


@router.patch(
    "/shops/{shop_slug}/payment-policy"
)
def update_shop_payment_policy(
    shop_slug: str,
    payload: ShopPaymentPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Change the business's reservation payment
    policy.

    Only the authenticated owner of this
    business may change this setting.
    """

    clean_slug = require_owner_for_shop(
        shop_slug,
        current_user,
    )

    shop = (
        db.query(Shop)
        .filter(
            Shop.slug == clean_slug
        )
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found.",
        )

    shop.payment_policy = (
        payload.payment_policy
    )

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
                "The payment preference "
                "could not be saved."
            ),
        )

    return {
        "slug": shop.slug,
        "payment_policy": (
            shop.payment_policy
        ),
    }


@router.get(
    "/shops/{shop_slug}/staff-appointment-permission"
)
def get_staff_appointment_permission(
    shop_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    clean_slug = require_shop_access(
        shop_slug,
        current_user,
    )

    shop = (
        db.query(Shop)
        .filter(
            Shop.slug == clean_slug
        )
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found.",
        )

    return {
        "staff_can_manage_other_staff_appointments": bool(
            shop.staff_can_manage_other_staff_appointments
        ),
    }


@router.patch(
    "/shops/{shop_slug}/staff-appointment-permission"
)
def update_staff_appointment_permission(
    shop_slug: str,
    payload: ShopStaffAppointmentPermissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    clean_slug = require_owner_for_shop(
        shop_slug,
        current_user,
    )

    shop = (
        db.query(Shop)
        .filter(
            Shop.slug == clean_slug
        )
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found.",
        )

    shop.staff_can_manage_other_staff_appointments = (
        payload.staff_can_manage_other_staff_appointments
    )

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
                "The staff appointment permission "
                "could not be saved."
            ),
        )

    return {
        "staff_can_manage_other_staff_appointments": bool(
            shop.staff_can_manage_other_staff_appointments
        ),
    }
