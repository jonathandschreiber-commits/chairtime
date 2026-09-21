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

TEST_AGENT_PROMPT = (
    "You are the appointment receptionist for this business. "
    "Be warm, brief, and efficient.\n"
    "Use ChairTime actions for real availability and bookings. "
    "Never invent an opening or claim a booking succeeded before "
    "the booking action confirms it.\n"
    "A caller saying anyone, any barber, whoever is available, "
    "or no preference has given a complete staff preference. "
    "Do not ask them to choose a provider. Use No preference for "
    "the availability and booking actions. Tell the caller the "
    "assigned provider after booking.\n"
    "Collect the service and date, then check availability. "
    "A morning, afternoon, or evening request is sufficient; "
    "pass that time window to the availability action. Morning "
    "is before noon, afternoon is noon to 5 PM, and evening is "
    "5 PM onward, subject to actual shop hours. Offer up to three "
    "suitable returned times. If the caller asks for the earliest "
    "opening, use the earliest matching time. If they give an exact "
    "time, check that time directly.\n"
    "Once the caller chooses a time, collect only missing booking "
    "information and book. A clear request to book is authorization; "
    "do not ask for another confirmation of the same service, date, "
    "time, or provider. Ask only when information is missing or "
    "genuinely ambiguous.\n"
    "After a successful booking, state the assigned provider, date, "
    "and time, and say that a confirmation text was sent only if "
    "confirmation_sms_sent is true. If texting failed, say the "
    "appointment is booked but the text could not be sent. Do not "
    "promise a reminder was delivered merely because it is scheduled.\n"
    "Do not repeat idle check-ins or narrate a long wait. If an "
    "action fails, apologize briefly and offer a useful next step. "
    "Never pretend to be checking availability when no action is running."
)

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


def build_test_agent_payload(
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
        "agentName": TEST_AGENT_NAME,
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


def get_or_create_test_agent(
    shop: Shop,
    location_id: str,
) -> tuple[dict, bool]:
    existing_agent = find_existing_test_agent(
        location_id=location_id
    )

    if existing_agent:
        return existing_agent, False

    response = highlevel_request(
        method="POST",
        path="/voice-ai/agents",
        json_body=build_test_agent_payload(
            shop=shop,
            location_id=location_id,
        ),
    )

    return response_json(response), True


def update_test_agent_settings(
    agent_id: str,
    location_id: str,
) -> dict:
    agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    if agent.get("agentName") != TEST_AGENT_NAME:
        raise HTTPException(
            status_code=409,
            detail=(
                "Only the provisioning test agent "
                "may be updated."
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
            "locationId": location_id
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
        refreshed.get("agentPrompt")
        != TEST_AGENT_PROMPT
        or refreshed.get("sendUserIdleReminders")
        is not False
    ):
        raise HTTPException(
            status_code=502,
            detail=(
                "HighLevel did not retain the "
                "requested test-agent settings."
            ),
        )

    return refreshed


def production_agent_name(shop: Shop) -> str:
    identifier = shop.slug or str(shop.id)

    return (
        f"{PRODUCTION_AGENT_NAME_PREFIX} - "
        f"{identifier}"
    )


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
        "agentName": production_agent_name(
            shop
        ),
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

    return str(
        shop.highlevel_webhook_secret
    )


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
            detail=(
                "Invalid ChairTime AI "
                "webhook credential."
            ),
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

        if (
            agent.get("agentName")
            == TEST_AGENT_NAME
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The shared provisioning-test "
                    "agent cannot be assigned "
                    "to a shop."
                ),
            )

        return agent, False

    response = highlevel_request(
        method="POST",
        path="/voice-ai/agents",
        json_body=(
            build_production_agent_payload(
                shop=shop,
                location_id=location_id,
            )
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
                "HighLevel did not return an ID "
                "for the shop AI receptionist."
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
                "HighLevel returned an AI agent "
                "already assigned to another "
                "ChairTime shop."
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
    if (
        str(shop.highlevel_agent_id or "")
        != agent_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This AI agent is not assigned "
                "to the current ChairTime shop."
            ),
        )

    agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    if (
        agent.get("agentName")
        == TEST_AGENT_NAME
    ):
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
        params={
            "locationId": location_id
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
        refreshed.get("agentPrompt")
        != TEST_AGENT_PROMPT
        or refreshed.get(
            "sendUserIdleReminders"
        )
        is not False
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel did not retain the "
                "requested shop AI settings."
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
            detail=(
                "AI agent not found for this shop."
            ),
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
            detail=(
                "AI action not found for this shop."
            ),
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
        detail=(
            "AI action not found for this shop."
        ),
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
                "success",
                "barber",
                "service",
                "target_date",
                "slots",
                "available_count",
                "time_window",
            ],
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


def create_or_update_action(
    agent_id: str,
    location_id: str,
    action_name: str,
    payload: dict,
    expected_url: Optional[str] = None,
) -> dict:
    agent_data = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    existing_action = find_action_by_name(
        agent_data=agent_data,
        action_name=action_name,
    )

    existing_action_id = get_action_id(
        existing_action
    )

    if existing_action_id:
        response = highlevel_raw_request(
            method="PUT",
            path=(
                f"/voice-ai/actions/"
                f"{existing_action_id}"
            ),
            json_body=payload,
        )

        if response.status_code < 400:
            refreshed_agent = get_agent_detail(
                agent_id=agent_id,
                location_id=location_id,
            )

            refreshed_action = find_action_by_name(
                agent_data=refreshed_agent,
                action_name=action_name,
            )

            return {
                "operation": "updated",
                "action": safe_action(
                    refreshed_action
                    or existing_action
                ),
            }

        verified_action = (
            verify_action_after_warning(
                agent_id=agent_id,
                location_id=location_id,
                action_name=action_name,
                response=response,
                expected_url=expected_url,
            )
        )

        if verified_action:
            return {
                "operation": (
                    "updated_and_verified"
                ),
                "action": safe_action(
                    verified_action
                ),
                "highlevel_warning": (
                    safe_highlevel_error(
                        response
                    )
                ),
            }

        raise_highlevel_error(response)

    response = highlevel_raw_request(
        method="POST",
        path="/voice-ai/actions",
        json_body=payload,
    )

    if response.status_code < 400:
        created_data = response_json(response)

        refreshed_agent = get_agent_detail(
            agent_id=agent_id,
            location_id=location_id,
        )

        refreshed_action = find_action_by_name(
            agent_data=refreshed_agent,
            action_name=action_name,
        )

        return {
            "operation": "created",
            "action": safe_action(
                refreshed_action
                or created_data
            ),
        }

    verified_action = (
        verify_action_after_warning(
            agent_id=agent_id,
            location_id=location_id,
            action_name=action_name,
            response=response,
            expected_url=expected_url,
        )
    )

    if verified_action:
        return {
            "operation": (
                "created_and_verified"
            ),
            "action": safe_action(
                verified_action
            ),
            "highlevel_warning": (
                safe_highlevel_error(
                    response
                )
            ),
        }

    raise_highlevel_error(response)


@router.post(
    "/webhook/{shop_slug}/availability"
)
async def tenant_voice_availability(
    shop_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    shop = get_shop_by_slug(
        shop_slug=shop_slug,
        db=db,
    )

    if shop.highlevel_agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "The legacy provisioning-test webhook is "
                "disabled for production AI shops."
            ),
        )

    incoming = {}

    try:
        json_data = await request.json()

        if isinstance(json_data, dict):
            incoming.update(json_data)

    except Exception:
        pass

    incoming = decode_highlevel_fields(incoming)

    for key, value in request.query_params.items():
        if (
            value is not None
            and key not in incoming
        ):
            incoming[key] = (
                decode_highlevel_value(value)
            )

    if not incoming:
        try:
            form_data = await request.form()

            for key, value in form_data.items():
                if value is not None:
                    incoming[key] = (
                        decode_highlevel_value(
                            value
                        )
                    )

        except Exception:
            pass

    service_name = incoming.get(
        "service_name"
    )
    target_date = incoming.get(
        "target_date"
    )
    barber_name = normalize_barber_name(
        incoming.get("barber_name")
    )

    missing_fields = []

    if not service_name:
        missing_fields.append(
            "service_name"
        )

    if not target_date:
        missing_fields.append(
            "target_date"
        )

    if missing_fields:
        return {
            "success": False,
            "message": (
                "ChairTime received the HighLevel webhook, "
                "but required appointment values were not "
                "included in the request."
            ),
            "missing_fields": missing_fields,
            "received_fields": sorted(
                incoming.keys()
            ),
            "content_type": (
                request.headers.get(
                    "content-type"
                )
            ),
        }

    request_payload = {
        "shop_slug": shop.slug,
        "service_name": str(
            service_name
        ).strip(),
        "target_date": str(
            target_date
        ).strip(),
        "barber_name": barber_name,
        "time_window": incoming.get(
            "time_window"
        ),
        "preferred_start_time": (
            incoming.get(
                "preferred_start_time"
            )
        ),
    }

    started = time.monotonic()

    result = await asyncio.to_thread(
        chairtime_voice_request,
        url=CHAIRTIME_AVAILABILITY_URL,
        payload=request_payload,
    )

    logger.info(
        "voice_availability shop=%s "
        "duration_ms=%d slot_count=%d",
        shop.slug,
        int(
            (
                time.monotonic()
                - started
            )
            * 1000
        ),
        len(
            result.get("slots")
            or []
        ),
    )

    return result


@router.post(
    "/webhook/{shop_slug}/book"
)
async def tenant_voice_booking(
    shop_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    shop = get_shop_by_slug(
        shop_slug=shop_slug,
        db=db,
    )

    if shop.highlevel_agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "The legacy provisioning-test webhook is "
                "disabled for production AI shops."
            ),
        )

    incoming = {}

    try:
        json_data = await request.json()

        if isinstance(json_data, dict):
            incoming.update(json_data)

    except Exception:
        pass

    incoming = decode_highlevel_fields(incoming)

    for key, value in request.query_params.items():
        if (
            value is not None
            and key not in incoming
        ):
            incoming[key] = (
                decode_highlevel_value(value)
            )

    if not incoming:
        try:
            form_data = await request.form()

            for key, value in form_data.items():
                if value is not None:
                    incoming[key] = (
                        decode_highlevel_value(
                            value
                        )
                    )

        except Exception:
            pass

    required_fields = [
        "service_name",
        "target_date",
        "start_time",
        "customer_name",
        "customer_phone",
    ]

    missing_fields = [
        field
        for field in required_fields
        if not incoming.get(field)
    ]

    if missing_fields:
        return {
            "success": False,
            "message": (
                "ChairTime received the HighLevel webhook, "
                "but required booking values were not "
                "included in the request."
            ),
            "missing_fields": missing_fields,
            "received_fields": sorted(
                incoming.keys()
            ),
            "content_type": (
                request.headers.get(
                    "content-type"
                )
            ),
        }

    barber_name = normalize_barber_name(
        incoming.get("barber_name")
    )

    request_payload = {
        "shop_slug": shop.slug,
        "service_name": str(
            incoming["service_name"]
        ).strip(),
        "target_date": str(
            incoming["target_date"]
        ).strip(),
        "start_time": str(
            incoming["start_time"]
        ).strip(),
        "customer_name": str(
            incoming["customer_name"]
        ).strip(),
        "customer_phone": str(
            incoming["customer_phone"]
        ).strip(),
        "barber_name": barber_name,
    }

    return await asyncio.to_thread(
        chairtime_voice_request,
        url=CHAIRTIME_BOOKING_URL,
        payload=request_payload,
    )


@router.post(
    "/tenant-webhook/{shop_slug}/availability"
)
async def production_tenant_voice_availability(
    shop_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    shop = get_shop_by_slug(
        shop_slug=shop_slug,
        db=db,
    )

    if not shop.highlevel_agent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Production AI receptionist "
                "is not configured."
            ),
        )

    verify_production_webhook_secret(
        shop=shop,
        request=request,
    )

    incoming = {}

    try:
        json_data = await request.json()

        if isinstance(json_data, dict):
            incoming.update(json_data)

    except Exception:
        pass

    incoming = decode_highlevel_fields(
        incoming
    )

    for key, value in request.query_params.items():
        if (
            value is not None
            and key not in incoming
        ):
            incoming[key] = (
                decode_highlevel_value(
                    value
                )
            )

    if not incoming:
        try:
            form_data = await request.form()

            for key, value in form_data.items():
                if value is not None:
                    incoming[key] = (
                        decode_highlevel_value(
                            value
                        )
                    )

        except Exception:
            pass

    service_name = incoming.get(
        "service_name"
    )
    target_date = incoming.get(
        "target_date"
    )
    barber_name = normalize_barber_name(
        incoming.get("barber_name")
    )

    missing_fields = []

    if not service_name:
        missing_fields.append(
            "service_name"
        )

    if not target_date:
        missing_fields.append(
            "target_date"
        )

    if missing_fields:
        return {
            "success": False,
            "message": (
                "ChairTime received the AI webhook, "
                "but required appointment values were "
                "not included in the request."
            ),
            "missing_fields": (
                missing_fields
            ),
            "received_fields": sorted(
                incoming.keys()
            ),
            "content_type": (
                request.headers.get(
                    "content-type"
                )
            ),
        }

    request_payload = {
        "shop_slug": shop.slug,
        "service_name": str(
            service_name
        ).strip(),
        "target_date": str(
            target_date
        ).strip(),
        "barber_name": barber_name,
        "time_window": incoming.get(
            "time_window"
        ),
        "preferred_start_time": (
            incoming.get(
                "preferred_start_time"
            )
        ),
    }

    started = time.monotonic()

    result = await asyncio.to_thread(
        chairtime_voice_request,
        url=CHAIRTIME_AVAILABILITY_URL,
        payload=request_payload,
    )

    logger.info(
        "production_voice_availability "
        "shop=%s duration_ms=%d "
        "slot_count=%d",
        shop.slug,
        int(
            (
                time.monotonic()
                - started
            )
            * 1000
        ),
        len(
            result.get("slots")
            or []
        ),
    )

    return result


@router.post(
    "/tenant-webhook/{shop_slug}/book"
)
async def production_tenant_voice_booking(
    shop_slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    shop = get_shop_by_slug(
        shop_slug=shop_slug,
        db=db,
    )

    if not shop.highlevel_agent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Production AI receptionist "
                "is not configured."
            ),
        )

    verify_production_webhook_secret(
        shop=shop,
        request=request,
    )

    incoming = {}

    try:
        json_data = await request.json()

        if isinstance(json_data, dict):
            incoming.update(json_data)

    except Exception:
        pass

    incoming = decode_highlevel_fields(
        incoming
    )

    for key, value in request.query_params.items():
        if (
            value is not None
            and key not in incoming
        ):
            incoming[key] = (
                decode_highlevel_value(
                    value
                )
            )

    if not incoming:
        try:
            form_data = await request.form()

            for key, value in form_data.items():
                if value is not None:
                    incoming[key] = (
                        decode_highlevel_value(
                            value
                        )
                    )

        except Exception:
            pass

    required_fields = [
        "service_name",
        "target_date",
        "start_time",
        "customer_name",
        "customer_phone",
    ]

    missing_fields = [
        field
        for field in required_fields
        if not incoming.get(field)
    ]

    if missing_fields:
        return {
            "success": False,
            "message": (
                "ChairTime received the AI webhook, "
                "but required booking values were not "
                "included in the request."
            ),
            "missing_fields": missing_fields,
            "received_fields": sorted(
                incoming.keys()
            ),
            "content_type": (
                request.headers.get(
                    "content-type"
                )
            ),
        }

    barber_name = normalize_barber_name(
        incoming.get("barber_name")
    )

    request_payload = {
        "shop_slug": shop.slug,
        "service_name": str(
            incoming["service_name"]
        ).strip(),
        "target_date": str(
            incoming["target_date"]
        ).strip(),
        "start_time": str(
            incoming["start_time"]
        ).strip(),
        "customer_name": str(
            incoming["customer_name"]
        ).strip(),
        "customer_phone": str(
            incoming["customer_phone"]
        ).strip(),
        "barber_name": barber_name,
    }

    return await asyncio.to_thread(
        chairtime_voice_request,
        url=CHAIRTIME_BOOKING_URL,
        payload=request_payload,
    )

@router.get("/agents")
def get_highlevel_voice_agents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if not agent_id:
        return {
            "success": True,
            "chairtime_shop": {
                "id": str(shop.id),
                "slug": shop.slug,
                "name": shop.name,
            },
            "agent_count": 0,
            "agents": [],
        }

    location_id = production_location_id(shop)
    agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    return {
        "success": True,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "agent_count": 1,
        "agents": [safe_agent_summary(agent)],
    }


@router.get("/agents/{agent_id}")
def get_highlevel_voice_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    require_shop_agent(
        shop=shop,
        agent_id=agent_id,
    )

    location_id = production_location_id(shop)

    data = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    actions = [
        safe_action(action)
        for action in extract_actions(data)
    ]

    return {
        "success": True,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "agent": {
            "id": (
                data.get("id")
                or data.get("_id")
            ),
            "agent_name": data.get(
                "agentName"
            ),
            "business_name": data.get(
                "businessName"
            ),
            "welcome_message": data.get(
                "welcomeMessage"
            ),
            "agent_prompt": data.get(
                "agentPrompt"
            ),
            "language": data.get("language"),
            "voice_id": data.get("voiceId"),
            "timezone": data.get("timezone"),
            "patience_level": data.get(
                "patienceLevel"
            ),
            "max_call_duration": data.get(
                "maxCallDuration"
            ),
            "send_user_idle_reminders": data.get(
                "sendUserIdleReminders"
            ),
            "reminder_after_idle_seconds": (
                data.get(
                    "reminderAfterIdleTimeSeconds"
                )
            ),
            "inbound_number": data.get(
                "inboundNumber"
            ),
            "number_pool_id": data.get(
                "numberPoolId"
            ),
            "working_hours": data.get(
                "agentWorkingHours"
            ),
            "backup_disabled": data.get(
                "isAgentAsBackupDisabled"
            ),
            "actions": actions,
            "action_count": len(actions),
        },
    }


@router.get("/actions/{action_id}")
def get_highlevel_voice_action(
    action_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    location_id = production_location_id(shop)

    action = require_shop_action(
        shop=shop,
        action_id=action_id,
        location_id=location_id,
    )

    return {
        "success": True,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "action": safe_action(action),
    }


def extract_location_phone_numbers(
    data: dict,
) -> list:
    if not isinstance(data, dict):
        return []

    payload = data.get("data")

    if not isinstance(payload, dict):
        return []

    raw_numbers = payload.get("numbers")

    if not isinstance(raw_numbers, list):
        return []

    return [
        number
        for number in raw_numbers
        if isinstance(number, dict)
    ]


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

    return (
        data,
        extract_location_phone_numbers(data),
    )


def get_phone_inbound_service(
    phone_record: dict,
) -> dict:
    if not isinstance(phone_record, dict):
        return {}

    service = phone_record.get(
        "inboundCallService"
    )

    if not isinstance(service, dict):
        return {}

    return service


def find_phone_numbers_routed_to_agent(
    phone_numbers: list,
    agent_id: str,
) -> list:
    clean_agent_id = str(
        agent_id or ""
    ).strip()

    if not clean_agent_id:
        return []

    matches = []

    for phone_record in phone_numbers:
        if not isinstance(
            phone_record,
            dict,
        ):
            continue

        capabilities = (
            phone_record.get(
                "capabilities"
            )
            or {}
        )

        if not isinstance(
            capabilities,
            dict,
        ):
            capabilities = {}

        if (
            capabilities.get("voice")
            is not True
        ):
            continue

        inbound_service = (
            get_phone_inbound_service(
                phone_record
            )
        )

        service_type = str(
            inbound_service.get("type")
            or ""
        ).strip()

        service_value = str(
            inbound_service.get("value")
            or ""
        ).strip()

        if (
            service_type == "voice_ai"
            and service_value
            == clean_agent_id
        ):
            matches.append(
                phone_record
            )

    return matches


def get_shop_routed_phone_record(
    shop: Shop,
) -> tuple[dict, list, Optional[dict]]:
    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "This shop does not have a "
                "provisioned AI Receptionist "
                "agent."
            ),
        )

    location_id = production_location_id(
        shop
    )

    data, phone_numbers = (
        get_location_phone_numbers(
            location_id=location_id,
        )
    )

    matches = (
        find_phone_numbers_routed_to_agent(
            phone_numbers=phone_numbers,
            agent_id=agent_id,
        )
    )

    if len(matches) > 1:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "More than one HighLevel phone "
                "number is routed to this shop's "
                "AI Receptionist."
            ),
        )

    matched_phone = (
        matches[0]
        if matches
        else None
    )

    return (
        data,
        phone_numbers,
        matched_phone,
    )


def sync_shop_phone_number_from_highlevel(
    shop: Shop,
    db: Session,
    require_match: bool = True,
) -> Optional[dict]:
    _, _, matched_phone = (
        get_shop_routed_phone_record(
            shop=shop,
        )
    )

    if matched_phone is None:
        if require_match:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    "No HighLevel phone number "
                    "is currently routed to this "
                    "shop's AI Receptionist."
                ),
            )

        return None

    phone_number = str(
        matched_phone.get("phoneNumber")
        or ""
    ).strip()

    if not phone_number:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=(
                "HighLevel returned a routed "
                "phone record without a phone "
                "number."
            ),
        )

    stored_phone_number = str(
        shop.highlevel_phone_number
        or ""
    ).strip()

    if (
        stored_phone_number
        != phone_number
    ):
        shop.highlevel_phone_number = (
            phone_number
        )

        try:
            db.add(shop)
            db.commit()
            db.refresh(shop)

        except Exception:
            db.rollback()
            raise

    return matched_phone


@router.get("/provision/status")
def get_production_provision_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    response = {
        "success": True,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "ai_voice_enabled": bool(
            shop.ai_voice_enabled
        ),
        "provisioned": bool(agent_id),
        "phone_number": (
            str(
                shop.highlevel_phone_number
                or ""
            ).strip()
            or None
        ),
        "agent": None,
    }

    if not agent_id:
        return response

    location_id = (
        production_location_id(shop)
    )

    agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    response["agent"] = (
        safe_agent_summary(agent)
    )

    return response


@router.post("/provision")
def provision_production_ai_receptionist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.ai_voice_enabled:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "AI Receptionist is not enabled "
                "for this ChairTime subscription."
            ),
        )

    if not shop.slug:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "The ChairTime shop does not "
                "have a slug."
            ),
        )

    location_id = (
        production_location_id(shop)
    )

    if (
        shop.highlevel_location_id
        and str(
            shop.highlevel_location_id
        ).strip()
        != location_id
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "This shop is already associated "
                "with a different HighLevel "
                "location."
            ),
        )

    webhook_secret = (
        ensure_shop_webhook_secret(
            shop=shop,
            db=db,
        )
    )

    agent_data, agent_created = (
        get_or_create_production_agent(
            shop=shop,
            location_id=location_id,
            db=db,
        )
    )

    agent_id = str(
        agent_data.get("id")
        or agent_data.get("_id")
        or shop.highlevel_agent_id
        or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=(
                "HighLevel did not return an ID "
                "for the shop AI receptionist."
            ),
        )

    agent_data = (
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
            action_name=(
                "check_availability"
            ),
            payload=(
                build_availability_action_payload(
                    shop=shop,
                    agent_id=agent_id,
                    location_id=location_id,
                    webhook_url=(
                        availability_url
                    ),
                    webhook_secret=(
                        webhook_secret
                    ),
                )
            ),
            expected_url=(
                availability_url
            ),
        )
    )

    booking_result = (
        create_or_update_action(
            agent_id=agent_id,
            location_id=location_id,
            action_name=(
                "book_appointment"
            ),
            payload=(
                build_booking_action_payload(
                    shop=shop,
                    agent_id=agent_id,
                    location_id=location_id,
                    webhook_url=booking_url,
                    webhook_secret=(
                        webhook_secret
                    ),
                )
            ),
            expected_url=booking_url,
        )
    )

    refreshed_agent = (
        get_agent_detail(
            agent_id=agent_id,
            location_id=location_id,
        )
    )

    if (
        str(
            shop.highlevel_agent_id
            or ""
        )
        != agent_id
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "ChairTime could not verify "
                "this shop's AI agent ownership."
            ),
        )

    final_actions = [
        safe_action(action)
        for action in extract_actions(
            refreshed_agent
        )
    ]

    return {
        "success": True,
        "message": (
            "This shop's AI Receptionist "
            "is configured."
        ),
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "agent": {
            "id": agent_id,
            "agent_name": (
                refreshed_agent.get(
                    "agentName"
                )
                or production_agent_name(
                    shop
                )
            ),
            "created_this_request": (
                agent_created
            ),
        },
        "availability_action": (
            availability_result
        ),
        "booking_action": (
            booking_result
        ),
        "final_action_count": len(
            final_actions
        ),
        "final_actions": final_actions,
        "tenant_isolation": {
            "shop_agent_binding": True,
            "authenticated_webhooks": True,
            "shared_test_agent_used": False,
        },
    }


@router.post(
    "/provisioning-test/availability"
)
def provision_tenant_safe_availability(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.slug:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "The ChairTime shop does not "
                "have a slug."
            ),
        )

    location_id = (
        get_highlevel_location_id()
    )

    agent_data, agent_created = (
        get_or_create_test_agent(
            shop=shop,
            location_id=location_id,
        )
    )

    agent_id = (
        agent_data.get("id")
        or agent_data.get("_id")
    )

    if not agent_id:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=(
                "HighLevel did not return an ID "
                "for the provisioning test agent."
            ),
        )

    agent_data = (
        update_test_agent_settings(
            agent_id=agent_id,
            location_id=location_id,
        )
    )

    webhook_url = (
        tenant_availability_webhook_url(
            shop
        )
    )

    availability_result = (
        create_or_update_action(
            agent_id=agent_id,
            location_id=location_id,
            action_name=(
                "check_availability"
            ),
            payload=(
                build_availability_action_payload(
                    shop=shop,
                    agent_id=agent_id,
                    location_id=location_id,
                )
            ),
            expected_url=webhook_url,
        )
    )

    return {
        "success": True,
        "message": (
            "Tenant-safe ChairTime "
            "availability action is configured."
        ),
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "test_agent": {
            "id": agent_id,
            "agent_name": (
                agent_data.get(
                    "agentName"
                )
                or TEST_AGENT_NAME
            ),
            "created_this_request": (
                agent_created
            ),
        },
        "availability_webhook": (
            webhook_url
        ),
        "availability_action": (
            availability_result
        ),
        "working_receptionist_modified": False,
    }


@router.post(
    "/provisioning-test/booking"
)
def provision_tenant_safe_booking(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.slug:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "The ChairTime shop does not "
                "have a slug."
            ),
        )

    location_id = (
        get_highlevel_location_id()
    )

    agent_data, agent_created = (
        get_or_create_test_agent(
            shop=shop,
            location_id=location_id,
        )
    )

    agent_id = (
        agent_data.get("id")
        or agent_data.get("_id")
    )

    if not agent_id:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=(
                "HighLevel did not return an ID "
                "for the provisioning test agent."
            ),
        )

    current_agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    availability_action = (
        find_action_by_name(
            current_agent,
            "check_availability",
        )
    )

    if not availability_action:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "The test agent does not yet "
                "have a check_availability "
                "action."
            ),
        )

    agent_data = (
        update_test_agent_settings(
            agent_id=agent_id,
            location_id=location_id,
        )
    )

    webhook_url = (
        tenant_booking_webhook_url(
            shop
        )
    )

    booking_result = (
        create_or_update_action(
            agent_id=agent_id,
            location_id=location_id,
            action_name=(
                "book_appointment"
            ),
            payload=(
                build_booking_action_payload(
                    shop=shop,
                    agent_id=agent_id,
                    location_id=location_id,
                )
            ),
            expected_url=webhook_url,
        )
    )

    refreshed_agent = (
        get_agent_detail(
            agent_id=agent_id,
            location_id=location_id,
        )
    )

    return {
        "success": True,
        "message": (
            "Tenant-safe ChairTime booking "
            "action is configured."
        ),
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "test_agent": {
            "id": agent_id,
            "agent_name": (
                refreshed_agent.get(
                    "agentName"
                )
                or TEST_AGENT_NAME
            ),
            "created_this_request": (
                agent_created
            ),
        },
        "booking_webhook": webhook_url,
        "booking_action": (
            booking_result
        ),
        "final_action_count": len(
            extract_actions(
                refreshed_agent
            )
        ),
        "working_receptionist_modified": False,
    }

@router.post("/provisioning-test/full")
def provision_tenant_safe_voice_test(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The ChairTime shop does not have a slug."
            ),
        )

    location_id = get_highlevel_location_id()

    agent_data, agent_created = (
        get_or_create_test_agent(
            shop=shop,
            location_id=location_id,
        )
    )

    agent_id = (
        agent_data.get("id")
        or agent_data.get("_id")
    )

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel did not return an ID for the "
                "provisioning test agent."
            ),
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

    agent_data = update_test_agent_settings(
        agent_id=agent_id,
        location_id=location_id,
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

    refreshed_agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    final_actions = [
        safe_action(action)
        for action in extract_actions(
            refreshed_agent
        )
    ]

    return {
        "success": True,
        "message": (
            "Tenant-safe ChairTime availability and "
            "booking actions are configured."
        ),
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "test_agent": {
            "id": agent_id,
            "agent_name": (
                refreshed_agent.get(
                    "agentName"
                )
                or TEST_AGENT_NAME
            ),
            "created_this_request": agent_created,
        },
        "webhooks": {
            "availability": availability_url,
            "booking": booking_url,
        },
        "availability_action": (
            availability_result
        ),
        "booking_action": booking_result,
        "final_action_count": len(
            final_actions
        ),
        "final_actions": final_actions,
        "working_receptionist_modified": False,
    }


@router.get("/phone-numbers")
def get_shop_highlevel_phone_numbers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.ai_voice_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "AI Receptionist is not enabled for "
                "this ChairTime subscription."
            ),
        )

    location_id = production_location_id(shop)

    highlevel_data, phone_numbers = (
        get_location_phone_numbers(
            location_id=location_id,
        )
    )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    routed_matches = (
        find_phone_numbers_routed_to_agent(
            phone_numbers=phone_numbers,
            agent_id=agent_id,
        )
        if agent_id
        else []
    )

    if len(routed_matches) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "More than one HighLevel phone number is "
                "routed to this shop's AI Receptionist."
            ),
        )

    routed_phone = (
        routed_matches[0]
        if routed_matches
        else None
    )

    return {
        "success": True,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "location_id": location_id,
        "agent_id": agent_id or None,
        "stored_phone_number": (
            str(
                shop.highlevel_phone_number
                or ""
            ).strip()
            or None
        ),
        "routed_phone_number": (
            str(
                (routed_phone or {}).get(
                    "phoneNumber"
                )
                or ""
            ).strip()
            or None
        ),
        "routed_phone_record": routed_phone,
        "highlevel_response": highlevel_data,
    }


@router.post("/phone-number/sync")
def sync_shop_highlevel_phone_number(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.ai_voice_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "AI Receptionist is not enabled for "
                "this ChairTime subscription."
            ),
        )

    matched_phone = (
        sync_shop_phone_number_from_highlevel(
            shop=shop,
            db=db,
            require_match=True,
        )
    )

    phone_number = str(
        (matched_phone or {}).get(
            "phoneNumber"
        )
        or ""
    ).strip()

    return {
        "success": True,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "agent_id": str(
            shop.highlevel_agent_id or ""
        ).strip(),
        "phone_number": phone_number,
        "friendly_name": (
            (matched_phone or {}).get(
                "friendlyName"
            )
        ),
        "message": (
            "ChairTime synchronized the phone number "
            "currently routed to this shop's AI "
            "Receptionist."
        ),
    }


@router.post("/phone-number/assign")
def assign_shop_highlevel_phone_number(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Backward-compatible alias for the original test endpoint.

    HighLevel's phone-system routing is the authoritative source.
    This endpoint no longer guesses which active phone number to
    assign. It safely synchronizes the number already routed to
    this shop's exact Voice AI agent.
    """
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.ai_voice_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "AI Receptionist is not enabled for "
                "this ChairTime subscription."
            ),
        )

    matched_phone = (
        sync_shop_phone_number_from_highlevel(
            shop=shop,
            db=db,
            require_match=True,
        )
    )

    phone_number = str(
        (matched_phone or {}).get(
            "phoneNumber"
        )
        or ""
    ).strip()

    return {
        "success": True,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "agent": {
            "id": str(
                shop.highlevel_agent_id
                or ""
            ).strip(),
            "agent_name": (
                production_agent_name(shop)
            ),
        },
        "phone_number": phone_number,
        "friendly_name": (
            (matched_phone or {}).get(
                "friendlyName"
            )
        ),
        "message": (
            "ChairTime synchronized the HighLevel phone "
            "number routed to this shop's AI Receptionist."
        ),
    }


@router.get("/phone-number/current-agent")
def get_phone_number_current_agent(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.ai_voice_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "AI Receptionist is not enabled for "
                "this ChairTime subscription."
            ),
        )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This shop does not have a provisioned "
                "AI Receptionist agent."
            ),
        )

    _, _, matched_phone = (
        get_shop_routed_phone_record(
            shop=shop,
        )
    )

    if matched_phone is None:
        return {
            "success": True,
            "phone_number": None,
            "friendly_name": None,
            "inbound_service": {},
            "current_agent": None,
        }

    inbound_service = (
        get_phone_inbound_service(
            matched_phone
        )
    )

    location_id = production_location_id(
        shop
    )

    agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    return {
        "success": True,
        "phone_number": (
            matched_phone.get(
                "phoneNumber"
            )
        ),
        "friendly_name": (
            matched_phone.get(
                "friendlyName"
            )
        ),
        "inbound_service": inbound_service,
        "current_agent": (
            safe_agent_summary(agent)
        ),
    }


@router.get("/phone-numbers/available")
def get_available_highlevel_phone_numbers(
    area_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.ai_voice_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "AI Receptionist is not enabled for "
                "this ChairTime subscription."
            ),
        )

    clean_area_code = "".join(
        character
        for character in str(area_code)
        if character.isdigit()
    )

    if len(clean_area_code) != 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Area code must contain exactly 3 digits."
            ),
        )

    location_id = production_location_id(
        shop
    )

    response = highlevel_request(
        method="GET",
        path=(
            f"/phone-system/numbers/location/"
            f"{location_id}/available"
        ),
        params={
            "firstPart": clean_area_code,
            "lastPart": "",
            "anywhere": "",
            "numberTypes": "local",
            "smsEnabled": True,
            "mmsEnabled": True,
            "voiceEnabled": True,
            "countryCode": "US",
        },
    )

    data = response_json(response)

    raw_numbers = (
        data.get("numbers")
        or (
            data.get("data")
            or {}
        ).get("numbers")
        or []
    )

    available_numbers = []

    if isinstance(raw_numbers, list):
        for number in raw_numbers:
            if not isinstance(
                number,
                dict,
            ):
                continue

            phone_number = str(
                number.get("phoneNumber")
                or number.get("number")
                or ""
            ).strip()

            if not phone_number:
                continue

            available_numbers.append(
                {
                    "phone_number": (
                        phone_number
                    ),
                    "friendly_name": (
                        number.get(
                            "friendlyName"
                        )
                    ),
                    "locality": (
                        number.get(
                            "locality"
                        )
                        or number.get(
                            "city"
                        )
                    ),
                    "region": (
                        number.get(
                            "region"
                        )
                        or number.get(
                            "state"
                        )
                    ),
                    "capabilities": (
                        number.get(
                            "capabilities"
                        )
                    ),
                }
            )

    return {
        "success": True,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "area_code": clean_area_code,
        "location_id": location_id,
        "count": len(
            available_numbers
        ),
        "available_numbers": (
            available_numbers[:10]
        ),
    }


class PhoneNumberPurchaseRequest(
    BaseModel
):
    phone_number: str


def normalize_us_phone_number(
    value: str,
) -> str:
    digits = "".join(
        character
        for character in str(
            value or ""
        )
        if character.isdigit()
    )

    if len(digits) == 10:
        digits = "1" + digits

    if (
        len(digits) != 11
        or not digits.startswith("1")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A valid U.S. phone number is required."
            ),
        )

    return f"+{digits}"


def phone_numbers_match(
    first_value: str,
    second_value: str,
) -> bool:
    first_digits = "".join(
        character
        for character in str(
            first_value or ""
        )
        if character.isdigit()
    )

    second_digits = "".join(
        character
        for character in str(
            second_value or ""
        )
        if character.isdigit()
    )

    return (
        bool(first_digits)
        and first_digits
        == second_digits
    )


def find_phone_record_by_number(
    phone_numbers: list,
    phone_number: str,
) -> Optional[dict]:
    for phone_record in phone_numbers:
        if not isinstance(
            phone_record,
            dict,
        ):
            continue

        record_number = (
            phone_record.get(
                "phoneNumber"
            )
            or phone_record.get(
                "number"
            )
            or ""
        )

        if phone_numbers_match(
            record_number,
            phone_number,
        ):
            return phone_record

    return None


def get_phone_purchase_credentials(
) -> tuple[str, str]:
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

    missing = []

    if not stripe_account_id:
        missing.append(
            "HIGHLEVEL_PHONE_STRIPE_ACCOUNT_ID"
        )

    if not payment_method_id:
        missing.append(
            "HIGHLEVEL_PHONE_PAYMENT_METHOD_ID"
        )

    if missing:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "HighLevel phone purchasing is not "
                "fully configured. Missing: "
                + ", ".join(missing)
            ),
        )

    return (
        stripe_account_id,
        payment_method_id,
    )


def extract_available_phone_records(
    data: dict,
) -> list:
    raw_numbers = (
        data.get("numbers")
        or (
            data.get("data")
            or {}
        ).get("numbers")
        or []
    )

    if not isinstance(
        raw_numbers,
        list,
    ):
        return []

    return [
        number
        for number in raw_numbers
        if isinstance(number, dict)
        and (
            number.get("phoneNumber")
            or number.get("number")
        )
    ]


def get_fresh_available_phone_records(
    location_id: str,
    area_code: str,
    attempts: int = 3,
) -> list:
    last_response = None

    for attempt in range(attempts):
        response = highlevel_raw_request(
            method="GET",
            path=(
                f"/phone-system/numbers/location/"
                f"{location_id}/available"
            ),
            params={
                "firstPart": area_code,
                "lastPart": "",
                "anywhere": "",
                "numberTypes": "local",
                "smsEnabled": True,
                "mmsEnabled": True,
                "voiceEnabled": True,
                "countryCode": "US",
            },
        )

        last_response = response

        if response.status_code < 400:
            data = response_json(
                response
            )

            records = (
                extract_available_phone_records(
                    data
                )
            )

            if records:
                return records

        elif response.status_code < 500:
            raise_highlevel_error(
                response
            )

        if attempt < attempts - 1:
            time.sleep(0.4)

    if (
        last_response is not None
        and last_response.status_code
        >= 400
    ):
        raise_highlevel_error(
            last_response
        )

    return []

def wait_for_purchased_phone_number(
    location_id: str,
    phone_number: str,
    attempts: int = 10,
) -> Optional[dict]:
    for attempt in range(attempts):
        _, phone_numbers = (
            get_location_phone_numbers(
                location_id=location_id,
            )
        )

        matched_phone = (
            find_phone_record_by_number(
                phone_numbers=phone_numbers,
                phone_number=phone_number,
            )
        )

        if matched_phone:
            return matched_phone

        if attempt < attempts - 1:
            time.sleep(0.75)

    return None


def phone_purchase_error_is_unavailable(
    response: requests.Response,
) -> bool:
    if response.status_code in {
        404,
        409,
        410,
    }:
        return True

    error_text = highlevel_error_text(
        response
    )

    unavailable_phrases = (
        "not available",
        "no longer available",
        "unavailable",
        "already purchased",
        "already taken",
    )

    return any(
        phrase in error_text
        for phrase in unavailable_phrases
    )


def purchase_one_highlevel_phone_number(
    location_id: str,
    available_record: dict,
    stripe_account_id: str,
    payment_method_id: str,
) -> tuple[
    requests.Response,
    str,
    str,
    str,
]:
    phone_number = (
        normalize_us_phone_number(
            str(
                available_record.get(
                    "phoneNumber"
                )
                or available_record.get(
                    "number"
                )
                or ""
            )
        )
    )

    locality = str(
        available_record.get("locality")
        or available_record.get("city")
        or ""
    ).strip()

    region = str(
        available_record.get("region")
        or available_record.get("state")
        or ""
    ).strip()

    if not locality or not region:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "HighLevel did not return the locality "
                "and region required to purchase this "
                "phone number."
            ),
        )

    fingerprint_id = str(
        int(time.time() * 1000)
    )

    purchase_url = (
        f"{HIGHLEVEL_API_BASE_URL}"
        f"/phone-system/numbers/location/"
        f"{location_id}/purchase"
    )

    purchase_headers = (
        highlevel_phone_purchase_headers()
    )

    purchase_payload = {
        "phoneNumber": phone_number,
        "addressSid": "",
        "bundleSid": "",
        "countryCode": "US",
        "numberType": "local",
        "paymentIntentId": None,
        "stripeAccountId": (
            stripe_account_id
        ),
        "paymentMethodId": (
            payment_method_id
        ),
        "locality": locality,
        "region": region,
        "fingerprintId": fingerprint_id,
        "skipLocationKYC": False,
    }

    print(
        "HIGHLEVEL_PHONE_PURCHASE_REQUEST",
        {
            "url": purchase_url,
            "version": (
                purchase_headers.get(
                    "Version"
                )
            ),
            "accept": (
                purchase_headers.get(
                    "Accept"
                )
            ),
            "content_type": (
                purchase_headers.get(
                    "Content-Type"
                )
            ),
            "user_agent": (
                purchase_headers.get(
                    "User-Agent"
                )
            ),
            "phone_number": phone_number,
            "country_code": "US",
            "number_type": "local",
            "locality": locality,
            "region": region,
            "fingerprint_id": (
                fingerprint_id
            ),
            "skip_location_kyc": False,
            "has_stripe_account_id": bool(
                stripe_account_id
            ),
            "has_payment_method_id": bool(
                payment_method_id
            ),
        },
        flush=True,
    )

    try:
        response = requests.post(
            purchase_url,
            headers=purchase_headers,
            json=purchase_payload,
            timeout=20,
        )

    except requests.RequestException as exc:
        print(
            "HIGHLEVEL_PHONE_PURCHASE_EXCEPTION",
            {
                "exception_type": type(
                    exc
                ).__name__,
                "message": str(exc),
            },
            flush=True,
        )

        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=(
                "Could not connect to HighLevel."
            ),
        )

    try:
        response_body = response.json()

    except ValueError:
        response_body = (
            response.text[:3000]
        )

    print(
        "HIGHLEVEL_PHONE_PURCHASE_RESPONSE",
        {
            "status_code": (
                response.status_code
            ),
            "content_type": (
                response.headers.get(
                    "Content-Type"
                )
            ),
            "response_body": (
                response_body
            ),
        },
        flush=True,
    )

    return (
        response,
        phone_number,
        locality,
        region,
    )


@router.post("/phone-number/purchase")
def purchase_shop_ai_phone_number(
    payload: PhoneNumberPurchaseRequest,
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

    if not shop.ai_voice_enabled:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "AI Receptionist is not enabled "
                "for this ChairTime subscription."
            ),
        )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Set up the AI Receptionist "
                "before purchasing its phone "
                "number."
            ),
        )

    requested_phone_number = (
        normalize_us_phone_number(
            payload.phone_number
        )
    )

    requested_digits = "".join(
        character
        for character
        in requested_phone_number
        if character.isdigit()
    )

    area_code = requested_digits[1:4]

    location_id = (
        production_location_id(shop)
    )

    # First make sure the selected number is
    # not already active in this HighLevel
    # location.
    _, active_phone_numbers = (
        get_location_phone_numbers(
            location_id=location_id,
        )
    )

    existing_phone = (
        find_phone_record_by_number(
            phone_numbers=(
                active_phone_numbers
            ),
            phone_number=(
                requested_phone_number
            ),
        )
    )

    if existing_phone:
        return {
            "success": True,
            "purchased": False,
            "already_owned": True,
            "requested_phone_number": (
                requested_phone_number
            ),
            "phone_number": (
                requested_phone_number
            ),
            "fallback_used": False,
            "message": (
                "This phone number is already "
                "active in the HighLevel location."
            ),
        }

    (
        stripe_account_id,
        payment_method_id,
    ) = get_phone_purchase_credentials()

    # Refresh HighLevel inventory immediately
    # before purchasing. ChairTime will purchase
    # ONLY the exact number selected by the
    # customer.
    available_records = (
        get_fresh_available_phone_records(
            location_id=location_id,
            area_code=area_code,
        )
    )

    if not available_records:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "HighLevel did not return any "
                "currently available numbers for "
                "this area code."
            ),
        )

    requested_record = (
        find_phone_record_by_number(
            phone_numbers=(
                available_records
            ),
            phone_number=(
                requested_phone_number
            ),
        )
    )

    if not requested_record:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail={
                "message": (
                    "The phone number you "
                    "selected is no longer "
                    "available. Please choose "
                    "another number."
                ),
                "requested_phone_number": (
                    requested_phone_number
                ),
            },
        )

    (
        response,
        purchased_number,
        locality,
        region,
    ) = purchase_one_highlevel_phone_number(
        location_id=location_id,
        available_record=requested_record,
        stripe_account_id=(
            stripe_account_id
        ),
        payment_method_id=(
            payment_method_id
        ),
    )

    # HighLevel reported success.
    if response.status_code < 400:
        purchase_data = response_json(
            response
        )

        purchased_phone = (
            wait_for_purchased_phone_number(
                location_id=location_id,
                phone_number=(
                    purchased_number
                ),
            )
        )

        if not purchased_phone:
            raise HTTPException(
                status_code=(
                    status.HTTP_502_BAD_GATEWAY
                ),
                detail=(
                    "HighLevel reported a "
                    "successful purchase, but "
                    "ChairTime could not verify "
                    "that the selected phone "
                    "number became active. "
                    "ChairTime stopped without "
                    "making another purchase."
                ),
            )

        return {
            "success": True,
            "purchased": True,
            "already_owned": False,
            "chairtime_shop": {
                "id": str(shop.id),
                "slug": shop.slug,
                "name": shop.name,
            },
            "location_id": location_id,
            "agent_id": agent_id,
            "requested_phone_number": (
                requested_phone_number
            ),
            "phone_number": (
                purchased_number
            ),
            "friendly_name": (
                purchased_phone.get(
                    "friendlyName"
                )
            ),
            "locality": locality,
            "region": region,
            "fallback_used": False,
            "attempted_numbers": [
                purchased_number
            ],
            "message": (
                "HighLevel phone number "
                "purchased and verified. It "
                "has not yet been routed to "
                "the AI Receptionist."
            ),
            "highlevel_purchase_confirmed": (
                bool(purchase_data)
            ),
        }

    # A server-side HighLevel error can be
    # ambiguous. Verify the exact selected number
    # before declaring failure, but NEVER try a
    # replacement number.
    if response.status_code >= 500:
        purchased_phone = (
            wait_for_purchased_phone_number(
                location_id=location_id,
                phone_number=(
                    purchased_number
                ),
            )
        )

        if purchased_phone:
            return {
                "success": True,
                "purchased": True,
                "already_owned": False,
                "chairtime_shop": {
                    "id": str(shop.id),
                    "slug": shop.slug,
                    "name": shop.name,
                },
                "location_id": (
                    location_id
                ),
                "agent_id": agent_id,
                "requested_phone_number": (
                    requested_phone_number
                ),
                "phone_number": (
                    purchased_number
                ),
                "friendly_name": (
                    purchased_phone.get(
                        "friendlyName"
                    )
                ),
                "locality": locality,
                "region": region,
                "fallback_used": False,
                "attempted_numbers": [
                    purchased_number
                ],
                "message": (
                    "The HighLevel purchase "
                    "response was ambiguous, "
                    "but ChairTime verified "
                    "that the selected number "
                    "became active. It has not "
                    "yet been routed to the AI "
                    "Receptionist."
                ),
                "highlevel_purchase_confirmed": (
                    False
                ),
            }

        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail={
                "message": (
                    "HighLevel returned an "
                    "ambiguous server error "
                    "while purchasing the "
                    "selected phone number. "
                    "ChairTime did not attempt "
                    "another number."
                ),
                "attempted_phone_number": (
                    purchased_number
                ),
                "highlevel_status": (
                    response.status_code
                ),
                "highlevel_error": (
                    safe_highlevel_error(
                        response
                    )
                ),
            },
        )

    # For any other HighLevel rejection, report
    # the failure. Never substitute another phone
    # number.
    if phone_purchase_error_is_unavailable(
        response
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail={
                "message": (
                    "The phone number you "
                    "selected is no longer "
                    "available. Please choose "
                    "another number."
                ),
                "requested_phone_number": (
                    requested_phone_number
                ),
                "highlevel_error": (
                    safe_highlevel_error(
                        response
                    )
                ),
            },
        )

    raise_highlevel_error(response)

def diagnostic_utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def redact_diagnostic_value(
    value,
    sensitive_values: list,
):
    """
    Recursively redact known sensitive values from
    diagnostic output before it is returned to Swagger
    or copied to HighLevel support.
    """
    clean_sensitive_values = [
        str(item)
        for item in sensitive_values
        if item is not None
        and str(item).strip()
    ]

    if isinstance(value, dict):
        return {
            key: redact_diagnostic_value(
                item,
                clean_sensitive_values,
            )
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            redact_diagnostic_value(
                item,
                clean_sensitive_values,
            )
            for item in value
        ]

    if isinstance(value, str):
        redacted = value

        for sensitive_value in (
            clean_sensitive_values
        ):
            redacted = redacted.replace(
                sensitive_value,
                "[REDACTED]",
            )

        return redacted

    return value


def diagnostic_response_body(
    response: requests.Response,
    sensitive_values: list,
):
    try:
        body = response.json()

    except ValueError:
        body = response.text

    return redact_diagnostic_value(
        body,
        sensitive_values,
    )


def diagnostic_response_headers(
    response: requests.Response,
) -> dict:
    """
    Return useful HighLevel response identifiers without
    exposing cookies or unrelated sensitive headers.
    """
    wanted_headers = {
        "content-type",
        "x-request-id",
        "request-id",
        "x-trace-id",
        "trace-id",
        "traceid",
        "cf-ray",
        "x-correlation-id",
        "correlation-id",
    }

    safe_headers = {}

    for key, value in (
        response.headers.items()
    ):
        if key.lower() in wanted_headers:
            safe_headers[key] = value

    return safe_headers


def diagnostic_trace_identifiers(
    response: requests.Response,
    response_body,
) -> dict:
    identifiers = {}

    header_names = (
        "x-request-id",
        "request-id",
        "x-trace-id",
        "trace-id",
        "traceid",
        "cf-ray",
        "x-correlation-id",
        "correlation-id",
    )

    for header_name in header_names:
        value = response.headers.get(
            header_name
        )

        if value:
            identifiers[
                header_name
            ] = value

    if isinstance(response_body, dict):
        body_names = (
            "traceId",
            "traceID",
            "trace_id",
            "requestId",
            "requestID",
            "request_id",
            "correlationId",
            "correlationID",
            "correlation_id",
        )

        for body_name in body_names:
            value = response_body.get(
                body_name
            )

            if value:
                identifiers[
                    body_name
                ] = value

        nested_error = (
            response_body.get("error")
        )

        if isinstance(
            nested_error,
            dict,
        ):
            for body_name in body_names:
                value = nested_error.get(
                    body_name
                )

                if value:
                    identifiers[
                        f"error.{body_name}"
                    ] = value

    return identifiers


def sanitized_purchase_headers(
    headers: dict,
) -> dict:
    """
    HighLevel support asked for all request headers except
    the access token. Authorization is intentionally omitted.
    """
    return {
        key: value
        for key, value in headers.items()
        if key.lower()
        != "authorization"
    }


def sanitized_purchase_payload(
    payload: dict,
) -> dict:
    safe_payload = dict(payload)

    if "stripeAccountId" in safe_payload:
        safe_payload[
            "stripeAccountId"
        ] = "[REDACTED]"

    if "paymentMethodId" in safe_payload:
        safe_payload[
            "paymentMethodId"
        ] = "[REDACTED]"

    return safe_payload


def build_sanitized_purchase_curl(
    purchase_url: str,
    headers: dict,
    payload: dict,
) -> str:
    safe_headers = (
        sanitized_purchase_headers(
            headers
        )
    )

    safe_payload = (
        sanitized_purchase_payload(
            payload
        )
    )

    parts = [
        "curl --request POST",
        f"'{purchase_url}'",
    ]

    for key, value in (
        safe_headers.items()
    ):
        parts.append(
            (
                "--header "
                f"'{key}: {value}'"
            )
        )

    payload_json = json.dumps(
        safe_payload,
        separators=(",", ":"),
    )

    parts.append(
        (
            "--data-raw "
            f"'{payload_json}'"
        )
    )

    return " \\\n  ".join(parts)


def diagnostic_available_record_summary(
    record: dict,
) -> dict:
    return {
        "phone_number": (
            record.get("phoneNumber")
            or record.get("number")
        ),
        "friendly_name": (
            record.get("friendlyName")
        ),
        "locality": (
            record.get("locality")
            or record.get("city")
        ),
        "region": (
            record.get("region")
            or record.get("state")
        ),
        "capabilities": (
            record.get("capabilities")
        ),
    }


def diagnostic_verify_active_number(
    location_id: str,
    phone_number: str,
) -> dict:
    """
    Verification only. This does not purchase, route,
    assign, or modify the ChairTime shop record.
    """
    try:
        _, active_phone_numbers = (
            get_location_phone_numbers(
                location_id=location_id,
            )
        )

        matched_phone = (
            find_phone_record_by_number(
                phone_numbers=(
                    active_phone_numbers
                ),
                phone_number=(
                    phone_number
                ),
            )
        )

        return {
            "verification_completed": True,
            "number_found_in_location": bool(
                matched_phone
            ),
            "phone_number": (
                phone_number
            ),
            "active_record": (
                diagnostic_available_record_summary(
                    matched_phone
                )
                if matched_phone
                else None
            ),
        }

    except HTTPException as exc:
        return {
            "verification_completed": False,
            "number_found_in_location": None,
            "phone_number": phone_number,
            "verification_error": (
                redact_diagnostic_value(
                    exc.detail,
                    [],
                )
            ),
        }

    except Exception as exc:
        return {
            "verification_completed": False,
            "number_found_in_location": None,
            "phone_number": phone_number,
            "verification_error": {
                "exception_type": (
                    type(exc).__name__
                ),
                "message": str(exc)[:500],
            },
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
    TEMPORARY HIGHLEVEL SUPPORT DIAGNOSTIC.

    This endpoint performs exactly:

        1. ONE HighLevel available-number search.
        2. Selects the first valid number returned.
        3. Immediately makes ONE purchase request for
           that exact number.
        4. Makes NO purchase retry.
        5. Makes NO fallback-number purchase.
        6. Checks whether that exact number became active.
        7. Does NOT route the number to the Voice AI agent.
        8. Does NOT update shop.highlevel_phone_number.

    The returned evidence is sanitized for HighLevel
    support. Authorization and payment identifiers are
    never returned.
    """
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.ai_voice_enabled:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "AI Receptionist is not enabled "
                "for this ChairTime subscription."
            ),
        )

    agent_id = str(
        shop.highlevel_agent_id or ""
    ).strip()

    if not agent_id:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Set up the AI Receptionist "
                "before running the phone "
                "purchase diagnostic."
            ),
        )

    clean_area_code = "".join(
        character
        for character in str(
            area_code or ""
        )
        if character.isdigit()
    )

    if len(clean_area_code) != 3:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "Area code must contain "
                "exactly 3 digits."
            ),
        )

    location_id = (
        production_location_id(shop)
    )

    (
        stripe_account_id,
        payment_method_id,
    ) = get_phone_purchase_credentials()

    sensitive_values = [
        get_highlevel_api_token(),
        stripe_account_id,
        payment_method_id,
    ]

    # -------------------------------------------------
    # STEP 1
    # Perform ONE availability search using the exact
    # same HighLevel endpoint and parameters proven by
    # ChairTime's normal /phone-numbers/available route.
    # -------------------------------------------------

    search_path = (
        f"/phone-system/numbers/location/"
        f"{location_id}/available"
    )

    search_url = (
        f"{HIGHLEVEL_API_BASE_URL}"
        f"{search_path}"
    )

    search_params = {
        "firstPart": clean_area_code,
        "lastPart": "",
        "anywhere": "",
        "numberTypes": "local",
        "smsEnabled": True,
        "mmsEnabled": True,
        "voiceEnabled": True,
        "countryCode": "US",
    }

    search_headers = (
        highlevel_voice_headers()
    )

    search_utc_timestamp = (
        diagnostic_utc_timestamp()
    )

    try:
        search_response = requests.get(
            search_url,
            headers=search_headers,
            params=search_params,
            timeout=20,
        )

    except requests.RequestException as exc:
        return {
            "success": False,
            "diagnostic_stage": (
                "availability_search"
            ),
            "purchase_attempted": False,
            "purchase_attempt_count": 0,
            "search_utc_timestamp": (
                search_utc_timestamp
            ),
            "location_id": location_id,
            "area_code": clean_area_code,
            "search_request": {
                "method": "GET",
                "url": search_url,
                "params": search_params,
                "headers": (
                    sanitized_purchase_headers(
                        search_headers
                    )
                ),
            },
            "search_error": {
                "exception_type": (
                    type(exc).__name__
                ),
                "message": str(exc)[:500],
            },
        }

    search_body = (
        diagnostic_response_body(
            search_response,
            sensitive_values,
        )
    )

    search_evidence = {
        "utc_timestamp": (
            search_utc_timestamp
        ),
        "method": "GET",
        "url": search_url,
        "params": search_params,
        "headers": (
            sanitized_purchase_headers(
                search_headers
            )
        ),
        "status_code": (
            search_response.status_code
        ),
        "response_headers": (
            diagnostic_response_headers(
                search_response
            )
        ),
        "trace_identifiers": (
            diagnostic_trace_identifiers(
                search_response,
                search_body,
            )
        ),
        "raw_response": search_body,
    }

    if search_response.status_code >= 400:
        return {
            "success": False,
            "diagnostic_stage": (
                "availability_search"
            ),
            "purchase_attempted": False,
            "purchase_attempt_count": 0,
            "chairtime_shop": {
                "id": str(shop.id),
                "slug": shop.slug,
                "name": shop.name,
            },
            "location_id": location_id,
            "area_code": clean_area_code,
            "search": search_evidence,
            "message": (
                "The HighLevel availability "
                "search failed. No purchase "
                "request was made."
            ),
        }

    if not isinstance(
        search_body,
        dict,
    ):
        return {
            "success": False,
            "diagnostic_stage": (
                "availability_search"
            ),
            "purchase_attempted": False,
            "purchase_attempt_count": 0,
            "chairtime_shop": {
                "id": str(shop.id),
                "slug": shop.slug,
                "name": shop.name,
            },
            "location_id": location_id,
            "area_code": clean_area_code,
            "search": search_evidence,
            "message": (
                "HighLevel returned an "
                "unexpected availability "
                "response. No purchase "
                "request was made."
            ),
        }

    available_records = (
        extract_available_phone_records(
            search_body
        )
    )

    if not available_records:
        return {
            "success": False,
            "diagnostic_stage": (
                "availability_search"
            ),
            "purchase_attempted": False,
            "purchase_attempt_count": 0,
            "chairtime_shop": {
                "id": str(shop.id),
                "slug": shop.slug,
                "name": shop.name,
            },
            "location_id": location_id,
            "area_code": clean_area_code,
            "search": search_evidence,
            "message": (
                "HighLevel returned no usable "
                "available phone numbers. No "
                "purchase request was made."
            ),
        }

    # Select the first record from THIS SAME search.
    # There is deliberately no second availability
    # refresh between selection and purchase.
    selected_record = (
        available_records[0]
    )

    selected_phone_number = (
        normalize_us_phone_number(
            str(
                selected_record.get(
                    "phoneNumber"
                )
                or selected_record.get(
                    "number"
                )
                or ""
            )
        )
    )

    locality = str(
        selected_record.get("locality")
        or selected_record.get("city")
        or ""
    ).strip()

    region = str(
        selected_record.get("region")
        or selected_record.get("state")
        or ""
    ).strip()

    if not locality or not region:
        return {
            "success": False,
            "diagnostic_stage": (
                "availability_search"
            ),
            "purchase_attempted": False,
            "purchase_attempt_count": 0,
            "chairtime_shop": {
                "id": str(shop.id),
                "slug": shop.slug,
                "name": shop.name,
            },
            "location_id": location_id,
            "area_code": clean_area_code,
            "search": search_evidence,
            "selected_number": (
                diagnostic_available_record_summary(
                    selected_record
                )
            ),
            "message": (
                "The first available number "
                "did not include the locality "
                "and region required by the "
                "HighLevel purchase request. "
                "No purchase request was made."
            ),
        }

    selected_number_evidence = {
        "phone_number": (
            selected_phone_number
        ),
        "locality": locality,
        "region": region,
        "returned_by_immediately_preceding_search": (
            True
        ),
        "search_result_index": 0,
        "search_result_count": len(
            available_records
        ),
    }

    # -------------------------------------------------
    # STEP 2
    # Immediately make ONE purchase request for the
    # exact first number returned above.
    # -------------------------------------------------

    fingerprint_id = str(
        int(time.time() * 1000)
    )

    purchase_url = (
        f"{HIGHLEVEL_API_BASE_URL}"
        f"/phone-system/numbers/location/"
        f"{location_id}/purchase"
    )

    purchase_headers = (
        highlevel_phone_purchase_headers()
    )

    purchase_payload = {
        "phoneNumber": (
            selected_phone_number
        ),
        "addressSid": "",
        "bundleSid": "",
        "countryCode": "US",
        "numberType": "local",
        "paymentIntentId": None,
        "stripeAccountId": (
            stripe_account_id
        ),
        "paymentMethodId": (
            payment_method_id
        ),
        "locality": locality,
        "region": region,
        "fingerprintId": (
            fingerprint_id
        ),
        "skipLocationKYC": False,
    }

    safe_purchase_headers = (
        sanitized_purchase_headers(
            purchase_headers
        )
    )

    safe_purchase_payload = (
        sanitized_purchase_payload(
            purchase_payload
        )
    )

    sanitized_curl = (
        build_sanitized_purchase_curl(
            purchase_url=(
                purchase_url
            ),
            headers=purchase_headers,
            payload=purchase_payload,
        )
    )

    purchase_utc_timestamp = (
        diagnostic_utc_timestamp()
    )

    try:
        # IMPORTANT:
        # Exactly ONE purchase request.
        # No retry and no fallback number.
        purchase_response = requests.post(
            purchase_url,
            headers=purchase_headers,
            json=purchase_payload,
            timeout=20,
        )

    except requests.RequestException as exc:
        verification = (
            diagnostic_verify_active_number(
                location_id=location_id,
                phone_number=(
                    selected_phone_number
                ),
            )
        )

        return {
            "success": False,
            "diagnostic_stage": (
                "purchase_request"
            ),
            "purchase_attempted": True,
            "purchase_attempt_count": 1,
            "chairtime_shop": {
                "id": str(shop.id),
                "slug": shop.slug,
                "name": shop.name,
            },
            "location_id": location_id,
            "area_code": clean_area_code,
            "search": search_evidence,
            "selected_number": (
                selected_number_evidence
            ),
            "purchase": {
                "utc_timestamp": (
                    purchase_utc_timestamp
                ),
                "method": "POST",
                "url": purchase_url,
                "headers": (
                    safe_purchase_headers
                ),
                "json_body": (
                    safe_purchase_payload
                ),
                "sanitized_curl": (
                    sanitized_curl
                ),
                "request_exception": {
                    "exception_type": (
                        type(exc).__name__
                    ),
                    "message": (
                        redact_diagnostic_value(
                            str(exc)[:1000],
                            sensitive_values,
                        )
                    ),
                },
            },
            "post_attempt_verification": (
                verification
            ),
            "message": (
                "The single HighLevel purchase "
                "request encountered a connection "
                "exception. ChairTime did not retry "
                "and did not attempt another number."
            ),
        }

    purchase_body = (
        diagnostic_response_body(
            purchase_response,
            sensitive_values,
        )
    )

    purchase_response_headers = (
        diagnostic_response_headers(
            purchase_response
        )
    )

    trace_identifiers = (
        diagnostic_trace_identifiers(
            purchase_response,
            purchase_body,
        )
    )

    # -------------------------------------------------
    # STEP 3
    # Verify whether the exact attempted number became
    # active. This is a read-only check and does not
    # purchase or route anything.
    # -------------------------------------------------

    verification = (
        diagnostic_verify_active_number(
            location_id=location_id,
            phone_number=(
                selected_phone_number
            ),
        )
    )

    purchase_succeeded = bool(
        purchase_response.status_code < 400
        or verification.get(
            "number_found_in_location"
        )
        is True
    )

    evidence = {
        "success": purchase_succeeded,
        "diagnostic_stage": "complete",
        "purchase_attempted": True,
        "purchase_attempt_count": 1,
        "no_purchase_retry_performed": True,
        "no_fallback_number_attempted": True,
        "phone_number_routed_to_agent": False,
        "chairtime_phone_number_updated": False,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "location_id": location_id,
        "area_code": clean_area_code,
        "agent_id": agent_id,
        "search": search_evidence,
        "selected_number": (
            selected_number_evidence
        ),
        "purchase": {
            "utc_timestamp": (
                purchase_utc_timestamp
            ),
            "method": "POST",
            "url": purchase_url,
            "headers": (
                safe_purchase_headers
            ),
            "json_body": (
                safe_purchase_payload
            ),
            "sanitized_curl": (
                sanitized_curl
            ),
            "status_code": (
                purchase_response.status_code
            ),
            "response_headers": (
                purchase_response_headers
            ),
            "trace_identifiers": (
                trace_identifiers
            ),
            "raw_response": (
                purchase_body
            ),
        },
        "post_attempt_verification": (
            verification
        ),
    }

    if purchase_succeeded:
        evidence["message"] = (
            "The single HighLevel purchase "
            "attempt appears to have succeeded. "
            "ChairTime made no retry, did not "
            "purchase a fallback number, did not "
            "route the number, and did not update "
            "the shop's stored phone number."
        )

    else:
        evidence["message"] = (
            "The single HighLevel purchase "
            "attempt did not result in the exact "
            "selected number becoming active. "
            "ChairTime made no retry and did not "
            "attempt another number."
        )

    return evidence


@router.get(
    "/phone-system/internal-host-test"
)
def test_highlevel_internal_phone_host(
    current_user=Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    shop = get_current_shop(
        db=db,
        current_user=current_user,
    )

    require_owner(current_user)

    require_shop_agent(
        shop,
        shop.highlevel_agent_id,
    )

    location_id = (
        production_location_id(shop)
    )

    url = (
        "https://backend.leadconnectorhq.com"
        f"/phone-system/numbers/location/"
        f"{location_id}"
    )

    headers = highlevel_voice_headers()

    try:
        response = requests.get(
            url,
            headers=headers,
            params={
                "page": 1,
                "pageSize": 100,
                "skipNumberPool": True,
            },
            timeout=20,
        )

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail={
                "message": (
                    "Could not connect to the "
                    "HighLevel internal phone host."
                ),
                "exception_type": (
                    type(exc).__name__
                ),
            },
        )

    try:
        body = response.json()

    except ValueError:
        body = (
            response.text[:3000]
        )

    return {
        "success": response.ok,
        "status_code": (
            response.status_code
        ),
        "location_id": location_id,
        "response": body,
    }
