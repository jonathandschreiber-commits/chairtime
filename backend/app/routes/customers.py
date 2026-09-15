from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, User
from app.routes.auth import get_current_user


router = APIRouter()


def require_user_shop_slug(current_user: User) -> str:
    shop_slug = str(
        current_user.shop_slug or ""
    ).strip().lower()

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not assigned to a business.",
        )

    return shop_slug


def require_customer_edit_permission(
    current_user: User,
) -> None:
    role = str(
        current_user.role or ""
    ).strip().lower()

    if role not in {"owner", "staff"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to edit customers.",
        )


@router.patch("/customers/update")
def update_customer(
    old_phone: str,
    new_name: str,
    new_phone: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_customer_edit_permission(current_user)

    shop_slug = require_user_shop_slug(
        current_user
    )

    clean_old_phone = str(
        old_phone or ""
    ).strip()

    clean_new_name = str(
        new_name or ""
    ).strip()

    clean_new_phone = str(
        new_phone or ""
    ).strip()

    if not clean_old_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current customer phone number is required.",
        )

    if not clean_new_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer name is required.",
        )

    if not clean_new_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer phone number is required.",
        )

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.shop_slug == shop_slug,
            Appointment.customer_phone == clean_old_phone,
        )
        .all()
    )

    if not appointments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    for appointment in appointments:
        appointment.customer_name = clean_new_name
        appointment.customer_phone = clean_new_phone

    try:
        db.commit()
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Customer information could not be updated.",
        )

    return {
        "success": True,
        "updated": len(appointments),
    }


@router.patch("/customers/tags")
def update_customer_tags(
    customer_phone: str,
    customer_tags: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_customer_edit_permission(current_user)

    shop_slug = require_user_shop_slug(
        current_user
    )

    clean_customer_phone = str(
        customer_phone or ""
    ).strip()

    if not clean_customer_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer phone number is required.",
        )

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.shop_slug == shop_slug,
            Appointment.customer_phone == clean_customer_phone,
        )
        .all()
    )

    if not appointments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    for appointment in appointments:
        appointment.customer_tags = customer_tags

    try:
        db.commit()
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Customer tags could not be updated.",
        )

    return {
        "success": True,
        "updated": len(appointments),
    }


@router.patch("/customers/notes")
def update_customer_notes(
    customer_phone: str,
    customer_notes: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_customer_edit_permission(current_user)

    shop_slug = require_user_shop_slug(
        current_user
    )

    clean_customer_phone = str(
        customer_phone or ""
    ).strip()

    if not clean_customer_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer phone number is required.",
        )

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.shop_slug == shop_slug,
            Appointment.customer_phone == clean_customer_phone,
        )
        .all()
    )

    if not appointments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    for appointment in appointments:
        appointment.customer_notes = customer_notes

    try:
        db.commit()
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Customer notes could not be updated.",
        )

    return {
        "success": True,
        "updated": len(appointments),
    }
