"""Test-only, administrator-initiated HighLevel OAuth flow for voicemail.

No unattended installation, SMS, or recording access. This route is intentionally
locked to the old Railway test backend and disabled until explicitly configured.
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routes.auth import get_current_user, is_platform_admin
from app.voicemail_oauth_models import DayTelloOAuthInstallation, DayTelloOAuthState

router = APIRouter()

# Only the known ORIGINAL TEST Railway backend may complete this first
# iteration of OAuth. Do not broaden this allowlist during testing.
TEST_REDIRECT_URI = (
    "https://chairtime-production-94da.up.railway.app"
    "/api/daytello/oauth/callback"
)
AUTHORIZATION_URL = (
    "https://marketplace.leadconnectorhq.com/v2/oauth/chooselocation"
)
TOKEN_URL = "https://services.leadconnectorhq.com/oauth/token"
REQUIRED_SCOPE = "conversations/message.readonly"
MAX_CODE_LENGTH = 2048


def utc_now_naive():
    """SQLAlchemy models store UTC timestamps without timezone."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def config():
    if os.getenv("DAYTELLO_VOICEMAIL_OAUTH_ENABLED", "").lower() != "true":
        raise HTTPException(503, "DayTello test OAuth is disabled")

    redirect = os.getenv("DAYTELLO_GHL_OAUTH_REDIRECT_URI", "").strip()
    client_id = os.getenv("DAYTELLO_GHL_CLIENT_ID", "").strip()
    client_secret = os.getenv("DAYTELLO_GHL_CLIENT_SECRET", "").strip()
    location_id = os.getenv("HIGHLEVEL_LOCATION_ID", "").strip()
    encryption_key = os.getenv("DAYTELLO_OAUTH_ENCRYPTION_KEY", "").strip()
    if (
        redirect != TEST_REDIRECT_URI
        or not client_id
        or not client_secret
        or not location_id
        or not encryption_key
    ):
        raise HTTPException(503, "DayTello test OAuth is not configured")
    try:
        cipher = Fernet(encryption_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError):
        raise HTTPException(503, "DayTello test OAuth encryption invalid")
    return client_id, client_secret, location_id, cipher


def ensure_test_admin(user: User):
    if not is_platform_admin(user):
        raise HTTPException(403, "Only a DayTello platform administrator can connect OAuth")


@router.post("/daytello/oauth/start")
def begin_oauth(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Issue a single-use install URL; bearer token + platform admin required."""
    ensure_test_admin(user)
    client_id, _, _, _ = config()
    state = secrets.token_urlsafe(48)
    digest = hashlib.sha256(state.encode("ascii")).hexdigest()
    db.add(DayTelloOAuthState(
        state_digest=digest,
        initiated_by_user_id=str(user.id),
        expires_at=utc_now_naive() + timedelta(minutes=10),
    ))
    db.commit()
    url = AUTHORIZATION_URL + "?" + urlencode({
        "response_type": "code",
        "redirect_uri": TEST_REDIRECT_URI,
        "client_id": client_id,
        "scope": REQUIRED_SCOPE,
        "state": state,
    })
    return {
        "authorization_url": url,
        "expires_in_seconds": 600,
        "note": "Open only for the test HighLevel location; choose that location.",
    }


def message_page(message: str, status_code: int):
    # Static messages only, never echo query parameters or tokens.
    return HTMLResponse(
        "<!doctype html><html><head><meta name='referrer' content='no-referrer'>"
        "<title>DayTello Connection</title></head><body>"
        "<h1>DayTello voicemail connection</h1><p>" + message + "</p>"
        "</body></html>",
        status_code=status_code,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/daytello/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Consume a one-time state, exchange the code, then store encrypted tokens."""
    if error:
        return message_page("Authorization was not completed.", 400)
    if not state or len(state) > 256 or not code or len(code) > MAX_CODE_LENGTH:
        return message_page("Invalid or expired connection request.", 400)

    # Fail before consuming a state if configuration is incomplete.
    client_id, client_secret, expected_location, cipher = config()
    digest = hashlib.sha256(state.encode("utf-8")).hexdigest()
    row = (
        db.query(DayTelloOAuthState)
        .filter(DayTelloOAuthState.state_digest == digest)
        .with_for_update()
        .first()
    )
    if not row or row.consumed_at or row.expires_at < utc_now_naive():
        return message_page("Invalid or expired connection request.", 400)

    # Consume first and commit BEFORE an external HTTP call: no repeated
    # code exchange or replay if the provider is slow/unavailable.
    row.consumed_at = utc_now_naive()
    db.commit()

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.post(
                TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "user_type": "Location",
                    "code": code,
                    "redirect_uri": TEST_REDIRECT_URI,
                },
            )
        if response.status_code != 200:
            return message_page(
                "HighLevel authorization failed. Begin a new connection.", 502
            )
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return message_page(
            "Unable to verify HighLevel authorization. Begin again.", 502
        )

    if not isinstance(data, dict):
        return message_page("Invalid HighLevel authorization response.", 502)

    # Never accept an Agency token or another location's credentials.
    if (
        data.get("userType") != "Location"
        or data.get("locationId") != expected_location
        or REQUIRED_SCOPE not in str(data.get("scope", "")).split()
    ):
        return message_page(
            "Authorization did not match the required testing location and scope.",
            403,
        )

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    expires_in = data.get("expires_in")
    if (
        not isinstance(access_token, str)
        or not access_token
        or not isinstance(refresh_token, str)
        or not refresh_token
        or not isinstance(expires_in, (int, float))
        or isinstance(expires_in, bool)
        or not 30 <= expires_in <= 172800
    ):
        return message_page("Incomplete HighLevel authorization response.", 502)

    record = db.get(DayTelloOAuthInstallation, expected_location)
    if record is None:
        record = DayTelloOAuthInstallation(location_id=expected_location)
        db.add(record)
    record.encrypted_access_token = cipher.encrypt(
        access_token.encode("utf-8")
    ).decode("ascii")
    record.encrypted_refresh_token = cipher.encrypt(
        refresh_token.encode("utf-8")
    ).decode("ascii")
    record.granted_scope = str(data["scope"])
    record.expires_at = utc_now_naive() + timedelta(seconds=expires_in)
    db.commit()
    return message_page(
        "The TEST HighLevel location was connected. Voicemail SMS remains disabled.",
        200,
    )
