import asyncio
import hmac
import json
import os
import logging
import secrets
import time
from datetime import datetime, timezone
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

PRODUCTION_AGENT_NAME_PREFIX = "ChairTime AI"
PRODUCTION_WEBHOOK_SECRET_HEADER = "X-ChairTime-Webhook-Secret"


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


def highlevel_phone_purchase_headers() -> dict:
    return {
        "Authorization": (
            f"Bearer {get_highlevel_api_token()}"
        ),
        "Version": "v3",
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
    agent = get_agent_detail(agent_id=agent_id, location_id=location_id)
    if agent.get("agentName") != TEST_AGENT_NAME:
        raise HTTPException(status_code=409, detail="Only the provisioning test agent may be updated.")
    payload = {
        "agentPrompt": TEST_AGENT_PROMPT,
        "sendUserIdleReminders": False,
    }
    response = highlevel_raw_request(
        method="PATCH",
        path=f"/voice-ai/agents/{agent_id}",
        params={"locationId": location_id},
        json_body=payload,
    )
    if response.status_code >= 400:
        raise_highlevel_error(response)
    refreshed = get_agent_detail(agent_id=agent_id, location_id=location_id)
    if (refreshed.get("agentPrompt") != TEST_AGENT_PROMPT
            or refreshed.get("sendUserIdleReminders") is not False):
        raise HTTPException(status_code=502, detail="HighLevel did not retain the requested test-agent settings.")
    return refreshed


def production_agent_name(shop: Shop) -> str:
    identifier = shop.slug or str(shop.id)
    return f"{PRODUCTION_AGENT_NAME_PREFIX} - {identifier}"


def production_location_id(shop: Shop) -> str:
    stored_location_id = str(
        shop.highlevel_location_id or ""
    ).strip()

    if stored_location_id:
        return stored_location_id

    return get_highlevel_location_id()


def build_production_agent_payload(
    shop: Shop,
    location_id: str,
) -> dict:
    business_name = (
        shop.name
        or shop.slug
        or "ChairTime Business"
    )

    return {
        "locationId": location_id,
        "agentName": production_agent_name(shop),
        "businessName": business_name,
        "welcomeMessage": (
            f"Thanks for calling {business_name}. "
            "How can I help you today?"
        ),
        "agentPrompt": TEST_AGENT_PROMPT,
        "language": "en-US",
        "maxCallDuration": 300,
        "sendUserIdleReminders": False,
        "reminderAfterIdleTimeSeconds": 8,
        "timezone": (
            shop.timezone
            or "America/New_York"
        ),
        "isAgentAsBackupDisabled": True,
    }


def ensure_shop_webhook_secret(
    shop: Shop,
    db: Session,
) -> str:
    existing_secret = str(
        shop.highlevel_webhook_secret or ""
    ).strip()

    if existing_secret:
        return existing_secret

    shop.highlevel_webhook_secret = (
        secrets.token_urlsafe(32)
    )

    try:
        db.commit()
        db.refresh(shop)
    except Exception:
        db.rollback()
        raise

    return str(shop.highlevel_webhook_secret)


def verify_production_webhook_secret(
    shop: Shop,
    request: Request,
) -> None:
    expected_secret = str(
        shop.highlevel_webhook_secret or ""
    ).strip()
    received_secret = str(
        request.headers.get(
            PRODUCTION_WEBHOOK_SECRET_HEADER,
            "",
        )
        or ""
    ).strip()

    if (
        not expected_secret
        or not received_secret
        or not hmac.compare_digest(
            expected_secret,
            received_secret,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ChairTime AI webhook credential.",
        )


def production_availability_webhook_url(
    shop: Shop,
) -> str:
    return (
        f"{CHAIRTIME_PUBLIC_API_BASE_URL}"
        f"/api/ai-setup/tenant-webhook/"
        f"{shop.slug}/availability"
    )


def production_booking_webhook_url(
    shop: Shop,
) -> str:
    return (
        f"{CHAIRTIME_PUBLIC_API_BASE_URL}"
        f"/api/ai-setup/tenant-webhook/"
        f"{shop.slug}/book"
    )


def get_or_create_production_agent(
    shop: Shop,
    location_id: str,
    db: Session,
) -> tuple[dict, bool]:
    existing_agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if existing_agent_id:
        other_shop = (
            db.query(Shop)
            .filter(
                Shop.highlevel_agent_id
                == existing_agent_id,
                Shop.id != shop.id,
            )
            .first()
        )

        if other_shop:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This AI agent is already assigned "
                    "to another ChairTime shop."
                ),
            )

        agent = get_agent_detail(
            agent_id=existing_agent_id,
            location_id=location_id,
        )

        if agent.get("agentName") == TEST_AGENT_NAME:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The shared provisioning-test agent "
                    "cannot be assigned to a shop."
                ),
            )

        return agent, False

    response = highlevel_request(
        method="POST",
        path="/voice-ai/agents",
        json_body=build_production_agent_payload(
            shop=shop,
            location_id=location_id,
        ),
    )
    agent = response_json(response)
    agent_id = str(
        agent.get("id")
        or agent.get("_id")
        or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel did not return an ID for the "
                "shop AI receptionist."
            ),
        )

    conflicting_shop = (
        db.query(Shop)
        .filter(
            Shop.highlevel_agent_id == agent_id,
            Shop.id != shop.id,
        )
        .first()
    )

    if conflicting_shop:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "HighLevel returned an AI agent already "
                "assigned to another ChairTime shop."
            ),
        )

    shop.highlevel_agent_id = agent_id
    shop.highlevel_location_id = location_id

    try:
        db.commit()
        db.refresh(shop)
    except Exception:
        db.rollback()
        raise

    return agent, True


def update_production_agent_settings(
    shop: Shop,
    agent_id: str,
    location_id: str,
) -> dict:
    if str(shop.highlevel_agent_id or "") != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This AI agent is not assigned to the "
                "current ChairTime shop."
            ),
        )

    agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    if agent.get("agentName") == TEST_AGENT_NAME:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The shared provisioning-test agent "
                "cannot be used as a production agent."
            ),
        )

    payload = {
        "agentPrompt": TEST_AGENT_PROMPT,
        "sendUserIdleReminders": False,
    }

    response = highlevel_raw_request(
        method="PATCH",
        path=f"/voice-ai/agents/{agent_id}",
        params={"locationId": location_id},
        json_body=payload,
    )

    if response.status_code >= 400:
        raise_highlevel_error(response)

    refreshed = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    if (
        refreshed.get("agentPrompt")
        != TEST_AGENT_PROMPT
        or refreshed.get("sendUserIdleReminders")
        is not False
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel did not retain the requested "
                "shop AI settings."
            ),
        )

    return refreshed


def require_shop_agent(
    shop: Shop,
    agent_id: str,
) -> None:
    assigned_agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if (
        not assigned_agent_id
        or assigned_agent_id != agent_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI agent not found for this shop.",
        )


def require_shop_action(
    shop: Shop,
    action_id: str,
    location_id: str,
) -> dict:
    assigned_agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if not assigned_agent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI action not found for this shop.",
        )

    agent = get_agent_detail(
        agent_id=assigned_agent_id,
        location_id=location_id,
    )

    for action in extract_actions(agent):
        if get_action_id(action) == action_id:
            return action

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="AI action not found for this shop.",
    )


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
    webhook_url: Optional[str] = None,
    webhook_secret: Optional[str] = None,
) -> dict:
    headers = [
        {
            "key": "Content-Type",
            "value": "application/json",
        },
    ]

    if webhook_secret:
        headers.append(
            {
                "key": PRODUCTION_WEBHOOK_SECRET_HEADER,
                "value": webhook_secret,
            }
        )

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
                "url": (
                    webhook_url
                    or tenant_availability_webhook_url(
                        shop
                    )
                ),
                "method": "POST",
                "authenticationRequired": False,
                "headers": headers,
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
                        "description": (
                            "Optional morning, afternoon, "
                            "or evening. Use the caller's "
                            "requested part of day."
                        ),
                        "type": "string",
                        "example": "afternoon",
                    },
                    {
                        "name": "preferred_start_time",
                        "description": (
                            "Optional exact requested time "
                            "in 24-hour HH:MM format. "
                            "Do not invent one."
                        ),
                        "type": "string",
                        "example": "10:00",
                    },
                    {
                        "name": "barber_name",
                        "description": (
                            "Requested staff member. Use "
                            "No preference when the caller "
                            "does not care who provides "
                            "the service."
                        ),
                        "type": "string",
                        "example": "No preference",
                    },
                ],
            },
        },
    }


def build_booking_action_payload(
    shop: Shop,
    agent_id: str,
    location_id: str,
    webhook_url: Optional[str] = None,
    webhook_secret: Optional[str] = None,
) -> dict:
    headers = [
        {
            "key": "Content-Type",
            "value": "application/json",
        },
    ]

    if webhook_secret:
        headers.append(
            {
                "key": PRODUCTION_WEBHOOK_SECRET_HEADER,
                "value": webhook_secret,
            }
        )

    return {
        "agentId": agent_id,
        "locationId": location_id,
        "actionType": "CUSTOM_ACTION",
        "name": "book_appointment",
        "actionParameters": {
            "triggerPrompt": (
                "Use this action only after the caller "
                "has selected an appointment time that "
                "was returned by the ChairTime "
                "availability action and you have the "
                "customer's name and phone number. "
                "Never claim the appointment is booked "
                "until this action reports success."
            ),
            "triggerMessage": (
                "I'll book that for you now."
            ),
            "apiDetails": {
                "url": (
                    webhook_url
                    or tenant_booking_webhook_url(
                        shop
                    )
                ),
                "method": "POST",
                "authenticationRequired": False,
                "headers": headers,
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
                            "Selected appointment date "
                            "in YYYY-MM-DD format."
                        ),
                        "type": "string",
                        "example": "2026-09-10",
                    },
                    {
                        "name": "start_time",
                        "description": (
                            "Selected appointment start "
                            "time in 24-hour HH:MM format."
                        ),
                        "type": "string",
                        "example": "14:00",
                    },
                    {
                        "name": "customer_name",
                        "description": (
                            "Customer's full name."
                        ),
                        "type": "string",
                        "example": "John Smith",
                    },
                    {
                        "name": "customer_phone",
                        "description": (
                            "Customer's phone number."
                        ),
                        "type": "string",
                        "example": "2405551234",
                    },
                    {
                        "name": "barber_name",
                        "description": (
                            "Selected staff member. Use "
                            "No preference if ChairTime "
                            "should assign an available "
                            "provider."
                        ),
                        "type": "string",
                        "example": "No preference",
                    },
                ],
            },
        },
    }


def create_or_update_action(
    agent_id: str,
    location_id: str,
    action_name: str,
    payload: dict,
    expected_url: str,
) -> dict:
    agent_data = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    existing_action = find_action_by_name(
        agent_data=agent_data,
        action_name=action_name,
    )

    action_id = get_action_id(existing_action)

    if action_id:
        response = highlevel_raw_request(
            method="PUT",
            path=f"/voice-ai/actions/{action_id}",
            params={
                "locationId": location_id,
            },
            json_body=payload,
        )

        if response.status_code >= 400:
            response = highlevel_raw_request(
                method="PATCH",
                path=f"/voice-ai/actions/{action_id}",
                params={
                    "locationId": location_id,
                },
                json_body=payload,
            )

        if response.status_code >= 400:
            raise_highlevel_error(response)

        created = False

    else:
        response = highlevel_request(
            method="POST",
            path="/voice-ai/actions",
            json_body=payload,
        )

        action_data = response_json(response)

        action_id = get_action_id(action_data)

        if not action_id:
            refreshed_agent = get_agent_detail(
                agent_id=agent_id,
                location_id=location_id,
            )

            refreshed_action = find_action_by_name(
                agent_data=refreshed_agent,
                action_name=action_name,
            )

            action_id = get_action_id(
                refreshed_action
            )

        if not action_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "HighLevel created the Voice AI "
                    "action but did not return an "
                    "action ID."
                ),
            )

        created = True

    refreshed_agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    refreshed_action = find_action_by_name(
        agent_data=refreshed_agent,
        action_name=action_name,
    )

    if not refreshed_action:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel did not retain the "
                f"{action_name} action."
            ),
        )

    api_details = (
        refreshed_action
        .get("actionParameters", {})
        .get("apiDetails", {})
    )

    retained_url = str(
        api_details.get("url") or ""
    ).strip()

    if retained_url != expected_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel did not retain the expected "
                f"webhook URL for {action_name}."
            ),
        )

    return {
        "created_this_request": created,
        "action": safe_action(
            refreshed_action
        ),
    }


def extract_phone_numbers(data: dict) -> list:
    possible_lists = [
        data.get("numbers"),
        data.get("phoneNumbers"),
    ]

    nested_data = data.get("data")

    if isinstance(nested_data, dict):
        possible_lists.extend(
            [
                nested_data.get("numbers"),
                nested_data.get("phoneNumbers"),
            ]
        )

    for possible_list in possible_lists:
        if isinstance(possible_list, list):
            return [
                item
                for item in possible_list
                if isinstance(item, dict)
            ]

    return []


def get_location_phone_numbers(
    location_id: str,
) -> tuple[dict, list]:
    response = highlevel_request(
        method="GET",
        path=(
            f"/phone-system/numbers/location/"
            f"{location_id}"
        ),
        params={
            "page": 1,
            "pageSize": 100,
            "skipNumberPool": True,
        },
    )

    data = response_json(response)

    return data, extract_phone_numbers(data)


def get_phone_inbound_service(
    phone_record: dict,
) -> dict:
    inbound_service = phone_record.get(
        "inboundCallService"
    )

    if isinstance(inbound_service, dict):
        return inbound_service

    inbound_service = phone_record.get(
        "inbound_call_service"
    )

    if isinstance(inbound_service, dict):
        return inbound_service

    return {}


def get_phone_routed_agent_id(
    phone_record: dict,
) -> str:
    inbound_service = get_phone_inbound_service(
        phone_record
    )

    possible_ids = [
        inbound_service.get("agentId"),
        inbound_service.get("agent_id"),
        inbound_service.get("id"),
        phone_record.get("agentId"),
        phone_record.get("agent_id"),
    ]

    for possible_id in possible_ids:
        clean_id = str(
            possible_id or ""
        ).strip()

        if clean_id:
            return clean_id

    return ""


def find_phone_numbers_routed_to_agent(
    phone_numbers: list,
    agent_id: str,
) -> list:
    clean_agent_id = str(
        agent_id or ""
    ).strip()

    if not clean_agent_id:
        return []

    return [
        phone_record
        for phone_record in phone_numbers
        if get_phone_routed_agent_id(
            phone_record
        ) == clean_agent_id
    ]


def get_shop_routed_phone_record(
    shop: Shop,
) -> tuple[dict, list, Optional[dict]]:
    location_id = production_location_id(
        shop
    )

    highlevel_data, phone_numbers = (
        get_location_phone_numbers(
            location_id=location_id,
        )
    )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if not agent_id:
        return (
            highlevel_data,
            phone_numbers,
            None,
        )

    matches = (
        find_phone_numbers_routed_to_agent(
            phone_numbers=phone_numbers,
            agent_id=agent_id,
        )
    )

    if len(matches) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "More than one HighLevel phone number "
                "is routed to this shop's AI "
                "Receptionist."
            ),
        )

    return (
        highlevel_data,
        phone_numbers,
        matches[0] if matches else None,
    )


def sync_shop_phone_number_from_highlevel(
    shop: Shop,
    db: Session,
    require_match: bool = False,
) -> Optional[dict]:
    _, _, matched_phone = (
        get_shop_routed_phone_record(
            shop=shop,
        )
    )

    if matched_phone is None:
        if require_match:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "HighLevel does not currently show "
                    "a phone number routed to this "
                    "shop's AI Receptionist."
                ),
            )

        return None

    phone_number = str(
        matched_phone.get("phoneNumber")
        or matched_phone.get("number")
        or ""
    ).strip()

    if not phone_number:
        if require_match:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "HighLevel returned a routed phone "
                    "record without a phone number."
                ),
            )

        return None

    existing_phone = str(
        shop.highlevel_phone_number or ""
    ).strip()

    if existing_phone != phone_number:
        shop.highlevel_phone_number = (
            phone_number
        )

        try:
            db.commit()
            db.refresh(shop)

        except Exception:
            db.rollback()
            raise

    return matched_phone


def get_tenant_voice_payload(
    payload: dict,
) -> dict:
    if not isinstance(payload, dict):
        return {}

    nested_body = payload.get("body")

    if isinstance(nested_body, dict):
        return nested_body

    nested_data = payload.get("data")

    if isinstance(nested_data, dict):
        return nested_data

    return payload


async def read_highlevel_webhook_payload(
    request: Request,
) -> dict:
    try:
        payload = await request.json()

        if isinstance(payload, dict):
            return get_tenant_voice_payload(
                payload
            )

    except Exception:
        pass

    form_values = {}

    try:
        form = await request.form()

        form_values = {
            str(key): value
            for key, value in form.items()
        }

    except Exception:
        pass

    if form_values:
        return get_tenant_voice_payload(
            form_values
        )

    query_values = dict(
        request.query_params
    )

    return get_tenant_voice_payload(
        query_values
    )


def normalize_tenant_availability_request(
    values: dict,
) -> TenantAvailabilityRequest:
    decoded_values = decode_highlevel_fields(
        values
    )

    try:
        return TenantAvailabilityRequest(
            service_name=str(
                decoded_values.get(
                    "service_name",
                    "",
                )
            ).strip(),
            target_date=str(
                decoded_values.get(
                    "target_date",
                    "",
                )
            ).strip(),
            barber_name=normalize_barber_name(
                decoded_values.get(
                    "barber_name"
                )
            ),
            time_window=(
                str(
                    decoded_values.get(
                        "time_window",
                        "",
                    )
                ).strip()
                or None
            ),
            preferred_start_time=(
                str(
                    decoded_values.get(
                        "preferred_start_time",
                        "",
                    )
                ).strip()
                or None
            ),
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid availability request."
            ),
        )


def normalize_tenant_booking_request(
    values: dict,
) -> TenantBookingRequest:
    decoded_values = decode_highlevel_fields(
        values
    )

    try:
        return TenantBookingRequest(
            service_name=str(
                decoded_values.get(
                    "service_name",
                    "",
                )
            ).strip(),
            target_date=str(
                decoded_values.get(
                    "target_date",
                    "",
                )
            ).strip(),
            start_time=str(
                decoded_values.get(
                    "start_time",
                    "",
                )
            ).strip(),
            customer_name=str(
                decoded_values.get(
                    "customer_name",
                    "",
                )
            ).strip(),
            customer_phone=str(
                decoded_values.get(
                    "customer_phone",
                    "",
                )
            ).strip(),
            barber_name=normalize_barber_name(
                decoded_values.get(
                    "barber_name"
                )
            ),
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid booking request.",
        )


def validate_tenant_availability_request(
    payload: TenantAvailabilityRequest,
) -> None:
    missing = []

    if not payload.service_name:
        missing.append("service_name")

    if not payload.target_date:
        missing.append("target_date")

    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Missing required availability fields: "
                + ", ".join(missing)
            ),
        )


def validate_tenant_booking_request(
    payload: TenantBookingRequest,
) -> None:
    missing = []

    if not payload.service_name:
        missing.append("service_name")

    if not payload.target_date:
        missing.append("target_date")

    if not payload.start_time:
        missing.append("start_time")

    if not payload.customer_name:
        missing.append("customer_name")

    if not payload.customer_phone:
        missing.append("customer_phone")

    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Missing required booking fields: "
                + ", ".join(missing)
            ),
        )


def chairtime_availability_payload(
    shop: Shop,
    payload: TenantAvailabilityRequest,
) -> dict:
    return {
        "shop_slug": shop.slug,
        "service_name": payload.service_name,
        "target_date": payload.target_date,
        "barber_name": payload.barber_name,
        "time_window": payload.time_window,
        "preferred_start_time": (
            payload.preferred_start_time
        ),
    }


def chairtime_booking_payload(
    shop: Shop,
    payload: TenantBookingRequest,
) -> dict:
    return {
        "shop_slug": shop.slug,
        "service_name": payload.service_name,
        "target_date": payload.target_date,
        "start_time": payload.start_time,
        "customer_name": payload.customer_name,
        "customer_phone": payload.customer_phone,
        "barber_name": payload.barber_name,
    }


@router.post(
    "/webhook/{shop_slug}/availability"
)
async def tenant_availability_webhook(
    shop_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    shop = get_shop_by_slug(
        shop_slug=shop_slug,
        db=db,
    )

    values = (
        await read_highlevel_webhook_payload(
            request
        )
    )

    payload = (
        normalize_tenant_availability_request(
            values
        )
    )

    validate_tenant_availability_request(
        payload
    )

    return chairtime_voice_request(
        url=CHAIRTIME_AVAILABILITY_URL,
        payload=chairtime_availability_payload(
            shop=shop,
            payload=payload,
        ),
    )


@router.post(
    "/webhook/{shop_slug}/book"
)
async def tenant_booking_webhook(
    shop_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    shop = get_shop_by_slug(
        shop_slug=shop_slug,
        db=db,
    )

    values = (
        await read_highlevel_webhook_payload(
            request
        )
    )

    payload = (
        normalize_tenant_booking_request(
            values
        )
    )

    validate_tenant_booking_request(
        payload
    )

    return chairtime_voice_request(
        url=CHAIRTIME_BOOKING_URL,
        payload=chairtime_booking_payload(
            shop=shop,
            payload=payload,
        ),
    )


@router.post(
    "/tenant-webhook/{shop_slug}/availability"
)
async def production_tenant_availability_webhook(
    shop_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    shop = get_shop_by_slug(
        shop_slug=shop_slug,
        db=db,
    )

    verify_production_webhook_secret(
        shop=shop,
        request=request,
    )

    values = (
        await read_highlevel_webhook_payload(
            request
        )
    )

    payload = (
        normalize_tenant_availability_request(
            values
        )
    )

    validate_tenant_availability_request(
        payload
    )

    return chairtime_voice_request(
        url=CHAIRTIME_AVAILABILITY_URL,
        payload=chairtime_availability_payload(
            shop=shop,
            payload=payload,
        ),
    )


@router.post(
    "/tenant-webhook/{shop_slug}/book"
)
async def production_tenant_booking_webhook(
    shop_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    shop = get_shop_by_slug(
        shop_slug=shop_slug,
        db=db,
    )

    verify_production_webhook_secret(
        shop=shop,
        request=request,
    )

    values = (
        await read_highlevel_webhook_payload(
            request
        )
    )

    payload = (
        normalize_tenant_booking_request(
            values
        )
    )

    validate_tenant_booking_request(
        payload
    )

    return chairtime_voice_request(
        url=CHAIRTIME_BOOKING_URL,
        payload=chairtime_booking_payload(
            shop=shop,
            payload=payload,
        ),
    )

@router.get("/agents")
def list_voice_agents(
    current_user: User = Depends(
        get_current_user
    ),
):
    require_owner(current_user)

    location_id = get_highlevel_location_id()

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

    return {
        "location_id": location_id,
        "agents": [
            safe_agent_summary(agent)
            for agent in extract_agents(data)
        ],
    }


@router.get("/agents/{agent_id}")
def get_voice_agent(
    agent_id: str,
    current_user: User = Depends(
        get_current_user
    ),
):
    require_owner(current_user)

    location_id = get_highlevel_location_id()

    agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    return {
        "location_id": location_id,
        "agent": safe_agent_summary(agent),
        "actions": [
            safe_action(action)
            for action in extract_actions(agent)
        ],
    }


@router.get("/actions/{action_id}")
def get_voice_action(
    action_id: str,
    current_user: User = Depends(
        get_current_user
    ),
):
    require_owner(current_user)

    location_id = get_highlevel_location_id()

    response = highlevel_request(
        method="GET",
        path=f"/voice-ai/actions/{action_id}",
        params={
            "locationId": location_id,
        },
    )

    data = response_json(response)

    return {
        "location_id": location_id,
        "action": safe_action(data),
        "raw_action": data,
    }


@router.get("/provision/status")
def get_production_provision_status(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    location_id = production_location_id(
        shop
    )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if not agent_id:
        return {
            "shop_id": shop.id,
            "shop_slug": shop.slug,
            "location_id": location_id,
            "provisioned": False,
            "agent_id": None,
            "availability_action": None,
            "booking_action": None,
        }

    agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    availability_action = (
        find_action_by_name(
            agent_data=agent,
            action_name="check_availability",
        )
    )

    booking_action = (
        find_action_by_name(
            agent_data=agent,
            action_name="book_appointment",
        )
    )

    return {
        "shop_id": shop.id,
        "shop_slug": shop.slug,
        "location_id": location_id,
        "provisioned": bool(
            availability_action
            and booking_action
        ),
        "agent": safe_agent_summary(
            agent
        ),
        "availability_action": (
            safe_action(
                availability_action
            )
            if availability_action
            else None
        ),
        "booking_action": (
            safe_action(
                booking_action
            )
            if booking_action
            else None
        ),
    }


@router.post("/provision")
def provision_production_ai_receptionist(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not bool(shop.ai_voice_enabled):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "AI Receptionist is not enabled "
                "for this shop."
            ),
        )

    location_id = production_location_id(
        shop
    )

    webhook_secret = (
        ensure_shop_webhook_secret(
            shop=shop,
            db=db,
        )
    )

    agent, agent_created = (
        get_or_create_production_agent(
            shop=shop,
            location_id=location_id,
            db=db,
        )
    )

    agent_id = str(
        agent.get("id")
        or agent.get("_id")
        or shop.highlevel_agent_id
        or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel did not return the "
                "shop AI agent ID."
            ),
        )

    refreshed_agent = (
        update_production_agent_settings(
            shop=shop,
            agent_id=agent_id,
            location_id=location_id,
        )
    )

    availability_url = (
        production_availability_webhook_url(
            shop
        )
    )

    booking_url = (
        production_booking_webhook_url(
            shop
        )
    )

    availability_result = (
        create_or_update_action(
            agent_id=agent_id,
            location_id=location_id,
            action_name="check_availability",
            payload=(
                build_availability_action_payload(
                    shop=shop,
                    agent_id=agent_id,
                    location_id=location_id,
                    webhook_url=availability_url,
                    webhook_secret=webhook_secret,
                )
            ),
            expected_url=availability_url,
        )
    )

    booking_result = (
        create_or_update_action(
            agent_id=agent_id,
            location_id=location_id,
            action_name="book_appointment",
            payload=(
                build_booking_action_payload(
                    shop=shop,
                    agent_id=agent_id,
                    location_id=location_id,
                    webhook_url=booking_url,
                    webhook_secret=webhook_secret,
                )
            ),
            expected_url=booking_url,
        )
    )

    return {
        "success": True,
        "shop_id": shop.id,
        "shop_slug": shop.slug,
        "location_id": location_id,
        "agent_created_this_request": (
            agent_created
        ),
        "agent": safe_agent_summary(
            refreshed_agent
        ),
        "availability_action": (
            availability_result
        ),
        "booking_action": booking_result,
    }


@router.post(
    "/provisioning-test/availability"
)
def provision_tenant_safe_availability(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    location_id = get_highlevel_location_id()

    agent, agent_created = (
        get_or_create_test_agent(
            shop=shop,
            location_id=location_id,
        )
    )

    agent_id = str(
        agent.get("id")
        or agent.get("_id")
        or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel did not return the "
                "test agent ID."
            ),
        )

    update_test_agent_settings(
        agent_id=agent_id,
        location_id=location_id,
    )

    webhook_url = (
        tenant_availability_webhook_url(
            shop
        )
    )

    result = create_or_update_action(
        agent_id=agent_id,
        location_id=location_id,
        action_name="check_availability",
        payload=(
            build_availability_action_payload(
                shop=shop,
                agent_id=agent_id,
                location_id=location_id,
            )
        ),
        expected_url=webhook_url,
    )

    return {
        "success": True,
        "location_id": location_id,
        "agent_created_this_request": (
            agent_created
        ),
        "agent_id": agent_id,
        "webhook_url": webhook_url,
        **result,
    }


@router.post(
    "/provisioning-test/booking"
)
def provision_tenant_safe_booking(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    location_id = get_highlevel_location_id()

    agent, agent_created = (
        get_or_create_test_agent(
            shop=shop,
            location_id=location_id,
        )
    )

    agent_id = str(
        agent.get("id")
        or agent.get("_id")
        or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel did not return the "
                "test agent ID."
            ),
        )

    update_test_agent_settings(
        agent_id=agent_id,
        location_id=location_id,
    )

    webhook_url = (
        tenant_booking_webhook_url(
            shop
        )
    )

    result = create_or_update_action(
        agent_id=agent_id,
        location_id=location_id,
        action_name="book_appointment",
        payload=(
            build_booking_action_payload(
                shop=shop,
                agent_id=agent_id,
                location_id=location_id,
            )
        ),
        expected_url=webhook_url,
    )

    return {
        "success": True,
        "location_id": location_id,
        "agent_created_this_request": (
            agent_created
        ),
        "agent_id": agent_id,
        "webhook_url": webhook_url,
        **result,
    }


@router.post(
    "/provisioning-test/full"
)
def provision_tenant_safe_voice_test(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    location_id = get_highlevel_location_id()

    agent, agent_created = (
        get_or_create_test_agent(
            shop=shop,
            location_id=location_id,
        )
    )

    agent_id = str(
        agent.get("id")
        or agent.get("_id")
        or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel did not return the "
                "test agent ID."
            ),
        )

    refreshed_agent = (
        update_test_agent_settings(
            agent_id=agent_id,
            location_id=location_id,
        )
    )

    availability_url = (
        tenant_availability_webhook_url(
            shop
        )
    )

    booking_url = (
        tenant_booking_webhook_url(
            shop
        )
    )

    availability_result = (
        create_or_update_action(
            agent_id=agent_id,
            location_id=location_id,
            action_name="check_availability",
            payload=(
                build_availability_action_payload(
                    shop=shop,
                    agent_id=agent_id,
                    location_id=location_id,
                )
            ),
            expected_url=availability_url,
        )
    )

    booking_result = (
        create_or_update_action(
            agent_id=agent_id,
            location_id=location_id,
            action_name="book_appointment",
            payload=(
                build_booking_action_payload(
                    shop=shop,
                    agent_id=agent_id,
                    location_id=location_id,
                )
            ),
            expected_url=booking_url,
        )
    )

    return {
        "success": True,
        "location_id": location_id,
        "agent_created_this_request": (
            agent_created
        ),
        "agent": safe_agent_summary(
            refreshed_agent
        ),
        "availability_action": (
            availability_result
        ),
        "booking_action": booking_result,
    }


@router.get("/phone-numbers")
def get_shop_highlevel_phone_numbers(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    location_id = production_location_id(
        shop
    )

    highlevel_data, phone_numbers = (
        get_location_phone_numbers(
            location_id=location_id,
        )
    )

    return {
        "success": True,
        "chairtime_shop": {
            "id": shop.id,
            "slug": shop.slug,
            "name": shop.name,
            "stored_phone_number": (
                shop.highlevel_phone_number
            ),
            "highlevel_agent_id": (
                shop.highlevel_agent_id
            ),
        },
        "location_id": location_id,
        "count": len(phone_numbers),
        "phone_numbers": phone_numbers,
        "highlevel_response": highlevel_data,
    }


@router.post("/phone-number/sync")
def sync_shop_highlevel_phone_number(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not str(
        shop.highlevel_agent_id or ""
    ).strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This shop does not have a "
                "HighLevel AI agent yet."
            ),
        )

    matched_phone = (
        sync_shop_phone_number_from_highlevel(
            shop=shop,
            db=db,
            require_match=True,
        )
    )

    return {
        "success": True,
        "chairtime_shop": {
            "id": shop.id,
            "slug": shop.slug,
            "name": shop.name,
            "highlevel_phone_number": (
                shop.highlevel_phone_number
            ),
            "highlevel_agent_id": (
                shop.highlevel_agent_id
            ),
        },
        "location_id": (
            production_location_id(shop)
        ),
        "matched_phone_record": matched_phone,
    }


class AssignShopPhoneNumberRequest(
    BaseModel
):
    phone_number: str


class PurchaseShopPhoneNumberRequest(
    BaseModel
):
    phone_number: str


def normalize_phone_number(
    phone_number: str,
) -> str:
    return (
        str(phone_number or "")
        .strip()
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )


def phone_record_number(
    phone_record: dict,
) -> str:
    return normalize_phone_number(
        str(
            phone_record.get("phoneNumber")
            or phone_record.get("number")
            or ""
        )
    )


def find_phone_record_by_number(
    phone_numbers: list,
    phone_number: str,
) -> Optional[dict]:
    target = normalize_phone_number(
        phone_number
    )

    for phone_record in phone_numbers:
        if (
            phone_record_number(
                phone_record
            )
            == target
        ):
            return phone_record

    return None


def get_phone_record_id(
    phone_record: dict,
) -> str:
    possible_ids = [
        phone_record.get("_id"),
        phone_record.get("id"),
        phone_record.get("phoneNumberId"),
        phone_record.get("phone_number_id"),
        phone_record.get("sid"),
    ]

    for possible_id in possible_ids:
        clean_id = str(
            possible_id or ""
        ).strip()

        if clean_id:
            return clean_id

    return ""


def highlevel_phone_host() -> str:
    configured_host = str(
        os.getenv(
            "HIGHLEVEL_PHONE_API_BASE_URL",
            "",
        )
        or ""
    ).strip()

    if configured_host:
        return configured_host.rstrip("/")

    return HIGHLEVEL_API_BASE_URL


def highlevel_internal_phone_host() -> str:
    configured_host = str(
        os.getenv(
            "HIGHLEVEL_INTERNAL_PHONE_API_BASE_URL",
            "",
        )
        or ""
    ).strip()

    if configured_host:
        return configured_host.rstrip("/")

    return "https://backend.leadconnectorhq.com"


def highlevel_internal_phone_headers() -> dict:
    access_token = str(
        os.getenv(
            "HIGHLEVEL_INTERNAL_ACCESS_TOKEN",
            "",
        )
        or ""
    ).strip()

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "HIGHLEVEL_INTERNAL_ACCESS_TOKEN "
                "environment variable is missing."
            ),
        )

    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ChairTime/1.0",
        "token-id": access_token,
    }


def highlevel_internal_phone_request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
) -> requests.Response:
    try:
        return requests.request(
            method=method,
            url=(
                f"{highlevel_internal_phone_host()}"
                f"{path}"
            ),
            headers=(
                highlevel_internal_phone_headers()
            ),
            params=params,
            json=json_body,
            timeout=30,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Could not connect to the HighLevel "
                "internal phone service."
            ),
        )


def highlevel_phone_request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
    timeout: int = 30,
) -> requests.Response:
    try:
        return requests.request(
            method=method,
            url=f"{highlevel_phone_host()}{path}",
            headers=highlevel_voice_headers(),
            params=params,
            json=json_body,
            timeout=timeout,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Could not connect to the HighLevel "
                "phone service."
            ),
        )


def highlevel_phone_purchase_request(
    method: str,
    path: str,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
    timeout: int = 45,
) -> requests.Response:
    try:
        return requests.request(
            method=method,
            url=f"{highlevel_phone_host()}{path}",
            headers=(
                highlevel_phone_purchase_headers()
            ),
            params=params,
            json=json_body,
            timeout=timeout,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Could not connect to the HighLevel "
                "phone purchase service."
            ),
        )


def safe_response_text(
    response: requests.Response,
    max_length: int = 2000,
) -> str:
    try:
        return str(response.text or "")[
            :max_length
        ]

    except Exception:
        return ""


def response_body_for_log(
    response: requests.Response,
):
    try:
        return response.json()

    except ValueError:
        return safe_response_text(response)


def get_response_request_id(
    response: requests.Response,
) -> Optional[str]:
    possible_headers = [
        "traceid",
        "trace-id",
        "trace_id",
        "x-trace-id",
        "request-id",
        "requestid",
        "x-request-id",
        "x-correlation-id",
        "cf-ray",
    ]

    lower_headers = {
        str(key).lower(): str(value)
        for key, value
        in response.headers.items()
    }

    for header_name in possible_headers:
        value = lower_headers.get(
            header_name
        )

        if value:
            return value

    try:
        body = response.json()

    except ValueError:
        return None

    if not isinstance(body, dict):
        return None

    possible_body_keys = [
        "traceId",
        "traceID",
        "trace_id",
        "requestId",
        "requestID",
        "request_id",
    ]

    for key in possible_body_keys:
        value = body.get(key)

        if value:
            return str(value)

    return None

def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def safe_response_headers(
    response: requests.Response,
) -> dict:
    """
    Return response headers that are useful for HighLevel
    support diagnostics.

    Response headers do not contain our bearer token, but
    we still exclude cookie-related headers defensively.
    """
    excluded_headers = {
        "set-cookie",
        "cookie",
        "authorization",
        "proxy-authorization",
    }

    return {
        str(key): str(value)
        for key, value in response.headers.items()
        if str(key).lower()
        not in excluded_headers
    }


def diagnostic_request_headers() -> dict:
    """
    Return the headers sent to HighLevel with the secret
    Authorization value removed.
    """
    headers = (
        highlevel_phone_purchase_headers()
        .copy()
    )

    headers.pop("Authorization", None)

    return headers


def shell_single_quote(value: str) -> str:
    """
    Safely represent a value inside single quotes in the
    sanitized cURL generated for HighLevel support.
    """
    return str(value).replace(
        "'",
        "'\"'\"'",
    )


def sanitized_purchase_curl(
    url: str,
    json_body: dict,
) -> str:
    """
    Generate a support-safe cURL representation of the
    HighLevel request.

    The real access token is intentionally never included.
    """
    headers = diagnostic_request_headers()

    body_text = json.dumps(
        json_body,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    lines = [
        "curl --request POST \\",
        f"  --url '{shell_single_quote(url)}' \\",
        (
            "  --header "
            "'Authorization: Bearer [REDACTED]' \\"
        ),
    ]

    header_items = list(
        headers.items()
    )

    for index, (key, value) in enumerate(
        header_items
    ):
        suffix = " \\"

        lines.append(
            "  --header "
            f"'{shell_single_quote(key)}: "
            f"{shell_single_quote(value)}'"
            f"{suffix}"
        )

    lines.append(
        "  --data "
        f"'{shell_single_quote(body_text)}'"
    )

    return "\n".join(lines)


def diagnostic_trace_values(
    response: requests.Response,
) -> dict:
    """
    Collect likely request/trace identifiers without
    assuming which header HighLevel's LC service uses.
    """
    interesting_names = {
        "traceid",
        "trace-id",
        "trace_id",
        "x-trace-id",
        "request-id",
        "requestid",
        "x-request-id",
        "x-correlation-id",
        "cf-ray",
    }

    values = {}

    for key, value in response.headers.items():
        if str(key).lower() in interesting_names:
            values[str(key)] = str(value)

    try:
        body = response.json()

    except ValueError:
        body = None

    if isinstance(body, dict):
        for key in [
            "traceId",
            "traceID",
            "trace_id",
            "requestId",
            "requestID",
            "request_id",
        ]:
            value = body.get(key)

            if value:
                values[key] = str(value)

    return values


def phone_number_from_available_record(
    record: dict,
) -> str:
    possible_values = [
        record.get("phoneNumber"),
        record.get("phone_number"),
        record.get("number"),
        record.get("phone"),
    ]

    for possible_value in possible_values:
        clean_value = normalize_phone_number(
            str(possible_value or "")
        )

        if clean_value:
            return clean_value

    return ""


def available_number_locality(
    record: dict,
) -> Optional[str]:
    possible_values = [
        record.get("locality"),
        record.get("city"),
        record.get("rateCenter"),
        record.get("rate_center"),
    ]

    for possible_value in possible_values:
        clean_value = str(
            possible_value or ""
        ).strip()

        if clean_value:
            return clean_value

    return None


def available_number_region(
    record: dict,
) -> Optional[str]:
    possible_values = [
        record.get("region"),
        record.get("state"),
        record.get("province"),
    ]

    for possible_value in possible_values:
        clean_value = str(
            possible_value or ""
        ).strip()

        if clean_value:
            return clean_value

    return None


def extract_available_phone_records(
    data,
) -> list:
    """
    HighLevel has returned available-number inventory in
    more than one envelope shape over time. Accept only
    dictionaries that contain an actual phone number.
    """
    possible_lists = []

    if isinstance(data, list):
        possible_lists.append(data)

    if isinstance(data, dict):
        for key in [
            "numbers",
            "phoneNumbers",
            "availableNumbers",
            "available_numbers",
        ]:
            value = data.get(key)

            if isinstance(value, list):
                possible_lists.append(value)

        nested_data = data.get("data")

        if isinstance(nested_data, list):
            possible_lists.append(
                nested_data
            )

        elif isinstance(nested_data, dict):
            for key in [
                "numbers",
                "phoneNumbers",
                "availableNumbers",
                "available_numbers",
            ]:
                value = nested_data.get(key)

                if isinstance(value, list):
                    possible_lists.append(
                        value
                    )

    for possible_list in possible_lists:
        records = [
            record
            for record in possible_list
            if (
                isinstance(record, dict)
                and phone_number_from_available_record(
                    record
                )
            )
        ]

        if records:
            return records

    return []


def available_phone_search_attempts(
    location_id: str,
    area_code: str,
) -> list:
    """
    Return the supported search variants already used by
    ChairTime. The first successful response containing
    inventory wins.
    """
    clean_area_code = str(
        area_code or ""
    ).strip()

    return [
        {
            "method": "GET",
            "path": (
                "/phone-system/numbers/"
                "available-numbers"
            ),
            "params": {
                "locationId": location_id,
                "countryCode": "US",
                "areaCode": clean_area_code,
                "limit": 10,
            },
        },
        {
            "method": "GET",
            "path": (
                "/phone-system/numbers/"
                "location/"
                f"{location_id}/available"
            ),
            "params": {
                "countryCode": "US",
                "areaCode": clean_area_code,
                "limit": 10,
            },
        },
        {
            "method": "GET",
            "path": (
                "/phone-system/numbers/"
                "location/"
                f"{location_id}/available-numbers"
            ),
            "params": {
                "countryCode": "US",
                "areaCode": clean_area_code,
                "limit": 10,
            },
        },
    ]


def search_available_phone_numbers(
    location_id: str,
    area_code: str,
) -> tuple[list, dict]:
    """
    Search HighLevel's current inventory.

    Returns:
        (records, metadata)

    Metadata identifies the exact successful HighLevel
    search request so the support diagnostic can prove
    which inventory call immediately preceded purchase.
    """
    attempts = (
        available_phone_search_attempts(
            location_id=location_id,
            area_code=area_code,
        )
    )

    failures = []

    for attempt in attempts:
        search_started_at = (
            utc_now_iso()
        )

        response = highlevel_phone_request(
            method=attempt["method"],
            path=attempt["path"],
            params=attempt["params"],
            timeout=30,
        )

        search_completed_at = (
            utc_now_iso()
        )

        response_body = (
            response_body_for_log(
                response
            )
        )

        records = []

        if response.status_code < 400:
            records = (
                extract_available_phone_records(
                    response_body
                )
            )

        if records:
            return (
                records,
                {
                    "search_started_at_utc": (
                        search_started_at
                    ),
                    "search_completed_at_utc": (
                        search_completed_at
                    ),
                    "method": (
                        attempt["method"]
                    ),
                    "url": (
                        f"{highlevel_phone_host()}"
                        f"{attempt['path']}"
                    ),
                    "params": (
                        attempt["params"]
                    ),
                    "highlevel_status": (
                        response.status_code
                    ),
                    "trace_values": (
                        diagnostic_trace_values(
                            response
                        )
                    ),
                    "response_headers": (
                        safe_response_headers(
                            response
                        )
                    ),
                },
            )

        failures.append(
            {
                "method": attempt["method"],
                "path": attempt["path"],
                "params": attempt["params"],
                "highlevel_status": (
                    response.status_code
                ),
                "highlevel_response": (
                    response_body
                ),
                "trace_values": (
                    diagnostic_trace_values(
                        response
                    )
                ),
            }
        )

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={
            "message": (
                "HighLevel did not return any "
                "available phone numbers."
            ),
            "search_attempts": failures,
        },
    )


def get_phone_purchase_billing_values() -> dict:
    """
    Load the same purchase/billing values used by the
    existing ChairTime phone-number purchase workflow.

    These values are never returned by the diagnostic
    endpoint. Only boolean presence indicators are
    exposed to support.
    """
    stripe_account_id = str(
        os.getenv(
            "HIGHLEVEL_PHONE_STRIPE_ACCOUNT_ID",
            "",
        )
        or ""
    ).strip()

    payment_method_id = str(
        os.getenv(
            "HIGHLEVEL_PHONE_PAYMENT_METHOD_ID",
            "",
        )
        or ""
    ).strip()

    fingerprint_id = str(
        os.getenv(
            "HIGHLEVEL_PHONE_FINGERPRINT_ID",
            "",
        )
        or ""
    ).strip()

    return {
        "stripe_account_id": (
            stripe_account_id
        ),
        "payment_method_id": (
            payment_method_id
        ),
        "fingerprint_id": fingerprint_id,
    }


def build_phone_purchase_payload(
    phone_number: str,
    available_record: dict,
) -> dict:
    """
    Build the purchase payload using the fields currently
    required by ChairTime's HighLevel purchase workflow.
    """
    billing_values = (
        get_phone_purchase_billing_values()
    )

    locality = (
        available_number_locality(
            available_record
        )
        or ""
    )

    region = (
        available_number_region(
            available_record
        )
        or ""
    )

    return {
        "phoneNumber": normalize_phone_number(
            phone_number
        ),
        "stripeAccountId": (
            billing_values[
                "stripe_account_id"
            ]
        ),
        "paymentMethodId": (
            billing_values[
                "payment_method_id"
            ]
        ),
        "locality": locality,
        "region": region,
        "fingerprintId": (
            billing_values[
                "fingerprint_id"
            ]
        ),
        "skipLocationKYC": True,
        "addressSid": "",
        "bundleSid": "",
    }


def sanitized_purchase_payload(
    purchase_payload: dict,
) -> dict:
    """
    Produce the JSON body HighLevel support can inspect
    without disclosing payment identifiers.
    """
    safe_payload = dict(
        purchase_payload
    )

    for key in [
        "stripeAccountId",
        "paymentMethodId",
        "fingerprintId",
    ]:
        original_value = str(
            safe_payload.get(key) or ""
        ).strip()

        safe_payload[key] = (
            "[REDACTED]"
            if original_value
            else ""
        )

    return safe_payload


def phone_exists_in_location(
    location_id: str,
    phone_number: str,
) -> tuple[bool, Optional[dict]]:
    """
    Check the location after the purchase request to
    determine whether HighLevel actually added the number
    despite an error/timeout response.
    """
    try:
        _, phone_numbers = (
            get_location_phone_numbers(
                location_id=location_id,
            )
        )

    except HTTPException:
        return False, None

    record = find_phone_record_by_number(
        phone_numbers=phone_numbers,
        phone_number=phone_number,
    )

    return (
        record is not None,
        record,
    )


@router.get(
    "/phone-numbers/available"
)
def get_available_highlevel_phone_numbers(
    area_code: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not bool(shop.ai_voice_enabled):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "AI Receptionist is not enabled "
                "for this shop."
            ),
        )

    clean_area_code = str(
        area_code or ""
    ).strip()

    if (
        len(clean_area_code) != 3
        or not clean_area_code.isdigit()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "area_code must be a "
                "3-digit U.S. area code."
            ),
        )

    location_id = production_location_id(
        shop
    )

    records, _ = (
        search_available_phone_numbers(
            location_id=location_id,
            area_code=clean_area_code,
        )
    )

    available_numbers = []

    for record in records[:10]:
        phone_number = (
            phone_number_from_available_record(
                record
            )
        )

        if not phone_number:
            continue

        capabilities = (
            record.get("capabilities")
            if isinstance(
                record.get("capabilities"),
                dict,
            )
            else {}
        )

        available_numbers.append(
            {
                "phone_number": phone_number,
                "friendly_name": (
                    record.get(
                        "friendlyName"
                    )
                    or record.get(
                        "friendly_name"
                    )
                    or phone_number
                ),
                "locality": (
                    available_number_locality(
                        record
                    )
                ),
                "region": (
                    available_number_region(
                        record
                    )
                ),
                "capabilities": (
                    capabilities
                ),
            }
        )

    return {
        "success": True,
        "chairtime_shop": {
            "id": shop.id,
            "slug": shop.slug,
            "name": shop.name,
        },
        "area_code": clean_area_code,
        "location_id": location_id,
        "count": len(
            available_numbers
        ),
        "available_numbers": (
            available_numbers
        ),
    }


@router.post(
    "/phone-number/support-diagnostic"
)
def run_phone_purchase_support_diagnostic(
    area_code: str = "240",
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    ONE-SHOT HighLevel support diagnostic.

    This endpoint:
      1. Searches live HighLevel inventory.
      2. Selects the first number returned.
      3. Immediately purchases that exact number.
      4. Captures timestamps, sanitized request details,
         response headers/body, and trace IDs.
      5. Checks whether the number was actually added.

    It NEVER retries with a second phone number.

    If the purchase unexpectedly succeeds, the number
    may incur HighLevel's normal phone-number charge.
    """
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not bool(shop.ai_voice_enabled):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "AI Receptionist is not enabled "
                "for this shop."
            ),
        )

    clean_area_code = str(
        area_code or ""
    ).strip()

    if (
        len(clean_area_code) != 3
        or not clean_area_code.isdigit()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "area_code must be a "
                "3-digit U.S. area code."
            ),
        )

    location_id = production_location_id(
        shop
    )

    diagnostic_started_at = (
        utc_now_iso()
    )

    available_records, search_metadata = (
        search_available_phone_numbers(
            location_id=location_id,
            area_code=clean_area_code,
        )
    )

    selected_record = (
        available_records[0]
    )

    selected_phone_number = (
        phone_number_from_available_record(
            selected_record
        )
    )

    if not selected_phone_number:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel returned an available "
                "number without a phone number."
            ),
        )

    purchase_path = (
        "/phone-system/numbers/location/"
        f"{location_id}/purchase"
    )

    purchase_url = (
        f"{highlevel_phone_host()}"
        f"{purchase_path}"
    )

    purchase_payload = (
        build_phone_purchase_payload(
            phone_number=(
                selected_phone_number
            ),
            available_record=(
                selected_record
            ),
        )
    )

    safe_payload = (
        sanitized_purchase_payload(
            purchase_payload
        )
    )

    purchase_started_at = (
        utc_now_iso()
    )

    logger.warning(
        "HighLevel support diagnostic purchase "
        "starting: location_id=%s "
        "phone_number=%s "
        "utc=%s",
        location_id,
        selected_phone_number,
        purchase_started_at,
    )

    purchase_response = (
        highlevel_phone_purchase_request(
            method="POST",
            path=purchase_path,
            json_body=purchase_payload,
            timeout=45,
        )
    )

    purchase_completed_at = (
        utc_now_iso()
    )

    raw_response = (
        response_body_for_log(
            purchase_response
        )
    )

    trace_values = (
        diagnostic_trace_values(
            purchase_response
        )
    )

    response_headers = (
        safe_response_headers(
            purchase_response
        )
    )

    logger.warning(
        "HighLevel support diagnostic purchase "
        "completed: location_id=%s "
        "phone_number=%s "
        "status=%s "
        "utc=%s "
        "trace_values=%s "
        "response=%s",
        location_id,
        selected_phone_number,
        purchase_response.status_code,
        purchase_completed_at,
        trace_values,
        raw_response,
    )

    # Give HighLevel a very short opportunity to reflect
    # a successful purchase in the location before the
    # verification read. This does not retry the purchase.
    time.sleep(2)

    number_added_to_location, added_record = (
        phone_exists_in_location(
            location_id=location_id,
            phone_number=(
                selected_phone_number
            ),
        )
    )

    diagnostic_completed_at = (
        utc_now_iso()
    )

    billing_values = (
        get_phone_purchase_billing_values()
    )

    return {
        "success": (
            purchase_response.status_code
            < 400
        ),
        "diagnostic": (
            "HighLevel LC Phone purchase "
            "support diagnostic"
        ),
        "chairtime_shop": {
            "id": shop.id,
            "slug": shop.slug,
            "name": shop.name,
        },
        "location_id": location_id,
        "area_code": clean_area_code,
        "selected_number": (
            selected_phone_number
        ),
        "selected_number_was_returned_by_"
        "immediate_search": True,
        "number_added_to_location": (
            number_added_to_location
        ),
        "timestamps": {
            "diagnostic_started_at_utc": (
                diagnostic_started_at
            ),
            "search_started_at_utc": (
                search_metadata.get(
                    "search_started_at_utc"
                )
            ),
            "search_completed_at_utc": (
                search_metadata.get(
                    "search_completed_at_utc"
                )
            ),
            "purchase_started_at_utc": (
                purchase_started_at
            ),
            "purchase_completed_at_utc": (
                purchase_completed_at
            ),
            "diagnostic_completed_at_utc": (
                diagnostic_completed_at
            ),
        },
        "availability_search": {
            "method": (
                search_metadata.get(
                    "method"
                )
            ),
            "url": (
                search_metadata.get(
                    "url"
                )
            ),
            "params": (
                search_metadata.get(
                    "params"
                )
            ),
            "highlevel_status": (
                search_metadata.get(
                    "highlevel_status"
                )
            ),
            "trace_values": (
                search_metadata.get(
                    "trace_values"
                )
            ),
        },
        "purchase_request": {
            "method": "POST",
            "url": purchase_url,
            "version": "v3",
            "headers": (
                diagnostic_request_headers()
            ),
            "authorization": (
                "Bearer [REDACTED]"
            ),
            "json_body": safe_payload,
            "billing_values_present": {
                "stripe_account_id": bool(
                    billing_values[
                        "stripe_account_id"
                    ]
                ),
                "payment_method_id": bool(
                    billing_values[
                        "payment_method_id"
                    ]
                ),
                "fingerprint_id": bool(
                    billing_values[
                        "fingerprint_id"
                    ]
                ),
            },
            "sanitized_curl": (
                sanitized_purchase_curl(
                    url=purchase_url,
                    json_body=safe_payload,
                )
            ),
        },
        "purchase_response": {
            "http_status": (
                purchase_response.status_code
            ),
            "trace_or_request_id": (
                get_response_request_id(
                    purchase_response
                )
            ),
            "trace_values": trace_values,
            "headers": response_headers,
            "raw_body": raw_response,
        },
        "post_purchase_verification": {
            "number_added_to_location": (
                number_added_to_location
            ),
            "matched_phone_record": (
                added_record
                if number_added_to_location
                else None
            ),
        },
        "support_confirmations": {
            "version_v3_used": True,
            "number_returned_by_search_"
            "immediately_before_purchase": (
                True
            ),
            "purchase_retried": False,
            "replacement_number_used": False,
            "access_token_redacted": True,
            "sensitive_payment_identifiers_"
            "redacted": True,
        },
    }

@router.post(
    "/phone-number/purchase"
)
def purchase_shop_ai_phone_number(
    payload: PurchaseShopPhoneNumberRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not bool(shop.ai_voice_enabled):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "AI Receptionist is not enabled "
                "for this shop."
            ),
        )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Provision the shop AI Receptionist "
                "before purchasing a phone number."
            ),
        )

    location_id = production_location_id(
        shop
    )

    requested_phone_number = (
        normalize_phone_number(
            payload.phone_number
        )
    )

    if not requested_phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A phone number is required."
            ),
        )

    _, existing_numbers = (
        get_location_phone_numbers(
            location_id=location_id,
        )
    )

    existing_record = (
        find_phone_record_by_number(
            phone_numbers=existing_numbers,
            phone_number=(
                requested_phone_number
            ),
        )
    )

    if existing_record:
        routed_agent_id = (
            get_phone_routed_agent_id(
                existing_record
            )
        )

        if (
            routed_agent_id
            and routed_agent_id != agent_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "That HighLevel phone number "
                    "already exists in this location "
                    "and is routed to another AI agent."
                ),
            )

        return {
            "success": True,
            "already_owned": True,
            "chairtime_shop": {
                "id": shop.id,
                "slug": shop.slug,
                "name": shop.name,
            },
            "location_id": location_id,
            "phone_number": (
                requested_phone_number
            ),
            "phone_record": existing_record,
        }

    area_code_digits = "".join(
        character
        for character
        in requested_phone_number
        if character.isdigit()
    )

    if (
        len(area_code_digits) == 11
        and area_code_digits.startswith("1")
    ):
        area_code = area_code_digits[1:4]

    elif len(area_code_digits) >= 10:
        area_code = area_code_digits[:3]

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The phone number must be a "
                "valid U.S. phone number."
            ),
        )

    available_records, _ = (
        search_available_phone_numbers(
            location_id=location_id,
            area_code=area_code,
        )
    )

    available_record = None

    for record in available_records:
        candidate_number = (
            phone_number_from_available_record(
                record
            )
        )

        if (
            candidate_number
            == requested_phone_number
        ):
            available_record = record
            break

    if not available_record:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The phone number you selected is "
                "no longer available. Please choose "
                "another number."
            ),
        )

    purchase_path = (
        "/phone-system/numbers/location/"
        f"{location_id}/purchase"
    )

    purchase_payload = (
        build_phone_purchase_payload(
            phone_number=(
                requested_phone_number
            ),
            available_record=(
                available_record
            ),
        )
    )

    purchase_response = (
        highlevel_phone_purchase_request(
            method="POST",
            path=purchase_path,
            json_body=purchase_payload,
            timeout=45,
        )
    )

    if purchase_response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": (
                    "HighLevel could not purchase "
                    "the selected phone number."
                ),
                "highlevel_status": (
                    purchase_response.status_code
                ),
                "highlevel_error": (
                    response_body_for_log(
                        purchase_response
                    )
                ),
                "trace_or_request_id": (
                    get_response_request_id(
                        purchase_response
                    )
                ),
            },
        )

    # HighLevel may take a moment to expose the newly
    # purchased number in the location's number list.
    purchased_record = None

    for _ in range(5):
        time.sleep(1)

        _, refreshed_numbers = (
            get_location_phone_numbers(
                location_id=location_id,
            )
        )

        purchased_record = (
            find_phone_record_by_number(
                phone_numbers=(
                    refreshed_numbers
                ),
                phone_number=(
                    requested_phone_number
                ),
            )
        )

        if purchased_record:
            break

    if not purchased_record:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel reported that the phone "
                "number purchase succeeded, but the "
                "number is not yet visible in the "
                "location. Do not purchase another "
                "number until this is verified."
            ),
        )

    return {
        "success": True,
        "already_owned": False,
        "chairtime_shop": {
            "id": shop.id,
            "slug": shop.slug,
            "name": shop.name,
        },
        "location_id": location_id,
        "phone_number": (
            requested_phone_number
        ),
        "phone_record": purchased_record,
    }


@router.post(
    "/phone-number/assign"
)
def assign_shop_ai_phone_number(
    payload: AssignShopPhoneNumberRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not bool(shop.ai_voice_enabled):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "AI Receptionist is not enabled "
                "for this shop."
            ),
        )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Provision the shop AI Receptionist "
                "before assigning a phone number."
            ),
        )

    location_id = production_location_id(
        shop
    )

    requested_phone_number = (
        normalize_phone_number(
            payload.phone_number
        )
    )

    if not requested_phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A phone number is required."
            ),
        )

    _, phone_numbers = (
        get_location_phone_numbers(
            location_id=location_id,
        )
    )

    phone_record = (
        find_phone_record_by_number(
            phone_numbers=phone_numbers,
            phone_number=(
                requested_phone_number
            ),
        )
    )

    if not phone_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "That phone number does not exist "
                "in this HighLevel location."
            ),
        )

    existing_routed_agent_id = (
        get_phone_routed_agent_id(
            phone_record
        )
    )

    if (
        existing_routed_agent_id
        and existing_routed_agent_id
        != agent_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "That phone number is already routed "
                "to another HighLevel AI agent."
            ),
        )

    phone_record_id = (
        get_phone_record_id(
            phone_record
        )
    )

    if not phone_record_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel returned the phone number "
                "without an assignable phone record ID."
            ),
        )

    if existing_routed_agent_id == agent_id:
        assigned_record = phone_record

    else:
        assignment_payloads = [
            {
                "inboundCallService": {
                    "type": "voiceAi",
                    "agentId": agent_id,
                },
            },
            {
                "inboundCallService": {
                    "type": "VOICE_AI",
                    "agentId": agent_id,
                },
            },
            {
                "inboundCallService": {
                    "type": "voice_ai",
                    "agentId": agent_id,
                },
            },
            {
                "agentId": agent_id,
            },
        ]

        assignment_paths = [
            (
                "/phone-system/numbers/"
                f"{phone_record_id}"
            ),
            (
                "/phone-system/numbers/location/"
                f"{location_id}/"
                f"{phone_record_id}"
            ),
        ]

        last_response = None

        for assignment_path in assignment_paths:
            for assignment_payload in (
                assignment_payloads
            ):
                response = (
                    highlevel_phone_request(
                        method="PUT",
                        path=assignment_path,
                        json_body=(
                            assignment_payload
                        ),
                        timeout=30,
                    )
                )

                last_response = response

                if response.status_code < 400:
                    break

                response = (
                    highlevel_phone_request(
                        method="PATCH",
                        path=assignment_path,
                        json_body=(
                            assignment_payload
                        ),
                        timeout=30,
                    )
                )

                last_response = response

                if response.status_code < 400:
                    break

            if (
                last_response is not None
                and last_response.status_code
                < 400
            ):
                break

        if (
            last_response is None
            or last_response.status_code >= 400
        ):
            if last_response is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_502_BAD_GATEWAY
                    ),
                    detail=(
                        "ChairTime could not submit "
                        "the phone assignment request."
                    ),
                )

            raise HTTPException(
                status_code=(
                    status.HTTP_502_BAD_GATEWAY
                ),
                detail={
                    "message": (
                        "HighLevel could not assign "
                        "the phone number to the "
                        "AI Receptionist."
                    ),
                    "highlevel_status": (
                        last_response.status_code
                    ),
                    "highlevel_error": (
                        response_body_for_log(
                            last_response
                        )
                    ),
                },
            )

        assigned_record = None

        for _ in range(5):
            time.sleep(1)

            _, refreshed_numbers = (
                get_location_phone_numbers(
                    location_id=location_id,
                )
            )

            candidate_record = (
                find_phone_record_by_number(
                    phone_numbers=(
                        refreshed_numbers
                    ),
                    phone_number=(
                        requested_phone_number
                    ),
                )
            )

            if (
                candidate_record
                and get_phone_routed_agent_id(
                    candidate_record
                )
                == agent_id
            ):
                assigned_record = (
                    candidate_record
                )
                break

        if not assigned_record:
            raise HTTPException(
                status_code=(
                    status.HTTP_502_BAD_GATEWAY
                ),
                detail=(
                    "HighLevel accepted the phone "
                    "assignment request, but ChairTime "
                    "could not verify that the number "
                    "is routed to this AI Receptionist."
                ),
            )

    shop.highlevel_phone_number = (
        requested_phone_number
    )

    try:
        db.commit()
        db.refresh(shop)

    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "chairtime_shop": {
            "id": shop.id,
            "slug": shop.slug,
            "name": shop.name,
            "highlevel_phone_number": (
                shop.highlevel_phone_number
            ),
            "highlevel_agent_id": (
                shop.highlevel_agent_id
            ),
        },
        "location_id": location_id,
        "phone_record": assigned_record,
    }


@router.get(
    "/phone-number/status"
)
def get_shop_ai_phone_number_status(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    location_id = production_location_id(
        shop
    )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    stored_phone_number = str(
        shop.highlevel_phone_number or ""
    ).strip()

    if not agent_id:
        return {
            "success": True,
            "configured": False,
            "reason": (
                "The shop AI Receptionist "
                "has not been provisioned yet."
            ),
            "chairtime_shop": {
                "id": shop.id,
                "slug": shop.slug,
                "name": shop.name,
                "highlevel_phone_number": (
                    stored_phone_number
                    or None
                ),
                "highlevel_agent_id": None,
            },
            "location_id": location_id,
            "matched_phone_record": None,
        }

    _, phone_numbers = (
        get_location_phone_numbers(
            location_id=location_id,
        )
    )

    routed_matches = (
        find_phone_numbers_routed_to_agent(
            phone_numbers=phone_numbers,
            agent_id=agent_id,
        )
    )

    if len(routed_matches) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "More than one HighLevel phone "
                "number is routed to this shop's "
                "AI Receptionist."
            ),
        )

    matched_phone = (
        routed_matches[0]
        if routed_matches
        else None
    )

    matched_number = (
        phone_record_number(
            matched_phone
        )
        if matched_phone
        else ""
    )

    synchronized = (
        bool(matched_number)
        and matched_number
        == normalize_phone_number(
            stored_phone_number
        )
    )

    return {
        "success": True,
        "configured": bool(
            matched_phone
        ),
        "synchronized": synchronized,
        "chairtime_shop": {
            "id": shop.id,
            "slug": shop.slug,
            "name": shop.name,
            "highlevel_phone_number": (
                stored_phone_number
                or None
            ),
            "highlevel_agent_id": (
                agent_id
            ),
        },
        "location_id": location_id,
        "matched_phone_record": (
            matched_phone
        ),
    }

@router.post(
    "/phone-number/verify"
)
def verify_shop_ai_phone_number(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not bool(shop.ai_voice_enabled):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "AI Receptionist is not enabled "
                "for this shop."
            ),
        )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This shop does not have a "
                "HighLevel AI agent yet."
            ),
        )

    location_id = production_location_id(
        shop
    )

    matched_phone = (
        sync_shop_phone_number_from_highlevel(
            shop=shop,
            db=db,
            require_match=True,
        )
    )

    phone_number = (
        phone_record_number(
            matched_phone
        )
    )

    routed_agent_id = (
        get_phone_routed_agent_id(
            matched_phone
        )
    )

    if routed_agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The HighLevel phone number is not "
                "routed to this shop's AI "
                "Receptionist."
            ),
        )

    return {
        "success": True,
        "verified": True,
        "chairtime_shop": {
            "id": shop.id,
            "slug": shop.slug,
            "name": shop.name,
            "highlevel_phone_number": (
                shop.highlevel_phone_number
            ),
            "highlevel_agent_id": (
                shop.highlevel_agent_id
            ),
        },
        "location_id": location_id,
        "phone_number": phone_number,
        "phone_record": matched_phone,
    }


@router.post(
    "/phone-number/reconcile"
)
def reconcile_shop_ai_phone_number(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not bool(shop.ai_voice_enabled):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "AI Receptionist is not enabled "
                "for this shop."
            ),
        )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This shop does not have a "
                "HighLevel AI agent yet."
            ),
        )

    location_id = production_location_id(
        shop
    )

    highlevel_data, phone_numbers = (
        get_location_phone_numbers(
            location_id=location_id,
        )
    )

    routed_matches = (
        find_phone_numbers_routed_to_agent(
            phone_numbers=phone_numbers,
            agent_id=agent_id,
        )
    )

    if len(routed_matches) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "More than one HighLevel phone "
                "number is routed to this shop's "
                "AI Receptionist. ChairTime will "
                "not choose between them "
                "automatically."
            ),
        )

    if not routed_matches:
        return {
            "success": True,
            "reconciled": False,
            "reason": (
                "No HighLevel phone number is "
                "currently routed to this shop's "
                "AI Receptionist."
            ),
            "chairtime_shop": {
                "id": shop.id,
                "slug": shop.slug,
                "name": shop.name,
                "stored_phone_number": (
                    shop.highlevel_phone_number
                ),
                "highlevel_agent_id": (
                    shop.highlevel_agent_id
                ),
            },
            "location_id": location_id,
            "highlevel_phone_count": len(
                phone_numbers
            ),
            "highlevel_response": (
                highlevel_data
            ),
        }

    matched_phone = routed_matches[0]

    matched_number = (
        phone_record_number(
            matched_phone
        )
    )

    if not matched_number:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel returned a routed phone "
                "record without a phone number."
            ),
        )

    previous_phone_number = str(
        shop.highlevel_phone_number or ""
    ).strip()

    changed = (
        normalize_phone_number(
            previous_phone_number
        )
        != matched_number
    )

    if changed:
        shop.highlevel_phone_number = (
            matched_number
        )

        try:
            db.commit()
            db.refresh(shop)

        except Exception:
            db.rollback()
            raise

    return {
        "success": True,
        "reconciled": True,
        "database_changed": changed,
        "chairtime_shop": {
            "id": shop.id,
            "slug": shop.slug,
            "name": shop.name,
            "previous_phone_number": (
                previous_phone_number
                or None
            ),
            "highlevel_phone_number": (
                shop.highlevel_phone_number
            ),
            "highlevel_agent_id": (
                shop.highlevel_agent_id
            ),
        },
        "location_id": location_id,
        "matched_phone_record": (
            matched_phone
        ),
    }


@router.get(
    "/phone-number/debug"
)
def debug_shop_ai_phone_number(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    location_id = production_location_id(
        shop
    )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    stored_phone_number = str(
        shop.highlevel_phone_number or ""
    ).strip()

    highlevel_data, phone_numbers = (
        get_location_phone_numbers(
            location_id=location_id,
        )
    )

    stored_record = None

    if stored_phone_number:
        stored_record = (
            find_phone_record_by_number(
                phone_numbers=phone_numbers,
                phone_number=(
                    stored_phone_number
                ),
            )
        )

    routed_matches = []

    if agent_id:
        routed_matches = (
            find_phone_numbers_routed_to_agent(
                phone_numbers=phone_numbers,
                agent_id=agent_id,
            )
        )

    return {
        "success": True,
        "chairtime_shop": {
            "id": shop.id,
            "slug": shop.slug,
            "name": shop.name,
            "ai_voice_enabled": bool(
                shop.ai_voice_enabled
            ),
            "stored_phone_number": (
                stored_phone_number
                or None
            ),
            "highlevel_location_id": (
                location_id
            ),
            "highlevel_agent_id": (
                agent_id
                or None
            ),
        },
        "stored_phone_found_in_highlevel": (
            stored_record is not None
        ),
        "stored_phone_record": (
            stored_record
        ),
        "numbers_routed_to_shop_agent": (
            routed_matches
        ),
        "highlevel_phone_count": len(
            phone_numbers
        ),
        "highlevel_response": highlevel_data,
    }


@router.get(
    "/phone-number/purchase-config"
)
def get_phone_purchase_config_status(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    billing_values = (
        get_phone_purchase_billing_values()
    )

    return {
        "success": True,
        "chairtime_shop": {
            "id": shop.id,
            "slug": shop.slug,
            "name": shop.name,
        },
        "location_id": (
            production_location_id(shop)
        ),
        "phone_api_base_url": (
            highlevel_phone_host()
        ),
        "purchase_api_version": "v3",
        "configuration": {
            "highlevel_api_token_present": bool(
                str(
                    os.getenv(
                        "HIGHLEVEL_API_TOKEN",
                        "",
                    )
                    or ""
                ).strip()
            ),
            "stripe_account_id_present": bool(
                billing_values[
                    "stripe_account_id"
                ]
            ),
            "payment_method_id_present": bool(
                billing_values[
                    "payment_method_id"
                ]
            ),
            "fingerprint_id_present": bool(
                billing_values[
                    "fingerprint_id"
                ]
            ),
        },
    }


@router.get(
    "/phone-number/highlevel-routing"
)
def get_highlevel_phone_routing(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    location_id = production_location_id(
        shop
    )

    _, phone_numbers = (
        get_location_phone_numbers(
            location_id=location_id,
        )
    )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    routing = []

    for phone_record in phone_numbers:
        routing.append(
            {
                "phone_number": (
                    phone_record_number(
                        phone_record
                    )
                ),
                "phone_record_id": (
                    get_phone_record_id(
                        phone_record
                    )
                ),
                "routed_agent_id": (
                    get_phone_routed_agent_id(
                        phone_record
                    )
                    or None
                ),
                "belongs_to_shop_agent": (
                    bool(agent_id)
                    and (
                        get_phone_routed_agent_id(
                            phone_record
                        )
                        == agent_id
                    )
                ),
                "inbound_call_service": (
                    get_phone_inbound_service(
                        phone_record
                    )
                ),
            }
        )

    return {
        "success": True,
        "chairtime_shop": {
            "id": shop.id,
            "slug": shop.slug,
            "name": shop.name,
            "highlevel_agent_id": (
                agent_id
                or None
            ),
        },
        "location_id": location_id,
        "count": len(routing),
        "routing": routing,
    }
