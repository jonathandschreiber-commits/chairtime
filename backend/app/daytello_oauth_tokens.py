"""Fail-closed HighLevel OAuth token refresh for the test voicemail integration.

No public route: callers within backend use get_valid_access_token().
The refresh token is rotated only after the response passes all checks.
"""
from datetime import timedelta

import httpx
from cryptography.fernet import InvalidToken
from sqlalchemy.orm import Session

from app.routes.daytello_voicemail_oauth import (
    REQUIRED_SCOPE, TOKEN_URL, config, utc_now_naive,
)
from app.voicemail_oauth_models import DayTelloOAuthInstallation


class OAuthReconnectRequired(Exception):
    """Credentials missing, invalid or expired; require administrator reauthorization."""


def valid_refresh_payload(data: object, expected_location: str) -> bool:
    if not isinstance(data, dict):
        return False
    expires = data.get("expires_in")
    scope = data.get("scope")
    # HighLevel may omit the unchanged scope on refresh; if supplied validate it.
    if scope is not None and (
        not isinstance(scope, str) or REQUIRED_SCOPE not in scope.split()
    ):
        return False
    return (
        data.get("locationId") == expected_location
        and data.get("userType") == "Location"
        and isinstance(data.get("access_token"), str)
        and bool(data["access_token"])
        and isinstance(data.get("refresh_token"), str)
        and bool(data["refresh_token"])
        and isinstance(expires, (int, float))
        and not isinstance(expires, bool)
        and 30 <= expires <= 172800
    )


async def get_valid_access_token(db: Session) -> str:
    """Returns access token, refreshing under DB lock when near expiry.

    Call only from authenticated administrative/server-side code; never return
    the token from a public HTTP endpoint. Do not log credentials.
    """
    client_id, client_secret, location_id, cipher = config()

    installation = (
        db.query(DayTelloOAuthInstallation)
        .filter(DayTelloOAuthInstallation.location_id == location_id)
        .with_for_update()
        .first()
    )
    if not installation or REQUIRED_SCOPE not in installation.granted_scope.split():
        raise OAuthReconnectRequired("HighLevel voicemail connection is not ready")

    try:
        access_token = cipher.decrypt(
            installation.encrypted_access_token.encode("ascii")
        ).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        raise OAuthReconnectRequired("HighLevel credential cannot be decrypted")

    if installation.expires_at > utc_now_naive() + timedelta(minutes=5):
        return access_token

    try:
        refresh_token = cipher.decrypt(
            installation.encrypted_refresh_token.encode("ascii")
        ).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        raise OAuthReconnectRequired("HighLevel refresh credential cannot be decrypted")

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            result = await client.post(
                TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Version": "v3",
                },
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "user_type": "Location",
                },
            )
        if result.status_code != 200:
            raise OAuthReconnectRequired("HighLevel token refresh was rejected")
        new_data = result.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OAuthReconnectRequired("HighLevel token refresh failed") from exc

    if not valid_refresh_payload(new_data, location_id):
        raise OAuthReconnectRequired("Invalid HighLevel token refresh response")

    installation.encrypted_access_token = cipher.encrypt(
        new_data["access_token"].encode("utf-8")
    ).decode("ascii")
    installation.encrypted_refresh_token = cipher.encrypt(
        new_data["refresh_token"].encode("utf-8")
    ).decode("ascii")
    installation.expires_at = utc_now_naive() + timedelta(
        seconds=new_data["expires_in"]
    )
    if new_data.get("scope") is not None:
        installation.granted_scope = new_data["scope"]
    db.commit()
    return new_data["access_token"]
