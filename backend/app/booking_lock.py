
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Barber


def lock_booking_provider(
    db: Session,
    shop_slug: str,
    barber_id: str,
) -> Barber:
    """
    Lock a provider's database row while checking and
    saving an appointment.

    PostgreSQL holds the row lock until the current
    transaction commits or rolls back. Competing
    bookings for the same provider must wait.

    Every appointment-creation and rescheduling path
    must use this function before its final conflict
    check.

    SQLite does not support PostgreSQL-style row locks.
    The local SQLite fallback therefore does not
    provide the same concurrency guarantee.
    """

    clean_shop_slug = str(
        shop_slug or ""
    ).strip().lower()

    clean_barber_id = str(
        barber_id or ""
    ).strip()

    if not clean_shop_slug or not clean_barber_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business and staff member are required.",
        )

    query = (
        db.query(Barber)
        .filter(
            Barber.id == clean_barber_id,
            Barber.shop_slug == clean_shop_slug,
        )
    )

    database_dialect = db.get_bind().dialect.name

    if database_dialect == "postgresql":
        query = query.with_for_update()

    barber = query.first()

    if barber is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found.",
        )

    return barber
