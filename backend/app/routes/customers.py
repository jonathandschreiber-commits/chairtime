from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment

router = APIRouter()


@router.patch("/customers/update")
def update_customer(
    old_phone: str,
    new_name: str,
    new_phone: str,
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Appointment).filter(Appointment.customer_phone == old_phone)

    if shop_slug:
        query = query.filter(Appointment.shop_slug == shop_slug)

    appointments = query.all()

    if not appointments:
        raise HTTPException(status_code=404, detail="Customer not found")

    for appointment in appointments:
        appointment.customer_name = new_name
        appointment.customer_phone = new_phone

    db.commit()

    return {"success": True, "updated": len(appointments)}


@router.patch("/customers/tags")
def update_customer_tags(
    customer_phone: str,
    customer_tags: str,
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Appointment).filter(
        Appointment.customer_phone == customer_phone
    )

    if shop_slug:
        query = query.filter(Appointment.shop_slug == shop_slug)

    appointments = query.all()

    if not appointments:
        raise HTTPException(status_code=404, detail="Customer not found")

    for appointment in appointments:
        appointment.customer_tags = customer_tags

    db.commit()

    return {"success": True, "updated": len(appointments)}


@router.patch("/customers/notes")
def update_customer_notes(
    customer_phone: str,
    customer_notes: str,
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Appointment).filter(
        Appointment.customer_phone == customer_phone
    )

    if shop_slug:
        query = query.filter(Appointment.shop_slug == shop_slug)

    appointments = query.all()

    if not appointments:
        raise HTTPException(status_code=404, detail="Customer not found")

    for appointment in appointments:
        appointment.customer_notes = customer_notes

    db.commit()

    return {"success": True, "updated": len(appointments)}