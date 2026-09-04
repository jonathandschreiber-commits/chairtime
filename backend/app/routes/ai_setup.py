import os
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.routes.auth import get_current_user


router = APIRouter()

HIGHLEVEL_API_BASE_URL = "https://services.leadconnectorhq.com"
HIGHLEVEL_VOICE_API_VERSION = "v3"

CHAIRTIME_PUBLIC_API_BASE_URL = os.getenv(
    "CHAIRTIME_PUBLIC_API_BASE_URL",
    "https://chairtime-production-94da.up.railway.app",
).rstrip("/")

CHAIRTIME_AVAILABILITY_URL = (
    f"{CHAIRTIME_PUBLIC_API_BASE_URL}/api/voice/availability"
)

CHAIRTIME_BOOKING_URL = (
    f"{CHAIRTIME_PUBLIC_API_BASE_URL}/api/voice/book"
)

TEST_AGENT_NAME = "ChairTime Provisioning Test"


class TenantAvailabilityRequest(BaseModel):
    service_name: str
    target_date: str
    barber_name: Optional[str] = None


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
        "agentPrompt": (
            "You are a temporary ChairTime Voice AI "
            "provisioning test agent. "
            "Use the available ChairTime actions to check "
            "real availability and book appointments. "
            "Never invent an appointment time. "
            "Never claim an appointment is booked unless "
            "the booking action confirms success."
        ),
        "language": "en-US",
        "maxCallDuration": 300,
        "sendUserIdleReminders": True,
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
        location_id=location_id,
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
                "result.slots",
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
                "result.success",
                "result.message",
                "result.appointment_id",
                "result.barber",
                "result.service",
                "result.start_datetime",
                "result.status",
                "result.confirmation_sms_sent",
                "result.confirmation_sms_error",
                "result.reminder_scheduled",
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
    """
    HighLevel sometimes returns an error even though the
    action was created or updated successfully.

    Re-read the parent agent and verify the stored action.
    """

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
def tenant_voice_availability(
    shop_slug: str,
    payload: TenantAvailabilityRequest,
    db: Session = Depends(get_db),
):
    shop = get_shop_by_slug(
        shop_slug=shop_slug,
        db=db,
    )

    barber_name = normalize_barber_name(
        payload.barber_name
    )

    request_payload = {
        "shop_slug": shop.slug,
        "service_name": payload.service_name,
        "target_date": payload.target_date,
        "barber_name": barber_name,
    }

    return chairtime_voice_request(
        url=CHAIRTIME_AVAILABILITY_URL,
        payload=request_payload,
    )


@router.post(
    "/webhook/{shop_slug}/book"
)
def tenant_voice_booking(
    shop_slug: str,
    payload: TenantBookingRequest,
    db: Session = Depends(get_db),
):
    shop = get_shop_by_slug(
        shop_slug=shop_slug,
        db=db,
    )

    barber_name = normalize_barber_name(
        payload.barber_name
    )

    request_payload = {
        "shop_slug": shop.slug,
        "service_name": payload.service_name,
        "target_date": payload.target_date,
        "start_time": payload.start_time,
        "customer_name": payload.customer_name,
        "customer_phone": payload.customer_phone,
        "barber_name": barber_name,
    }

    return chairtime_voice_request(
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
    raw_agents = extract_agents(data)

    safe_agents = [
        safe_agent_summary(agent)
        for agent in raw_agents
    ]

    return {
        "success": True,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "highlevel_location_id": location_id,
        "agent_count": len(safe_agents),
        "agents": safe_agents,
        "highlevel_total": data.get("total"),
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

    location_id = get_highlevel_location_id()

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
        "success": True,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "highlevel_location_id": location_id,
        "action": safe_action(data),
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

    webhook_url = (
        tenant_availability_webhook_url(
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
            expected_url=webhook_url,
        )
    )

    return {
        "success": True,
        "message": (
            "Tenant-safe ChairTime availability action "
            "is configured."
        ),
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "test_agent": {
            "id": agent_id,
            "agent_name": (
                agent_data.get("agentName")
                or TEST_AGENT_NAME
            ),
            "created_this_request": agent_created,
        },
        "availability_webhook": webhook_url,
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
    """
    Provision only the book_appointment action.

    This does not update check_availability.
    """

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

    #
    # Protect against accidentally creating booking before
    # availability is present.
    #
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
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The test agent does not yet have a "
                "check_availability action."
            ),
        )

    webhook_url = (
        tenant_booking_webhook_url(
            shop
        )
    )

    booking_result = create_or_update_action(
        agent_id=agent_id,
        location_id=location_id,
        action_name="book_appointment",
        payload=build_booking_action_payload(
            shop=shop,
            agent_id=agent_id,
            location_id=location_id,
        ),
        expected_url=webhook_url,
    )

    refreshed_agent = get_agent_detail(
        agent_id=agent_id,
        location_id=location_id,
    )

    return {
        "success": True,
        "message": (
            "Tenant-safe ChairTime booking action "
            "is configured."
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
        "booking_webhook": webhook_url,
        "booking_action": booking_result,
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
