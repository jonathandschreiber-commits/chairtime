from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Appointment,
    AvailabilityRule,
    Barber,
    BlockedTime,
    Service,
    User,
)
from app.routes.auth import get_current_user
from app.schemas import BarberCreate, BarberUpdate


router = APIRouter()


def require_owner(
    current_user: User,
):
    role = str(
        current_user.role or ""
    ).strip().lower()

    if role != "owner":
        raise HTTPException(
            status_code=403,
            detail=(
                "Only the shop owner may manage "
                "staff members."
            ),
        )

    shop_slug = str(
        current_user.shop_slug or ""
    ).strip().lower()

    if not shop_slug:
        raise HTTPException(
            status_code=403,
            detail=(
                "Your account is not associated "
                "with a shop."
            ),
        )

    return shop_slug


@router.post("/barbers")
def create_barber(
    payload: BarberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    shop_slug = require_owner(
        current_user
    )

    payload_shop_slug = str(
        payload.shop_slug or ""
    ).strip().lower()

    if (
        payload_shop_slug
        and payload_shop_slug != shop_slug
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "You may only add staff members "
                "to your own shop."
            ),
        )

    barber_data = payload.model_dump()
    barber_data["shop_slug"] = shop_slug

    barber = Barber(
        **barber_data
    )

    db.add(barber)
    db.commit()
    db.refresh(barber)

    return barber


@router.get("/barbers")
def list_barbers(
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Barber)

    if shop_slug:
        query = query.filter(
            Barber.shop_slug == shop_slug
        )

    return query.all()


@router.delete("/barbers/{barber_id}")
def delete_barber(
    barber_id: str,
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    authenticated_shop_slug = require_owner(
        current_user
    )

    requested_shop_slug = str(
        shop_slug or ""
    ).strip().lower()

    if (
        requested_shop_slug
        and requested_shop_slug
        != authenticated_shop_slug
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "You may only delete staff members "
                "from your own shop."
            ),
        )

    barber = (
        db.query(Barber)
        .filter(
            Barber.id == barber_id,
            Barber.shop_slug
            == authenticated_shop_slug,
        )
        .first()
    )

    if not barber:
        raise HTTPException(
            status_code=404,
            detail="Staff member not found",
        )

    #
    # Preserve appointment history.
    #
    appointment_count = (
        db.query(Appointment)
        .filter(
            Appointment.barber_id == barber_id,
            Appointment.shop_slug
            == authenticated_shop_slug,
        )
        .count()
    )

    if appointment_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{barber.name} cannot be deleted because "
                f"{appointment_count} appointment"
                f"{'' if appointment_count == 1 else 's'} "
                "are associated with this staff member."
            ),
        )

    try:
        #
        # Remove staff-specific configuration first.
        #
        db.query(Service).filter(
            Service.barber_id == barber_id,
            Service.shop_slug
            == authenticated_shop_slug,
        ).delete(
            synchronize_session=False
        )

        db.query(AvailabilityRule).filter(
            AvailabilityRule.barber_id
            == barber_id,
            AvailabilityRule.shop_slug
            == authenticated_shop_slug,
        ).delete(
            synchronize_session=False
        )

        db.query(BlockedTime).filter(
            BlockedTime.barber_id == barber_id,
            BlockedTime.shop_slug
            == authenticated_shop_slug,
        ).delete(
            synchronize_session=False
        )

        #
        # Now the staff member can safely be removed.
        #
        db.delete(barber)
        db.commit()

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                f"{barber.name} could not be deleted."
            ),
        )

    return {
        "message": (
            f"{barber.name} deleted"
        ),
    }


@router.patch("/barbers/{barber_id}")
def update_barber(
    barber_id: str,
    payload: BarberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    authenticated_shop_slug = require_owner(
        current_user
    )

    barber = (
        db.query(Barber)
        .filter(
            Barber.id == barber_id,
            Barber.shop_slug
            == authenticated_shop_slug,
        )
        .first()
    )

    if not barber:
        raise HTTPException(
            status_code=404,
            detail="Staff member not found",
        )

    updates = payload.model_dump(
        exclude_unset=True
    )

    requested_shop_slug = str(
        updates.get("shop_slug") or ""
    ).strip().lower()

    if (
        requested_shop_slug
        and requested_shop_slug
        != authenticated_shop_slug
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "You may only update staff members "
                "in your own shop."
            ),
        )

    #
    # The authenticated account, not the browser,
    # determines which shop owns this staff member.
    #
    updates["shop_slug"] = (
        authenticated_shop_slug
    )

    for key, value in updates.items():
        setattr(
            barber,
            key,
            value,
        )

    db.commit()
    db.refresh(barber)

    return barber
