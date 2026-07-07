from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, AvailabilityRule, Barber, BlockedTime, Service

router = APIRouter()


@router.post("/migrate-shop")
def migrate_shop(
    shop_slug: str = "joebarber",
    db: Session = Depends(get_db),
):
    barbers_updated = (
        db.query(Barber)
        .filter(Barber.shop_slug == None)
        .update({"shop_slug": shop_slug}, synchronize_session=False)
    )

    services_updated = (
        db.query(Service)
        .filter(Service.shop_slug == None)
        .update({"shop_slug": shop_slug}, synchronize_session=False)
    )

    availability_updated = (
        db.query(AvailabilityRule)
        .filter(AvailabilityRule.shop_slug == None)
        .update({"shop_slug": shop_slug}, synchronize_session=False)
    )

    blocked_times_updated = (
        db.query(BlockedTime)
        .filter(BlockedTime.shop_slug == None)
        .update({"shop_slug": shop_slug}, synchronize_session=False)
    )

    appointments_updated = (
        db.query(Appointment)
        .filter(Appointment.shop_slug == None)
        .update({"shop_slug": shop_slug}, synchronize_session=False)
    )

    db.commit()

    return {
        "success": True,
        "shop_slug": shop_slug,
        "barbers_updated": barbers_updated,
        "services_updated": services_updated,
        "availability_updated": availability_updated,
        "blocked_times_updated": blocked_times_updated,
        "appointments_updated": appointments_updated,
    }