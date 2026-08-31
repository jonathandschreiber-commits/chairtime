import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop
from app.schemas import (
    ShopCreate,
    ShopPaymentPolicyUpdate,
)


router = APIRouter()


def normalize_slug(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")

    return slug


@router.post("/shops")
def create_shop(
    payload: ShopCreate,
    db: Session = Depends(get_db),
):
    clean_name = payload.name.strip()

    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business name is required.",
        )

    requested_slug = payload.slug or clean_name
    clean_slug = normalize_slug(requested_slug)

    if not clean_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid business slug is required.",
        )

    clean_business_type = payload.business_type.strip().lower()

    if not clean_business_type:
        clean_business_type = "service_business"

    existing_shop = (
        db.query(Shop)
        .filter(Shop.slug == clean_slug)
        .first()
    )

    if existing_shop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That business URL is already in use.",
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
                "The business could not be created because "
                "one of its values is already in use."
            ),
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The business could not be created.",
        )

    return shop


@router.get("/shops")
def list_shops(
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Shop)

    if shop_slug:
        clean_slug = normalize_slug(shop_slug)

        query = query.filter(
            Shop.slug == clean_slug
        )

    return query.order_by(Shop.name.asc()).all()


@router.patch("/shops/{shop_slug}/payment-policy")
def update_shop_payment_policy(
    shop_slug: str,
    payload: ShopPaymentPolicyUpdate,
    db: Session = Depends(get_db),
):
    clean_slug = normalize_slug(shop_slug)

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

    shop.payment_policy = payload.payment_policy

    try:
        db.commit()
        db.refresh(shop)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The payment preference could not be saved.",
        )

    return shop
