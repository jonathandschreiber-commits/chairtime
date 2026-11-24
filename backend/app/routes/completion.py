"""Confirm payment and complete a shop appointment in one transaction."""
from typing import Literal

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AppointmentCompletionNote, Service, User
from app.payment_records import ManualAppointmentPayment, ServicePayment
from app.routes.appointments import require_appointment_modify_permission
from app.routes.auth import get_current_user
from app.routes.payments import appointment_for_user, reconcile, stripe_failure
from app.service_packages import current_redemption, redeem_on_completion

router = APIRouter()


class CompletionInput(BaseModel):
    method: Literal["stripe", "package", "cash", "check", "external_card", "bank_transfer", "other"]
    note: str = Field(default="", max_length=2000)
    no_notes: bool = False


@router.post("/appointments/{appointment_id}/complete")
def complete_appointment(appointment_id: str, payload: CompletionInput,
                         user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    appointment = appointment_for_user(db, appointment_id, user)
    require_appointment_modify_permission(db, user, appointment, user.shop_slug)
    if appointment.status == "completed":
        return {"status": "completed"}
    if appointment.status in {"canceled", "no_show"}:
        raise HTTPException(409, "Reconfirm this appointment before completing it.")
    note = payload.note.strip()
    if bool(note) == payload.no_notes:
        raise HTTPException(422, "Enter a note or select None.")

    payment = db.query(ServicePayment).filter_by(
        appointment_id=appointment.id, shop_slug=user.shop_slug,
    ).first()
    if payload.method == "stripe":
        if payment:
            try:
                reconcile(db, payment)
            except stripe.StripeError:
                raise stripe_failure()
        if not payment or payment.status != "paid":
            raise HTTPException(409, "Stripe must confirm payment before completion.")
    elif payload.method == "package":
        redeem_on_completion(db, appointment, user.id)
        db.flush()
        if not current_redemption(db, appointment):
            raise HTTPException(409, "No prepaid session could be applied to this appointment.")
    else:
        if current_redemption(db, appointment) or payment:
            raise HTTPException(409, "An existing payment or Stripe attempt must be resolved first.")
        service = db.query(Service).filter_by(id=appointment.service_id, shop_slug=user.shop_slug).first()
        if not service or service.price is None:
            raise HTTPException(409, "Set a service price before recording payment.")
        db.add(ManualAppointmentPayment(appointment_id=appointment.id, shop_slug=user.shop_slug,
                                        method=payload.method, amount_cents=int(service.price * 100),
                                        recorded_by=user.id))

    if note:
        db.add(AppointmentCompletionNote(appointment_id=appointment.id, shop_slug=user.shop_slug,
                                         body=note, created_by=user.id))
    appointment.status = "completed"
    db.commit()
    return {"status": "completed"}
