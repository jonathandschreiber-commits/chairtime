import json
import os
from datetime import datetime, timedelta, date
from urllib import request

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Barber, Service, AvailabilityRule, Appointment, Shop, BlockedTime
from app.schemas import (
    BarberCreate,
    ServiceCreate,
    AvailabilityCreate,
    AppointmentCreate,
    ShopCreate,
    BlockedTimeCreate,
    BarberUpdate,
    ServiceUpdate,
)
from app.scheduling import has_overlap, generate_available_slots

router = APIRouter()


def highlevel_headers(api_token: str, location_id: str):
    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Version": "2021-07-28",
        "locationId": location_id,
    }


def send_highlevel_sms(phone: str, message: str):
    api_token = os.getenv("HIGHLEVEL_API_TOKEN")
    location_id = os.getenv("HIGHLEVEL_LOCATION_ID")

    if not api_token or not location_id or not phone:
        return {
            "success": False,
            "step": "config",
            "error": "Missing HIGHLEVEL_API_TOKEN, HIGHLEVEL_LOCATION_ID, or phone",
        }

    contact_payload = {
        "locationId": location_id,
        "phone": phone,
    }

    contact_req = request.Request(
        "https://services.leadconnectorhq.com/contacts/",
        data=json.dumps(contact_payload).encode("utf-8"),
        headers=highlevel_headers(api_token, location_id),
        method="POST",
    )

    try:
        with request.urlopen(contact_req, timeout=10) as response:
            contact_data = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        return {
            "success": False,
            "step": "contact",
            "error": str(error),
        }

    contact_id = (
        contact_data.get("contact", {}).get("id")
        or contact_data.get("id")
    )

    if not contact_id:
        return {
            "success": False,
            "step": "contact_id",
            "error": "No contact ID returned",
            "response": contact_data,
        }

    message_payload = {
        "type": "SMS",
        "contactId": contact_id,
        "message": message,
    }

    message_req = request.Request(
        "https://services.leadconnectorhq.com/conversations/messages",
        data=json.dumps(message_payload).encode("utf-8"),
        headers=highlevel_headers(api_token, location_id),
        method="POST",
    )

    try:
        with request.urlopen(message_req, timeout=10) as response:
            message_data = response.read().decode("utf-8")

        return {
            "success": True,
            "step": "message",
            "contact_id": contact_id,
            "response": message_data,
        }

    except Exception as error:
        return {
            "success": False,
            "step": "message",
            "contact_id": contact_id,
            "error": str(error),
        }


@router.post("/barbers")
def create_barber(payload: BarberCreate, db: Session = Depends(get_db)):
    barber = Barber(**payload.model_dump())
    db.add(barber)
    db.commit()
    db.refresh(barber)
    return barber


@router.get("/barbers")
def list_barbers(db: Session = Depends(get_db)):
    return db.query(Barber).all()


@router.post("/services")
def create_service(payload: ServiceCreate, db: Session = Depends(get_db)):
    service = Service(**payload.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("/services")
def list_services(db: Session = Depends(get_db)):
    return db.query(Service).all()


@router.post("/availability-rules")
def create_availability_rule(payload: AvailabilityCreate, db: Session = Depends(get_db)):
    rule = AvailabilityRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/availability")
def get_availability(
    barber_id: str,
    service_id: str,
    target_date: date,
    db: Session = Depends(get_db),
):
    try:
        slots = generate_available_slots(db, barber_id, service_id, target_date)
        return {"slots": slots}
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/appointments")
def create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == payload.service_id).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    end_datetime = payload.start_datetime + timedelta(minutes=service.duration_minutes)

    overlap = has_overlap(
        db,
        payload.barber_id,
        payload.start_datetime,
        end_datetime,
    )

    if overlap:
        raise HTTPException(status_code=409, detail="Time slot already booked")

    appointment = Appointment(
        barber_id=payload.barber_id,
        service_id=payload.service_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        notes=payload.notes,
        start_datetime=payload.start_datetime,
        end_datetime=end_datetime,
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    barber = db.query(Barber).filter(Barber.id == appointment.barber_id).first()

    confirmation_message = (
        f"You're booked with {barber.name if barber else 'your barber'} "
        f"on {appointment.start_datetime.strftime('%A, %B %d at %I:%M %p')}. "
        "Reply STOP to unsubscribe."
    )

    send_highlevel_sms(appointment.customer_phone, confirmation_message)

    return appointment


@router.get("/appointments")
def list_appointments(db: Session = Depends(get_db)):
    return db.query(Appointment).all()


@router.patch("/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: str, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.status = "canceled"
    db.commit()
    db.refresh(appointment)
    return appointment


@router.delete("/services")
def delete_all_services(db: Session = Depends(get_db)):
    db.query(Service).delete()
    db.commit()
    return {"message": "All services deleted"}


@router.post("/shops")
def create_shop(payload: ShopCreate, db: Session = Depends(get_db)):
    shop = Shop(**payload.model_dump())
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop


@router.get("/shops")
def list_shops(db: Session = Depends(get_db)):
    return db.query(Shop).all()


@router.post("/blocked-times")
def create_blocked_time(payload: BlockedTimeCreate, db: Session = Depends(get_db)):
    blocked_time = BlockedTime(**payload.model_dump())
    db.add(blocked_time)
    db.commit()
    db.refresh(blocked_time)
    return blocked_time


@router.get("/blocked-times")
def list_blocked_times(db: Session = Depends(get_db)):
    return db.query(BlockedTime).all()


@router.delete("/barbers/{barber_id}")
def delete_barber(barber_id: str, db: Session = Depends(get_db)):
    barber = db.query(Barber).filter(Barber.id == barber_id).first()

    if not barber:
        raise HTTPException(status_code=404, detail="Barber not found")

    db.delete(barber)
    db.commit()
    return {"message": "Barber deleted"}


@router.delete("/services/{service_id}")
def delete_service(service_id: str, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == service_id).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    db.delete(service)
    db.commit()
    return {"message": "Service deleted"}


@router.delete("/blocked-times/{blocked_time_id}")
def delete_blocked_time(blocked_time_id: str, db: Session = Depends(get_db)):
    blocked_time = db.query(BlockedTime).filter(BlockedTime.id == blocked_time_id).first()

    if not blocked_time:
        raise HTTPException(status_code=404, detail="Blocked time not found")

    db.delete(blocked_time)
    db.commit()
    return {"message": "Blocked time deleted"}


@router.patch("/barbers/{barber_id}")
def update_barber(
    barber_id: str,
    payload: BarberUpdate,
    db: Session = Depends(get_db),
):
    barber = db.query(Barber).filter(Barber.id == barber_id).first()

    if not barber:
        raise HTTPException(status_code=404, detail="Barber not found")

    updates = payload.model_dump(exclude_unset=True)

    for key, value in updates.items():
        setattr(barber, key, value)

    db.commit()
    db.refresh(barber)
    return barber


@router.patch("/services/{service_id}")
def update_service(
    service_id: str,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
):
    service = db.query(Service).filter(Service.id == service_id).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    updates = payload.model_dump(exclude_unset=True)

    for key, value in updates.items():
        setattr(service, key, value)

    db.commit()
    db.refresh(service)
    return service


@router.get("/availability-rules")
def list_availability_rules(db: Session = Depends(get_db)):
    return db.query(AvailabilityRule).all()


@router.delete("/availability-rules/{rule_id}")
def delete_availability_rule(rule_id: str, db: Session = Depends(get_db)):
    rule = db.query(AvailabilityRule).filter(AvailabilityRule.id == rule_id).first()

    if not rule:
        raise HTTPException(status_code=404, detail="Availability rule not found")

    db.delete(rule)
    db.commit()
    return {"message": "Availability rule deleted"}


@router.patch("/appointments/{appointment_id}/status")
def update_appointment_status(
    appointment_id: str,
    status: str,
    db: Session = Depends(get_db),
):
    allowed_statuses = ["confirmed", "completed", "no_show", "canceled"]

    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Invalid appointment status")

    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.status = status
    db.commit()
    db.refresh(appointment)
    return appointment


@router.patch("/appointments/{appointment_id}/reschedule")
def reschedule_appointment(
    appointment_id: str,
    new_start_datetime: str,
    db: Session = Depends(get_db),
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    service = db.query(Service).filter(Service.id == appointment.service_id).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    new_start = datetime.fromisoformat(new_start_datetime)
    new_end = new_start + timedelta(minutes=service.duration_minutes)

    conflict = db.query(Appointment).filter(
        Appointment.barber_id == appointment.barber_id,
        Appointment.id != appointment.id,
        Appointment.status != "canceled",
        Appointment.start_datetime < new_end,
        Appointment.end_datetime > new_start,
    ).first()

    if conflict:
        raise HTTPException(status_code=409, detail="That time is already booked")

    blocked_conflict = db.query(BlockedTime).filter(
        BlockedTime.barber_id == appointment.barber_id,
        BlockedTime.start_datetime < new_end,
        BlockedTime.end_datetime > new_start,
    ).first()

    if blocked_conflict:
        raise HTTPException(status_code=409, detail="That time is blocked")

    appointment.start_datetime = new_start
    appointment.end_datetime = new_end
    appointment.status = "confirmed"

    db.commit()
    db.refresh(appointment)
    return appointment


@router.patch("/appointments/{appointment_id}/notes")
def update_appointment_notes(
    appointment_id: str,
    notes: str,
    db: Session = Depends(get_db),
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.notes = notes
    db.commit()
    db.refresh(appointment)
    return appointment


@router.get("/test-highlevel-location")
def test_highlevel_location():
    api_token = os.getenv("HIGHLEVEL_API_TOKEN")
    location_id = os.getenv("HIGHLEVEL_LOCATION_ID")

    if not api_token or not location_id:
        return {
            "success": False,
            "error": "Missing HIGHLEVEL_API_TOKEN or HIGHLEVEL_LOCATION_ID",
        }

    location_req = request.Request(
        f"https://services.leadconnectorhq.com/locations/{location_id}",
        headers=highlevel_headers(api_token, location_id),
        method="GET",
    )

    try:
        with request.urlopen(location_req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }


@router.get("/test-highlevel-sms")
def test_highlevel_sms(phone: str):
    result = send_highlevel_sms(
        phone,
        "ChairTime test message. Reply STOP to unsubscribe.",
    )

    return result