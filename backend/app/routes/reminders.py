import os
import json
from datetime import datetime, timedelta
from urllib import request, error
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment, Barber

router = APIRouter()


def highlevel_headers(api_token: str, location_id: str):
    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Version": "v3",
        "User-Agent": "ChairTimeBackend/1.0",
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

    clean_phone = "".join(character for character in str(phone) if character.isdigit())

    formatted_phone = f"+1{clean_phone}" if len(clean_phone) == 10 else str(phone)

    contact_payload = {
        "firstName": "ChairTime",
        "lastName": "Customer",
        "name": "ChairTime Customer",
        "email": f"{clean_phone}@chairtimehq.com",
        "locationId": location_id,
        "phone": formatted_phone,
        "source": "ChairTime",
        "country": "US",
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

        contact_id = contact_data.get("contact", {}).get("id") or contact_data.get("id")

    except error.HTTPError as http_error:
        error_body_text = http_error.read().decode("utf-8")

        try:
            error_body = json.loads(error_body_text)
        except Exception:
            error_body = {}

        contact_id = error_body.get("meta", {}).get("contactId")

        if not contact_id:
            return {
                "success": False,
                "step": "contact",
                "status": http_error.code,
                "error": error_body_text,
            }

    except Exception as general_error:
        return {
            "success": False,
            "step": "contact",
            "error": str(general_error),
        }

    if not contact_id:
        return {
            "success": False,
            "step": "contact_id",
            "error": "No contact ID returned",
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

    except error.HTTPError as http_error:
        return {
            "success": False,
            "step": "message",
            "contact_id": contact_id,
            "status": http_error.code,
            "error": http_error.read().decode("utf-8"),
        }

    except Exception as general_error:
        return {
            "success": False,
            "step": "message",
            "contact_id": contact_id,
            "error": str(general_error),
        }


@router.head("/send-reminders")
def send_reminders_head():
    return Response(status_code=200)


@router.get("/send-reminders")
def send_reminders_get(db: Session = Depends(get_db)):
    return send_reminders(db)


@router.post("/send-reminders")
def send_reminders(db: Session = Depends(get_db)):
    now = datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None)

    window_start = now + timedelta(hours=3)
    window_end = now + timedelta(hours=4)

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.status == "confirmed",
            Appointment.reminder_sent == False,
            Appointment.start_datetime >= window_start,
            Appointment.start_datetime <= window_end,
        )
        .all()
    )

    reminders_sent = 0

    for appointment in appointments:
        barber = db.query(Barber).filter(Barber.id == appointment.barber_id).first()

        reminder_message = (
            "Reminder: You have an appointment with "
            f"{barber.name if barber else 'your barber'} "
            "today at "
            f"{appointment.start_datetime.strftime('%I:%M %p')}. "
            "Reply STOP to unsubscribe."
        )

        result = send_highlevel_sms(
            appointment.customer_phone,
            reminder_message,
        )

        if result.get("success"):
            appointment.reminder_sent = True
            appointment.reminder_sent_at = datetime.utcnow()
            reminders_sent += 1

    db.commit()

    return {
        "success": True,
        "reminders_sent": reminders_sent,
    }


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

    except Exception as caught_error:
        return {
            "success": False,
            "error": str(caught_error),
        }


@router.get("/test-highlevel-sms")
def test_highlevel_sms(phone: str):
    result = send_highlevel_sms(
        phone,
        "ChairTime test message. Reply STOP to unsubscribe.",
    )

    return result