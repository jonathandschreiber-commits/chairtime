import os

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.routes.auth import get_current_user


router = APIRouter()

HIGHLEVEL_API_BASE_URL = "https://services.leadconnectorhq.com"
HIGHLEVEL_VOICE_API_VERSION = "v3"

CHAIRTIME_AVAILABILITY_URL = (
    "https://chairtime-production-94da.up.railway.app"
    "/api/voice/availability"
)


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


def require_owner(current_user: User) -> None:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access is required.",
        )


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
        "id": agent.get("id"),
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


def highlevel_request(
    method: str,
    path: str,
    params: dict | None = None,
    json_body: dict | None = None,
) -> requests.Response:
    try:
        response = requests.request(
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

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": (
                    "HighLevel rejected the Voice AI "
                    "request."
                ),
                "highlevel_status": response.status_code,
                "highlevel_error": safe_highlevel_error(
                    response
                ),
            },
        )

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
        "agentName": "ChairTime Provisioning Test",
        "businessName": business_name,
        "welcomeMessage": (
            f"Thanks for calling {business_name}. "
            "How can I help you today?"
        ),
        "agentPrompt": (
            "You are a temporary ChairTime Voice AI "
            "provisioning test agent. "
            "Do not represent this agent as ready for "
            "customer calls. "
            "This agent is used only to verify ChairTime "
            "Voice AI action provisioning."
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


def build_availability_action_payload(
    shop: Shop,
    agent_id: str,
    location_id: str,
) -> dict:
    request_body = {
        "shop_slug": shop.slug,
        "service_name": "{{service_name}}",
        "target_date": "{{target_date}}",
        "barber_name": "{{barber_name}}",
    }

    body_schema = {
        "type": "object",
        "properties": {
            "service_name": {
                "type": "string",
                "description": (
                    "The service the caller wants to book. "
                    "Use the service name stated by the caller."
                ),
            },
            "target_date": {
                "type": "string",
                "description": (
                    "The appointment date requested by the "
                    "caller. Convert relative dates such as "
                    "today, tomorrow, or next Monday to "
                    "YYYY-MM-DD format."
                ),
            },
            "barber_name": {
                "type": "string",
                "description": (
                    "The requested barber or staff member. "
                    "If the caller has no preference, use "
                    "no preference."
                ),
            },
        },
        "required": [
            "service_name",
            "target_date",
            "barber_name",
        ],
    }

    return {
        "agentId": agent_id,
        "locationId": location_id,
        "actionType": "CUSTOM_ACTION",
        "name": "check_availability",
        "actionParameters": {
            "triggerPrompt": (
                "When the caller wants to book an appointment "
                "and the service, requested date, and staff "
                "preference have been collected, use this "
                "action to check ChairTime for actual "
                "available appointment times before offering "
                "times to the caller."
            ),
            "triggerMessage": (
                "Let me check what's available."
            ),
            "schemaValues": {
                "paramsValues": {},
                "requestBodyValues": {
                    "webhookUrl": {
                        "value": CHAIRTIME_AVAILABILITY_URL,
                        "mode": "manual",
                    },
                    "httpMethod": {
                        "value": "POST",
                        "mode": "manual",
                    },
                    "headers": {
                        "value": {
                            "Content-Type": "application/json",
                        },
                        "mode": "manual",
                    },
                    "apiTimeout": {
                        "value": 10,
                        "mode": "manual",
                    },
                    "retryOnFailure": {
                        "value": False,
                        "mode": "manual",
                    },
                    "useSimpleRequestBody": {
                        "value": True,
                        "mode": "manual",
                    },
                    "simpleRequestBody": {
                        "value": request_body,
                        "type": "json",
                        "mode": "manual",
                    },
                    "bodySchema": {
                        "value": body_schema,
                        "mode": "manual",
                    },
                    "selectedOutputFields": {
                        "value": [
                            "result.slots[]",
                        ],
                        "mode": "manual",
                    },
                },
            },
        },
    }

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

    raw_agents = data.get("agents")

    if not isinstance(raw_agents, list):
        raw_agents = []

    safe_agents = [
        safe_agent_summary(agent)
        for agent in raw_agents
        if isinstance(agent, dict)
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

    response = highlevel_request(
        method="GET",
        path=f"/voice-ai/agents/{agent_id}",
        params={
            "locationId": location_id,
        },
    )

    data = response_json(response)

    raw_actions = data.get("actions")

    if not isinstance(raw_actions, list):
        raw_actions = []

    actions = [
        safe_action(action)
        for action in raw_actions
        if isinstance(action, dict)
    ]

    return {
        "success": True,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "agent": {
            "id": data.get("id"),
            "agent_name": data.get("agentName"),
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
            "reminder_after_idle_seconds": data.get(
                "reminderAfterIdleTimeSeconds"
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


@router.post("/provisioning-test/availability")
def create_availability_provisioning_test(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create an isolated HighLevel Voice AI test agent and attach one
    ChairTime availability action to it.

    This endpoint intentionally does NOT modify the existing working
    ChairTime Receptionist.
    """

    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    if not shop.slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The ChairTime shop does not have a slug.",
        )

    location_id = get_highlevel_location_id()

    #
    # Step 1:
    # Create an isolated Voice AI test agent.
    #
    agent_response = highlevel_request(
        method="POST",
        path="/voice-ai/agents",
        json_body=build_test_agent_payload(
            shop=shop,
            location_id=location_id,
        ),
    )

    agent_data = response_json(agent_response)

    agent_id = agent_data.get("id")

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "HighLevel created the test agent but "
                "did not return an agent ID."
            ),
        )

    #
    # Step 2:
    # Create a modern CUSTOM_ACTION on that test agent.
    #
    action_response = highlevel_request(
        method="POST",
        path="/voice-ai/actions",
        json_body=build_availability_action_payload(
            shop=shop,
            agent_id=agent_id,
            location_id=location_id,
        ),
    )

    action_data = response_json(action_response)

    action_id = (
        action_data.get("id")
        or action_data.get("_id")
    )

    if not action_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": (
                    "HighLevel created the test agent, "
                    "but the availability action did not "
                    "return an action ID."
                ),
                "test_agent_id": agent_id,
            },
        )

    return {
        "success": True,
        "message": (
            "Isolated ChairTime Voice AI provisioning "
            "test created successfully."
        ),
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "highlevel_location_id": location_id,
        "test_agent": {
            "id": agent_id,
            "agent_name": (
                agent_data.get("agentName")
                or "ChairTime Provisioning Test"
            ),
        },
        "availability_action": {
            "id": action_id,
            "action_type": action_data.get(
                "actionType"
            ),
            "name": action_data.get("name"),
        },
        "working_receptionist_modified": False,
    }
