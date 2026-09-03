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
        "action_type": action.get("actionType"),
        "name": action.get("name"),
        "action_parameters": action.get(
            "actionParameters"
        ),
    }


def safe_agent_summary(agent: dict) -> dict:
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


def highlevel_get(
    path: str,
    params: dict | None = None,
) -> requests.Response:
    try:
        response = requests.get(
            f"{HIGHLEVEL_API_BASE_URL}{path}",
            headers=highlevel_voice_headers(),
            params=params,
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

    response = highlevel_get(
        "/voice-ai/agents",
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

    response = highlevel_get(
        f"/voice-ai/agents/{agent_id}",
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

    response = highlevel_get(
        f"/voice-ai/actions/{action_id}",
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
