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
        "Version": HIGHLEVEL_API_VERSION,
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

@router.get("/agency")
def get_highlevel_agency(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    shop = get_current_shop(
        current_user=current_user,
        db=db,
    )

    try:
        response = requests.get(
            f"{HIGHLEVEL_API_BASE_URL}/companies/",
            headers=highlevel_agency_headers(),
            timeout=20,
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to HighLevel.",
        )

    if response.status_code >= 400:
        try:
            highlevel_error = response.json()
        except ValueError:
            highlevel_error = {
                "message": response.text[:500]
            }

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": (
                    "HighLevel rejected the agency API request."
                ),
                "highlevel_status": response.status_code,
                "highlevel_error": highlevel_error,
            },
        )

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="HighLevel returned an invalid response.",
        )

    companies = []

    if isinstance(data, dict):
        raw_companies = data.get("companies")

        if isinstance(raw_companies, list):
            companies = raw_companies

        elif data.get("id"):
            companies = [data]

    elif isinstance(data, list):
        companies = data

    safe_companies = []

    for company in companies:
        if not isinstance(company, dict):
            continue

        company_id = company.get("id")
        company_name = (
            company.get("name")
            or company.get("companyName")
        )

        if not company_id:
            continue

        safe_companies.append(
            {
                "id": company_id,
                "name": company_name,
            }
        )

    return {
        "success": True,
        "chairtime_shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
        },
        "companies": safe_companies,
        "company_count": len(safe_companies),
    }
