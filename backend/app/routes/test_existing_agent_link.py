"""Preview-only recovery: link Bob's already-installed HighLevel agent.

Does not provision, buy phone numbers, change Voice AI actions, or enable SMS.
All provider reads must succeed before a database link is persisted.
"""
import os
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.routes.auth import get_current_user
from app.routes.ai_setup import (
    extract_agents,
    find_phone_numbers_routed_to_agent,
    get_agent_detail,
    get_location_phone_numbers,
    highlevel_request,
    production_agent_name,
    response_json,
)
from app.voicemail_models import DayTelloVoicemailShopSettings

router = APIRouter()

def verified_highlevel_read(stage, action):
    """Give an actionable failure reason without exposing provider bodies or tokens."""
    try:
        return action()
    except HTTPException as exc:
        detail = exc.detail
        code = detail.get("highlevel_status") if isinstance(detail, dict) else None
        if code in (401, 403):
            permission = (
                "voice-ai-agents.readonly" if stage == "Voice AI agent lookup"
                else "phonenumbers.read"
            )
            raise HTTPException(
                502,
                f"{stage} was denied by HighLevel (HTTP {code}). "
                f"Verify the isolated HIGHLEVEL_API_TOKEN has {permission} "
                "and is valid for the correct HighLevel sub-account.",
            ) from None
        if code:
            raise HTTPException(
                502,
                f"{stage} failed in HighLevel (HTTP {code}). "
                "No changes were made to the shop.",
            ) from None
        raise HTTPException(
            exc.status_code,
            f"{stage} could not be verified. "
            "Check the test backend HighLevel connection.",
        ) from None



@router.post("/test-link-existing-agent")
def link_existing_bob_agent(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # This endpoint must never become a general-purpose agent takeover flow.
    if (
        os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true"
        or os.getenv("RAILWAY_ENVIRONMENT_NAME") != "daytello-voicemail-test"
    ):
        raise HTTPException(404, "Not found")
    if (
        current_user.role != "owner"
        or current_user.shop_slug != "bobs-shop"
        or not current_user.shop_id
    ):
        raise HTTPException(403, "Only the existing test shop owner may link this agent")

    shop = db.query(Shop).filter(Shop.id == current_user.shop_id).one_or_none()
    location_id = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    if (
        shop is None
        or shop.slug != "bobs-shop"
        or not shop.ai_voice_enabled
        or not location_id
        or shop.highlevel_location_id != location_id
    ):
        raise HTTPException(409, "Bob's isolated AI shop is not configured")

    settings = db.get(DayTelloVoicemailShopSettings, shop.id)
    if (
        settings is None
        or settings.location_id != location_id
        or not settings.receiving_number
        or not settings.owner_phone
        or settings.notifications_enabled
    ):
        raise HTTPException(409, "Save Bob's approved notification number first")

    if shop.highlevel_agent_id:
        raise HTTPException(409, "An AI agent is already assigned to this shop")

    # Exact-name lookup only; never create an agent or accept an approximate
    # name, unknown number, or a shared agent.
    payload = verified_highlevel_read(
        "Voice AI agent lookup",
        lambda: response_json(highlevel_request(
            method="GET",
            path="/voice-ai/agents",
            params={"locationId": location_id, "page": 1, "pageSize": 50},
        )),
    )
    expected_name = production_agent_name(shop)
    candidates = [
        item for item in extract_agents(payload)
        if (item.get("agentName") or item.get("name")) == expected_name
    ]
    if len(candidates) != 1:
        raise HTTPException(409, "Bob's existing HighLevel agent was not uniquely verified")
    agent_id = str(candidates[0].get("id") or candidates[0].get("_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", agent_id):
        raise HTTPException(409, "HighLevel agent ID was not valid")
    detail = verified_highlevel_read(
        "Voice AI agent lookup",
        lambda: get_agent_detail(agent_id, location_id),
    )
    if (
        (detail.get("agentName") or detail.get("name")) != expected_name
        or (detail.get("locationId") and detail["locationId"] != location_id)
    ):
        raise HTTPException(409, "HighLevel agent details did not match Bob's Shop")

    _, numbers = verified_highlevel_read(
        "Phone-number inventory",
        lambda: get_location_phone_numbers(location_id=location_id),
    )
    matches = find_phone_numbers_routed_to_agent(numbers, agent_id)
    if len(matches) != 1:
        raise HTTPException(409, "Bob's AI phone routing could not be uniquely verified")
    ai_phone = str(matches[0].get("phoneNumber") or "").strip()
    if (
        not re.fullmatch(r"\+1[2-9][0-9]{2}[2-9][0-9]{6}", ai_phone)
        or ai_phone == settings.receiving_number
        or (shop.highlevel_phone_number and shop.highlevel_phone_number != ai_phone)
    ):
        raise HTTPException(409, "AI phone number conflicts with existing voicemail routing")

    # Lock before assignment. Ensure a different shop has not acquired this
    # HighLevel agent or number since we read the provider state.
    shop = (
        db.query(Shop)
        .filter(Shop.id == current_user.shop_id)
        .with_for_update()
        .one_or_none()
    )
    if shop is None or shop.highlevel_agent_id:
        raise HTTPException(409, "Shop's AI agent assignment changed")
    other_shops = db.query(Shop).filter(Shop.id != shop.id).all()
    if any(
        other.highlevel_agent_id == agent_id
        or ai_phone in (other.highlevel_phone_number, other.phone)
        for other in other_shops
    ):
        raise HTTPException(409, "AI agent or phone already belongs to another shop")
    shop.highlevel_agent_id = agent_id
    shop.highlevel_phone_number = ai_phone
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "AI agent assignment conflict")
    except Exception:
        db.rollback()
        raise HTTPException(502, "Could not save the verified AI agent")
    return {
        "linked": True,
        "shop_slug": shop.slug,
        "agent_name": expected_name,
        "ai_phone_number": ai_phone,
        "sms_enabled": False,
        "forwarding_verified": False,
        "message": "Existing AI agent linked. Voicemail SMS remains off pending transfer verification.",
    }
