import asyncio
import os
import logging
import time
from typing import Optional
from urllib.parse import unquote

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.routes.auth import get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)

HIGHLEVEL_API_BASE_URL = "https://services.leadconnectorhq.com"
HIGHLEVEL_VOICE_API_VERSION = "v3"

CHAIRTIME_PUBLIC_API_BASE_URL = os.getenv(
    "CHAIRTIME_PUBLIC_API_BASE_URL",
    "https://chairtime-production-94da.up.railway.app",
).rstrip("/")

CHAIRTIME_INTERNAL_API_BASE_URL = os.getenv(
    "CHAIRTIME_INTERNAL_API_BASE_URL",
    "http://127.0.0.1:8080",
).rstrip("/")

CHAIRTIME_AVAILABILITY_URL = (
    f"{CHAIRTIME_INTERNAL_API_BASE_URL}/api/voice/availability"
)

CHAIRTIME_BOOKING_URL = (
    f"{CHAIRTIME_INTERNAL_API_BASE_URL}/api/voice/book"
)

TEST_AGENT_NAME = "ChairTime Provisioning Test"

TEST_AGENT_PROMPT = 'You are the appointment receptionist for this business. Be warm, brief, and efficient.\nUse ChairTime actions for real availability and bookings. Never invent an opening or claim a booking succeeded before the booking action confirms it.\nA caller saying anyone, any barber, whoever is available, or no preference has given a complete staff preference. Do not ask them to choose a provider. Use No preference for the availability and booking actions. Tell the caller the assigned provider after booking.\nCollect the service and date, then check availability. A morning, afternoon, or evening request is sufficient; pass that time window to the availability action. Morning is before noon, afternoon is noon to 5 PM, and evening is 5 PM onward, subject to actual shop hours. Offer up to three suitable returned times. If the caller asks for the earliest opening, use the earliest matching time. If they give an exact time, check that time directly.\nOnce the caller chooses a time, collect only missing booking information and book. A clear request to book is authorization; do not ask for another confirmation of the same service, date, time, or provider. Ask only when information is missing or genuinely ambiguous.\nAfter a successful booking, state the assigned provider, date, and time, and say that a confirmation text was sent only if confirmation_sms_sent is true. If texting failed, say the appointment is booked but the text could not be sent. Do not promise a reminder was delivered merely because it is scheduled.\nDo not repeat idle check-ins or narrate a long wait. If an action fails, apologize briefly and offer a useful next step. Never pretend to be checking availability when no action is running.'


class TenantAvailabilityRequest(BaseModel):
    service_name: str
    target_date: str
    barber_name: Optional[str] = None
    time_window: Optional[str] = None
    preferred_start_time: Optional[str] = None


class TenantBookingRequest(BaseModel):
    service_name: str
    target_date: str
    start_time: str
    customer_name: str
    customer_phone: str
    barber_name: Optional[str] = None


def get_highlevel_api_token() -> str:
    token = os.getenv("HIGHLEVEL_API_TOKEN")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "HIGHLEVEL_API_TOKEN environment "
                "variable is missing."
            ),
        )

    return token.strip()


def get_highlevel_location_id() -> str:
    location_id = os.getenv("HIGHLEVEL_LOCATION_ID")

    if not location_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "HIGHLEVEL_LOCATION_ID environment "
                "variable is missing."
            ),
        )

    return location_id.strip()


def highlevel_voice_headers() -> dict:
    return {
        "Authorization": (
            f"Bearer {get_highlevel_api_token()}"
        ),
        "Version": HIGHLEVEL_VOICE_API_VERSION,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ChairTime/1.0",
    }


def get_current_shop(
    current_user: User,
    db: Session,
) -> Shop:
    shop = (
        db.query(Shop)
        .filter(Shop.id == current_user.shop_id)
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found.",
        )

    return shop


def get_shop_by_slug(
    shop_slug: str,
    db: Session,
) -> Shop:
    shop = (
        db.query(Shop)
        .filter(Shop.slug == shop_slug)
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found.",
        )

    return shop


def require_owner(current_user: User) -> None:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access is required.",
        )


def decode_highlevel_value(value):
    """
    Decode one additional URL-encoding layer left by HighLevel.

    For example, FastAPI may receive values such as:
        13%3A30
        John%20Smith
        No%20preference
    after HighLevel double-encodes query parameters.
    """
    if not isinstance(value, str):
        return value

    return unquote(value)


def decode_highlevel_fields(values: dict) -> dict:
    return {
        key: decode_highlevel_value(value)
        for key, value in values.items()
    }


def normalize_barber_name(
    barber_name: Optional[str],
) -> Optional[str]:
    if not barber_name:
        return None

    cleaned = barber_name.strip()

    if not cleaned:
        return None

    no_preference_values = {
        "no preference",
        "no preference.",
        "any",
        "anyone",
        "any staff",
        "any staff member",
        "any barber",
        "any provider",
    }

    if cleaned.lower() in no_preference_values:
        return None

    return cleaned


def safe_highlevel_error(
    response: requests.Response,
) -> dict:
    try:
        data = response.json()

        if isinstance(data, dict):
            return data

        return {
            "message": str(data)[:500],
        }

    except ValueError:
        return {
            "message": response.text[:500],
        }


def highlevel_error_text(
    response: requests.Response,
) -> str:
    return str(
        safe_highlevel_error(response)
    ).lower()


def raise_highlevel_error(
    response: requests.Response,
) -> None:
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={
            "message": (
                "HighLevel rejected the Voice AI request."
            ),
            "highlevel_status": response.status_code,
            "highlevel_error": safe_highlevel_error(
                response
            ),
        },
    )


def safe_action(action: dict) -> dict:
    if not isinstance(action, dict):
        return {}

    return {
        "id": (
            action.get("_id")
            or action.get("id")
        ),
        "action_type": (
            action.get("actionType")
            or action.get("action_type")
        ),
        "name": action.get("name"),
        "action_parameters": (
            action.get("actionParameters")
            or action.get("action_parameters")
        ),
    }


def safe_agent_summary(agent: dict) -> dict:
    if not isinstance(agent, dict):
        return {}

    return {
        "id": (
            agent.get("id")
            or agent.get("_id")
        ),
        "agent_name": (
            agent.get("agentName")
            or agent.get("name")
        ),
        "business_name": agent.get("businessName"),
        "location_id": agent.get("locationId"),
        "language": agent.get("language"),
        "inbound_number": agent.get(
            "inboundNumber"
        ),
    }


def highlevel_raw_request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
) -> requests.Response:
    try:
        return requests.request(
            method=method,
            url=f"{HIGHLEVEL_API_BASE_URL}{path}",
            headers=highlevel_voice_headers(),
            params=params,
            json=json_body,
            timeout=20,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to HighLevel.",
        )


def highlevel_request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
) -> requests.Response:
    response = highlevel_raw_request(
        method=method,
        path=path,
        params=params,
        json_body=json_body,
    )

    if response.status_code >= 400:
        raise_highlevel_error(response)

    return response


def response_json(
    response: requests.Response,
) -> dict:
    try:
        data = response.json()

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel returned an invalid response."
            ),
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel returned an unexpected response."
            ),
        )

    return data


def chairtime_voice_request(
    url: str,
    payload: dict,
) -> dict:
    try:
        response = requests.post(
            url,
            json=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "ChairTime-Voice-Proxy/1.0",
            },
            timeout=20,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Could not connect to the ChairTime "
                "voice booking service."
            ),
        )

    try:
        data = response.json()

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ChairTime voice service returned "
                "an invalid response."
            ),
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=data,
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ChairTime voice service returned "
                "an unexpected response."
            ),
        )

    return data


def extract_agents(data: dict) -> list:
    raw_agents = data.get("agents")

    if not isinstance(raw_agents, list):
        return []

    return [
        agent
        for agent in raw_agents
        if isinstance(agent, dict)
    ]


def extract_actions(agent_data: dict) -> list:
    raw_actions = agent_data.get("actions")

    if not isinstance(raw_actions, list):
        return []

    return [
        action
        for action in raw_actions
        if isinstance(action, dict)
    ]


def find_action_by_name(
    agent_data: dict,
    action_name: str,
) -> Optional[dict]:
    for action in extract_actions(agent_data):
        if action.get("name") == action_name:
            return action

    return None


def get_action_id(
    action: Optional[dict],
) -> Optional[str]:
    if not isinstance(action, dict):
        return None

    return (
        action.get("_id")
        or action.get("id")
    )


def get_agent_detail(
    agent_id: str,
    location_id: str,
) -> dict:
    response = highlevel_request(
        method="GET",
        path=f"/voice-ai/agents/{agent_id}",
        params={
            "locationId": location_id,
        },
    )

    return response_json(response)


def find_existing_test_agent(
    location_id: str,
) -> Optional[dict]:
    response = highlevel_request(
        method="GET",
        path="/voice-ai/agents",
        params={
            "locationId": location_id,
            "page": 1,
            "pageSize": 50,
        },
    )

    data = response_json(response)

    for agent in extract_agents(data):
        agent_name = (
            agent.get("agentName")
            or agent.get("name")
        )

        if agent_name == TEST_AGENT_NAME:
            return agent

    return None


def build_test_agent_payload(shop: Shop, location_id: str) -> dict:
    business_name = shop.name or shop.slug or "ChairTime Business"
    return {
        "locationId": location_id,
        "agentName": TEST_AGENT_NAME,
        "businessName": business_name,
        "welcomeMessage": f"Thanks for calling {business_name}. How can I help you today?",
        "agentPrompt": TEST_AGENT_PROMPT,
        "language": "en-US",
        "maxCallDuration": 300,
        "sendUserIdleReminders": False,
        "reminderAfterIdleTimeSeconds": 8,
        "timezone": shop.timezone or "America/New_York",
        "isAgentAsBackupDisabled": True,
    }

def get_or_create_test_agent(shop: Shop, location_id: str) -> tuple[dict, bool]:
    existing_agent = find_existing_test_agent(location_id=location_id)
    if existing_agent:
        return existing_agent, False
    response = highlevel_request(
        method="POST",
        path="/voice-ai/agents",
        json_body=build_test_agent_payload(shop=shop, location_id=location_id),
    )
    return response_json(response), True


def update_test_agent_settings(agent_id: str, location_id: str) -> dict:
    agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    if agent.get("agentName") != TEST_AGENT_NAME:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only the provisioning test agent may "
                "be updated."
            ),
        )

    payload = {
        "agentPrompt": TEST_AGENT_PROMPT,
        "sendUserIdleReminders": False,
    }

    response = highlevel_raw_request(
        method="PATCH",
        path=f"/voice-ai/agents/{agent_id}",
        params={
            "locationId": location_id,
        },
        json_body=payload,
    )

    if response.status_code >= 400:
        raise_highlevel_error(response)

    refreshed = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    if (
        refreshed.get("agentPrompt") != TEST_AGENT_PROMPT
        or refreshed.get("sendUserIdleReminders") is not False
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel did not retain the requested "
                "test-agent settings."
            ),
        )

    return refreshed

def tenant_availability_webhook_url(
    shop: Shop,
) -> str:
    return (
        f"{CHAIRTIME_PUBLIC_API_BASE_URL}"
        f"/api/ai-setup/webhook/"
        f"{shop.slug}/availability"
    )


def tenant_booking_webhook_url(
    shop: Shop,
) -> str:
    return (
        f"{CHAIRTIME_PUBLIC_API_BASE_URL}"
        f"/api/ai-setup/webhook/"
        f"{shop.slug}/book"
    )


def build_availability_action_payload(
    shop: Shop,
    agent_id: str,
    location_id: str,
) -> dict:
    return {
        "agentId": agent_id,
        "locationId": location_id,
        "actionType": "CUSTOM_ACTION",
        "name": "check_availability",
        "actionParameters": {
            "triggerPrompt": (
                "Use this action when the caller wants "
                "to book an appointment and you have "
                "collected the service, requested date, "
                "and staff preference. Always use this "
                "action before offering appointment times. "
                "Only offer times returned by ChairTime."
            ),
            "triggerMessage": (
                "Let me check what's available."
            ),
            "apiDetails": {
                "url": tenant_availability_webhook_url(
                    shop
                ),
                "method": "POST",
                "authenticationRequired": False,
                "headers": [
                    {
                        "key": "Content-Type",
                        "value": "application/json",
                    },
                ],
                "parameters": [
                    {
                        "name": "service_name",
                        "description": (
                            "Exact service name requested "
                            "by the caller."
                        ),
                        "type": "string",
                        "example": "Haircut",
                    },
                    {
                        "name": "target_date",
                        "description": (
                            "Requested appointment date "
                            "in YYYY-MM-DD format."
                        ),
                        "type": "string",
                        "example": "2026-09-10",
                    },
                    {
                        "name": "time_window",
                        "description": "Optional morning, afternoon, or evening. Use the caller's requested part of day.",
                        "type": "string",
                        "example": "afternoon",
                    },
                    {
                        "name": "preferred_start_time",
                        "description": "Optional exact requested time in 24-hour HH:MM format. Do not invent one.",
                        "type": "string",
                        "example": "10:00",
                    },
                    {
                        "name": "barber_name",
                        "description": (
                            "Requested barber or staff "
                            "member. If the caller has no "
                            "preference, send No preference."
                        ),
                        "type": "string",
                        "example": "No preference",
                    },
                ],
            },
            "selectedPaths": [
                "success", "barber", "service", "target_date",
                "slots", "available_count", "time_window",
            ],
        },
    }


def build_booking_action_payload(
    shop: Shop,
    agent_id: str,
    location_id: str,
) -> dict:
    return {
        "agentId": agent_id,
        "locationId": location_id,
        "actionType": "CUSTOM_ACTION",
        "name": "book_appointment",
        "actionParameters": {
            "triggerPrompt": (
                "Use this action only after the caller "
                "chooses an appointment time returned by "
                "check_availability and explicitly confirms "
                "that they want to book it. Collect the "
                "service, date, start time, customer name, "
                "customer phone number, and staff preference "
                "before using this action."
            ),
            "triggerMessage": (
                "One moment while I confirm that "
                "appointment for you."
            ),
            "apiDetails": {
                "url": tenant_booking_webhook_url(
                    shop
                ),
                "method": "POST",
                "authenticationRequired": False,
                "headers": [
                    {
                        "key": "Content-Type",
                        "value": "application/json",
                    },
                ],
                "parameters": [
                    {
                        "name": "service_name",
                        "description": (
                            "Exact service name selected "
                            "by the caller."
                        ),
                        "type": "string",
                        "example": "Haircut",
                    },
                    {
                        "name": "target_date",
                        "description": (
                            "Appointment date in "
                            "YYYY-MM-DD format."
                        ),
                        "type": "string",
                        "example": "2026-09-10",
                    },
                    {
                        "name": "start_time",
                        "description": (
                            "Appointment start time in "
                            "24-hour HH:MM format."
                        ),
                        "type": "string",
                        "example": "13:30",
                    },
                    {
                        "name": "customer_name",
                        "description": (
                            "Full name of the customer "
                            "booking the appointment."
                        ),
                        "type": "string",
                        "example": "John Smith",
                    },
                    {
                        "name": "customer_phone",
                        "description": (
                            "Customer phone number used "
                            "for the appointment and "
                            "confirmation text."
                        ),
                        "type": "string",
                        "example": "3015551212",
                    },
                    {
                        "name": "barber_name",
                        "description": (
                            "Selected barber or staff "
                            "member. If there was no staff "
                            "preference, send No preference."
                        ),
                        "type": "string",
                        "example": "No preference",
                    },
                ],
            },
            "selectedPaths": [
                "success",
                "message",
                "appointment_id",
                "barber",
                "service",
                "start_datetime",
                "status",
                "confirmation_sms_sent",
                "confirmation_sms_error",
                "reminder_scheduled",
            ],
        },
    }


def verify_action_after_warning(
    agent_id: str,
    location_id: str,
    action_name: str,
    response: requests.Response,
    expected_url: Optional[str] = None,
) -> Optional[dict]:
    error_text = highlevel_error_text(response)

    known_highlevel_warning = (
        "maximum call stack size exceeded"
        in error_text
        or "action with same name already exists"
        in error_text
    )

    if not known_highlevel_warning:
        return None

    refreshed_agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    refreshed_action = find_action_by_name(
        agent_data=refreshed_agent,
        action_name=action_name,
    )

    if not refreshed_action:
        return None

    if expected_url:
        action_parameters = (
            refreshed_action.get(
                "actionParameters"
            )
            or {}
        )

        api_details = (
            action_parameters.get(
                "apiDetails"
            )
            or {}
        )

        stored_url = api_details.get("url")

        if stored_url != expected_url:
            return None
    
    return refreshed_action

import asyncio
import os
import logging
import time
from typing import Optional
from urllib.parse import unquote

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.routes.auth import get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)

HIGHLEVEL_API_BASE_URL = "https://services.leadconnectorhq.com"
HIGHLEVEL_VOICE_API_VERSION = "v3"

CHAIRTIME_PUBLIC_API_BASE_URL = os.getenv(
    "CHAIRTIME_PUBLIC_API_BASE_URL",
    "https://chairtime-production-94da.up.railway.app",
).rstrip("/")

CHAIRTIME_INTERNAL_API_BASE_URL = os.getenv(
    "CHAIRTIME_INTERNAL_API_BASE_URL",
    "http://127.0.0.1:8080",
).rstrip("/")

CHAIRTIME_AVAILABILITY_URL = (
    f"{CHAIRTIME_INTERNAL_API_BASE_URL}/api/voice/availability"
)

CHAIRTIME_BOOKING_URL = (
    f"{CHAIRTIME_INTERNAL_API_BASE_URL}/api/voice/book"
)

TEST_AGENT_NAME = "ChairTime Provisioning Test"

TEST_AGENT_PROMPT = 'You are the appointment receptionist for this business. Be warm, brief, and efficient.\nUse ChairTime actions for real availability and bookings. Never invent an opening or claim a booking succeeded before the booking action confirms it.\nA caller saying anyone, any barber, whoever is available, or no preference has given a complete staff preference. Do not ask them to choose a provider. Use No preference for the availability and booking actions. Tell the caller the assigned provider after booking.\nCollect the service and date, then check availability. A morning, afternoon, or evening request is sufficient; pass that time window to the availability action. Morning is before noon, afternoon is noon to 5 PM, and evening is 5 PM onward, subject to actual shop hours. Offer up to three suitable returned times. If the caller asks for the earliest opening, use the earliest matching time. If they give an exact time, check that time directly.\nOnce the caller chooses a time, collect only missing booking information and book. A clear request to book is authorization; do not ask for another confirmation of the same service, date, time, or provider. Ask only when information is missing or genuinely ambiguous.\nAfter a successful booking, state the assigned provider, date, and time, and say that a confirmation text was sent only if confirmation_sms_sent is true. If texting failed, say the appointment is booked but the text could not be sent. Do not promise a reminder was delivered merely because it is scheduled.\nDo not repeat idle check-ins or narrate a long wait. If an action fails, apologize briefly and offer a useful next step. Never pretend to be checking availability when no action is running.'


class TenantAvailabilityRequest(BaseModel):
    service_name: str
    target_date: str
    barber_name: Optional[str] = None
    time_window: Optional[str] = None
    preferred_start_time: Optional[str] = None


class TenantBookingRequest(BaseModel):
    service_name: str
    target_date: str
    start_time: str
    customer_name: str
    customer_phone: str
    barber_name: Optional[str] = None


def get_highlevel_api_token() -> str:
    token = os.getenv("HIGHLEVEL_API_TOKEN")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "HIGHLEVEL_API_TOKEN environment "
                "variable is missing."
            ),
        )

    return token.strip()


def get_highlevel_location_id() -> str:
    location_id = os.getenv("HIGHLEVEL_LOCATION_ID")

    if not location_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "HIGHLEVEL_LOCATION_ID environment "
                "variable is missing."
            ),
        )

    return location_id.strip()


def highlevel_voice_headers() -> dict:
    return {
        "Authorization": (
            f"Bearer {get_highlevel_api_token()}"
        ),
        "Version": HIGHLEVEL_VOICE_API_VERSION,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ChairTime/1.0",
    }


def get_current_shop(
    current_user: User,
    db: Session,
) -> Shop:
    shop = (
        db.query(Shop)
        .filter(Shop.id == current_user.shop_id)
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found.",
        )

    return shop


def get_shop_by_slug(
    shop_slug: str,
    db: Session,
) -> Shop:
    shop = (
        db.query(Shop)
        .filter(Shop.slug == shop_slug)
        .first()
    )

    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found.",
        )

    return shop


def require_owner(current_user: User) -> None:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access is required.",
        )


def decode_highlevel_value(value):
    """
    Decode one additional URL-encoding layer left by HighLevel.

    For example, FastAPI may receive values such as:
        13%3A30
        John%20Smith
        No%20preference
    after HighLevel double-encodes query parameters.
    """
    if not isinstance(value, str):
        return value

    return unquote(value)


def decode_highlevel_fields(values: dict) -> dict:
    return {
        key: decode_highlevel_value(value)
        for key, value in values.items()
    }


def normalize_barber_name(
    barber_name: Optional[str],
) -> Optional[str]:
    if not barber_name:
        return None

    cleaned = barber_name.strip()

    if not cleaned:
        return None

    no_preference_values = {
        "no preference",
        "no preference.",
        "any",
        "anyone",
        "any staff",
        "any staff member",
        "any barber",
        "any provider",
    }

    if cleaned.lower() in no_preference_values:
        return None

    return cleaned


def safe_highlevel_error(
    response: requests.Response,
) -> dict:
    try:
        data = response.json()

        if isinstance(data, dict):
            return data

        return {
            "message": str(data)[:500],
        }

    except ValueError:
        return {
            "message": response.text[:500],
        }


def highlevel_error_text(
    response: requests.Response,
) -> str:
    return str(
        safe_highlevel_error(response)
    ).lower()


def raise_highlevel_error(
    response: requests.Response,
) -> None:
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={
            "message": (
                "HighLevel rejected the Voice AI request."
            ),
            "highlevel_status": response.status_code,
            "highlevel_error": safe_highlevel_error(
                response
            ),
        },
    )


def safe_action(action: dict) -> dict:
    if not isinstance(action, dict):
        return {}

    return {
        "id": (
            action.get("_id")
            or action.get("id")
        ),
        "action_type": (
            action.get("actionType")
            or action.get("action_type")
        ),
        "name": action.get("name"),
        "action_parameters": (
            action.get("actionParameters")
            or action.get("action_parameters")
        ),
    }


def safe_agent_summary(agent: dict) -> dict:
    if not isinstance(agent, dict):
        return {}

    return {
        "id": (
            agent.get("id")
            or agent.get("_id")
        ),
        "agent_name": (
            agent.get("agentName")
            or agent.get("name")
        ),
        "business_name": agent.get("businessName"),
        "location_id": agent.get("locationId"),
        "language": agent.get("language"),
        "inbound_number": agent.get(
            "inboundNumber"
        ),
    }


def highlevel_raw_request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
) -> requests.Response:
    try:
        return requests.request(
            method=method,
            url=f"{HIGHLEVEL_API_BASE_URL}{path}",
            headers=highlevel_voice_headers(),
            params=params,
            json=json_body,
            timeout=20,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to HighLevel.",
        )


def highlevel_request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
) -> requests.Response:
    response = highlevel_raw_request(
        method=method,
        path=path,
        params=params,
        json_body=json_body,
    )

    if response.status_code >= 400:
        raise_highlevel_error(response)

    return response


def response_json(
    response: requests.Response,
) -> dict:
    try:
        data = response.json()

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel returned an invalid response."
            ),
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel returned an unexpected response."
            ),
        )

    return data


def chairtime_voice_request(
    url: str,
    payload: dict,
) -> dict:
    try:
        response = requests.post(
            url,
            json=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "ChairTime-Voice-Proxy/1.0",
            },
            timeout=20,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Could not connect to the ChairTime "
                "voice booking service."
            ),
        )

    try:
        data = response.json()

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ChairTime voice service returned "
                "an invalid response."
            ),
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=data,
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "ChairTime voice service returned "
                "an unexpected response."
            ),
        )

    return data


def extract_agents(data: dict) -> list:
    raw_agents = data.get("agents")

    if not isinstance(raw_agents, list):
        return []

    return [
        agent
        for agent in raw_agents
        if isinstance(agent, dict)
    ]


def extract_actions(agent_data: dict) -> list:
    raw_actions = agent_data.get("actions")

    if not isinstance(raw_actions, list):
        return []

    return [
        action
        for action in raw_actions
        if isinstance(action, dict)
    ]


def find_action_by_name(
    agent_data: dict,
    action_name: str,
) -> Optional[dict]:
    for action in extract_actions(agent_data):
        if action.get("name") == action_name:
            return action

    return None


def get_action_id(
    action: Optional[dict],
) -> Optional[str]:
    if not isinstance(action, dict):
        return None

    return (
        action.get("_id")
        or action.get("id")
    )


def get_agent_detail(
    agent_id: str,
    location_id: str,
) -> dict:
    response = highlevel_request(
        method="GET",
        path=f"/voice-ai/agents/{agent_id}",
        params={
            "locationId": location_id,
        },
    )

    return response_json(response)


def find_existing_test_agent(
    location_id: str,
) -> Optional[dict]:
    response = highlevel_request(
        method="GET",
        path="/voice-ai/agents",
        params={
            "locationId": location_id,
            "page": 1,
            "pageSize": 50,
        },
    )

    data = response_json(response)

    for agent in extract_agents(data):
        agent_name = (
            agent.get("agentName")
            or agent.get("name")
        )

        if agent_name == TEST_AGENT_NAME:
            return agent

    return None


def build_test_agent_payload(shop: Shop, location_id: str) -> dict:
    business_name = shop.name or shop.slug or "ChairTime Business"
    return {
        "locationId": location_id,
        "agentName": TEST_AGENT_NAME,
        "businessName": business_name,
        "welcomeMessage": f"Thanks for calling {business_name}. How can I help you today?",
        "agentPrompt": TEST_AGENT_PROMPT,
        "language": "en-US",
        "maxCallDuration": 300,
        "sendUserIdleReminders": False,
        "reminderAfterIdleTimeSeconds": 8,
        "timezone": shop.timezone or "America/New_York",
        "isAgentAsBackupDisabled": True,
    }

def get_or_create_test_agent(shop: Shop, location_id: str) -> tuple[dict, bool]:
    existing_agent = find_existing_test_agent(location_id=location_id)
    if existing_agent:
        return existing_agent, False
    response = highlevel_request(
        method="POST",
        path="/voice-ai/agents",
        json_body=build_test_agent_payload(shop=shop, location_id=location_id),
    )
    return response_json(response), True


def update_test_agent_settings(agent_id: str, location_id: str) -> dict:
    agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    if agent.get("agentName") != TEST_AGENT_NAME:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only the provisioning test agent may "
                "be updated."
            ),
        )

    payload = {
        "agentPrompt": TEST_AGENT_PROMPT,
        "sendUserIdleReminders": False,
    }

    response = highlevel_raw_request(
        method="PATCH",
        path=f"/voice-ai/agents/{agent_id}",
        params={
            "locationId": location_id,
        },
        json_body=payload,
    )

    if response.status_code >= 400:
        raise_highlevel_error(response)

    refreshed = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    if (
        refreshed.get("agentPrompt") != TEST_AGENT_PROMPT
        or refreshed.get("sendUserIdleReminders") is not False
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel did not retain the requested "
                "test-agent settings."
            ),
        )

    return refreshed

def tenant_availability_webhook_url(
    shop: Shop,
) -> str:
    return (
        f"{CHAIRTIME_PUBLIC_API_BASE_URL}"
        f"/api/ai-setup/webhook/"
        f"{shop.slug}/availability"
    )


def tenant_booking_webhook_url(
    shop: Shop,
) -> str:
    return (
        f"{CHAIRTIME_PUBLIC_API_BASE_URL}"
        f"/api/ai-setup/webhook/"
        f"{shop.slug}/book"
    )


def build_availability_action_payload(
    shop: Shop,
    agent_id: str,
    location_id: str,
) -> dict:
    return {
        "agentId": agent_id,
        "locationId": location_id,
        "actionType": "CUSTOM_ACTION",
        "name": "check_availability",
        "actionParameters": {
            "triggerPrompt": (
                "Use this action when the caller wants "
                "to book an appointment and you have "
                "collected the service, requested date, "
                "and staff preference. Always use this "
                "action before offering appointment times. "
                "Only offer times returned by ChairTime."
            ),
            "triggerMessage": (
                "Let me check what's available."
            ),
            "apiDetails": {
                "url": tenant_availability_webhook_url(
                    shop
                ),
                "method": "POST",
                "authenticationRequired": False,
                "headers": [
                    {
                        "key": "Content-Type",
                        "value": "application/json",
                    },
                ],
                "parameters": [
                    {
                        "name": "service_name",
                        "description": (
                            "Exact service name requested "
                            "by the caller."
                        ),
                        "type": "string",
                        "example": "Haircut",
                    },
                    {
                        "name": "target_date",
                        "description": (
                            "Requested appointment date "
                            "in YYYY-MM-DD format."
                        ),
                        "type": "string",
                        "example": "2026-09-10",
                    },
                    {
                        "name": "time_window",
                        "description": "Optional morning, afternoon, or evening. Use the caller's requested part of day.",
                        "type": "string",
                        "example": "afternoon",
                    },
                    {
                        "name": "preferred_start_time",
                        "description": "Optional exact requested time in 24-hour HH:MM format. Do not invent one.",
                        "type": "string",
                        "example": "10:00",
                    },
                    {
                        "name": "barber_name",
                        "description": (
                            "Requested barber or staff "
                            "member. If the caller has no "
                            "preference, send No preference."
                        ),
                        "type": "string",
                        "example": "No preference",
                    },
                ],
            },
            "selectedPaths": [
                "success", "barber", "service", "target_date",
                "slots", "available_count", "time_window",
            ],
        },
    }


def build_booking_action_payload(
    shop: Shop,
    agent_id: str,
    location_id: str,
) -> dict:
    return {
        "agentId": agent_id,
        "locationId": location_id,
        "actionType": "CUSTOM_ACTION",
        "name": "book_appointment",
        "actionParameters": {
            "triggerPrompt": (
                "Use this action only after the caller "
                "chooses an appointment time returned by "
                "check_availability and explicitly confirms "
                "that they want to book it. Collect the "
                "service, date, start time, customer name, "
                "customer phone number, and staff preference "
                "before using this action."
            ),
            "triggerMessage": (
                "One moment while I confirm that "
                "appointment for you."
            ),
            "apiDetails": {
                "url": tenant_booking_webhook_url(
                    shop
                ),
                "method": "POST",
                "authenticationRequired": False,
                "headers": [
                    {
                        "key": "Content-Type",
                        "value": "application/json",
                    },
                ],
                "parameters": [
                    {
                        "name": "service_name",
                        "description": (
                            "Exact service name selected "
                            "by the caller."
                        ),
                        "type": "string",
                        "example": "Haircut",
                    },
                    {
                        "name": "target_date",
                        "description": (
                            "Appointment date in "
                            "YYYY-MM-DD format."
                        ),
                        "type": "string",
                        "example": "2026-09-10",
                    },
                    {
                        "name": "start_time",
                        "description": (
                            "Appointment start time in "
                            "24-hour HH:MM format."
                        ),
                        "type": "string",
                        "example": "13:30",
                    },
                    {
                        "name": "customer_name",
                        "description": (
                            "Full name of the customer "
                            "booking the appointment."
                        ),
                        "type": "string",
                        "example": "John Smith",
                    },
                    {
                        "name": "customer_phone",
                        "description": (
                            "Customer phone number used "
                            "for the appointment and "
                            "confirmation text."
                        ),
                        "type": "string",
                        "example": "3015551212",
                    },
                    {
                        "name": "barber_name",
                        "description": (
                            "Selected barber or staff "
                            "member. If there was no staff "
                            "preference, send No preference."
                        ),
                        "type": "string",
                        "example": "No preference",
                    },
                ],
            },
            "selectedPaths": [
                "success",
                "message",
                "appointment_id",
                "barber",
                "service",
                "start_datetime",
                "status",
                "confirmation_sms_sent",
                "confirmation_sms_error",
                "reminder_scheduled",
            ],
        },
    }


def verify_action_after_warning(
    agent_id: str,
    location_id: str,
    action_name: str,
    response: requests.Response,
    expected_url: Optional[str] = None,
) -> Optional[dict]:
    error_text = highlevel_error_text(response)

    known_highlevel_warning = (
        "maximum call stack size exceeded"
        in error_text
        or "action with same name already exists"
        in error_text
    )

    if not known_highlevel_warning:
        return None

    refreshed_agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    refreshed_action = find_action_by_name(
        agent_data=refreshed_agent,
        action_name=action_name,
    )

    if not refreshed_action:
        return None

    if expected_url:
        action_parameters = (
            refreshed_action.get(
                "actionParameters"
            )
            or {}
        )

        api_details = (
            action_parameters.get(
                "apiDetails"
            )
            or {}
        )

        stored_url = api_details.get("url")

        if stored_url != expected_url:
            return None
    
    return refreshed_action
