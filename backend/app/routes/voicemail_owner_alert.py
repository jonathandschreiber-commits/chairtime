"""Test-only owner voicemail SMS and authenticated audio proxy.

All SMS is disabled by default; routing must be explicit per voicemail number.
"""
import logging
import os
import re

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.routes.reminders import send_highlevel_sms
from app.voicemail_models import DayTelloVoicemailEvent
from app.voicemail_owner_links import (
    decode_recording_link, make_recording_link, owner_phone_for_test_shop,
)

router = APIRouter()
log = logging.getLogger(__name__)
SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
MAX_RECORDING_BYTES = 15 * 1024 * 1024


def send_owner_voicemail_alert(location_id: str, message_id: str, shop_slug: str,
                               shop_name: str, shop_id: str, caller: str | None):
    """Only the webhook invokes this after committing a unique receipt."""
    status = "failed"
    try:
        recipient = owner_phone_for_test_shop(shop_slug)
        if not recipient:
            return
        link = make_recording_link(location_id, message_id, shop_id)
        text = f"DayTello TEST: New voicemail for {shop_name}. "
        if isinstance(caller, str) and re.fullmatch(r"\\+[1-9][0-9]{7,14}", caller):
            text += f"Caller: {caller}. "
        text += "Listen: " + link
        result = send_highlevel_sms(
            recipient, text, shop_id=shop_id, shop_slug=shop_slug,
            purpose="voicemail-owner-notification", source_id=message_id
        )
        status = "sent" if result.get("success") else "failed"
    except Exception:
        log.exception("DayTello test voicemail owner notification failed")
    finally:
        with SessionLocal() as session:
            event = session.get(DayTelloVoicemailEvent, (location_id, message_id))
            if event and event.notification_status == "queued":
                event.notification_status = status
                session.commit()


@router.get("/daytello/voicemail/listen/{token}")
async def listen_to_voicemail(token: str):
    """Short-lived bearer URL, server-side token; never expose provider key."""
    if os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true":
        raise HTTPException(404, "Recording link unavailable")
    payload = decode_recording_link(token)
    location_id, message_id, shop_id = (
        payload["location"], payload["message"], payload["shop"]
    )
    if not SAFE_ID.fullmatch(location_id) or not SAFE_ID.fullmatch(message_id):
        raise HTTPException(404, "Recording link unavailable")
    if location_id != os.getenv("HIGHLEVEL_LOCATION_ID", "").strip():
        raise HTTPException(404, "Recording link unavailable")
    with SessionLocal() as session:
        receipt = session.get(DayTelloVoicemailEvent, (location_id, message_id))
        if not receipt or receipt.shop_id != shop_id:
            raise HTTPException(404, "Recording link unavailable")
    api_token = os.getenv("HIGHLEVEL_API_TOKEN", "").strip()
    if not api_token:
        raise HTTPException(503, "Recording service unavailable")
    url = (
        "https://services.leadconnectorhq.com/conversations/messages/"
        + message_id + "/locations/" + location_id + "/recording"
    )
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            async with client.stream(
                "GET", url, headers={
                    "Authorization": f"Bearer {api_token}",
                    "Version": "v3",
                    "Accept": "audio/x-wav",
                },
            ) as response:
                if response.status_code != 200:
                    raise HTTPException(502, "Recording is not available")
                chunks, total = [], 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_RECORDING_BYTES:
                        raise HTTPException(502, "Recording exceeds size limit")
                    chunks.append(chunk)
                if not chunks:
                    raise HTTPException(502, "Recording is empty")
                content_type = response.headers.get("content-type", "").split(";")[0]
                if content_type not in ("audio/x-wav", "audio/wav", "audio/wave",
                                        "audio/mpeg", "audio/mp3", "application/octet-stream"):
                    raise HTTPException(502, "Unexpected recording content")
                return Response(
                    content=b"".join(chunks), media_type=content_type,
                    headers={
                        "Cache-Control": "private, no-store",
                        "Content-Disposition": "inline; filename=voicemail.wav",
                        "X-Content-Type-Options": "nosniff",
                        "Referrer-Policy": "no-referrer",
                    }
                )
    except httpx.HTTPError:
        raise HTTPException(502, "Recording service unavailable")
