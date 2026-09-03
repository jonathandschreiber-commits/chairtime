import os

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.routes.auth import get_current_user


router = APIRouter()

HIGHLEVEL_API_BASE_URL = "https://services.leadconnectorhq.com"
HIGHLEVEL_API_VERSION = "2021-07-28"


def get_highlevel_agency_api_token() -> str:
    token = os.getenv("HIGHLEVEL_AGENCY_API_TOKEN")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "HIGHLEVEL_AGENCY_API_TOKEN environment "
                "variable is missing."
            ),
        )

    return token.strip()


def highlevel_agency_headers() -> dict:
    return {
        "Authorization": (
            f"Bearer {get_highlevel_agency_api_token()}"
        ),
        "
