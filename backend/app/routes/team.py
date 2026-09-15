from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Barber, User
from app.routes.auth import get_current_user, hash_password


router = APIRouter()


class TeamMemberCreate(BaseModel):
    name: str
    email: str
    password: str
    barber_id: Optional[str] = None
    can_accept_payments: bool = False


class TeamMemberUpdate(BaseModel):
    name: Optional[str] = None
    barber_id: Optional[str] = None
    can_accept_payments: Optional[bool] = None
    is_active: Optional[bool] = None


def require_owner(current_user: User) -> None:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access is required.",
        )


def team_member_response(user: User) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "shop_id": user.shop_id,
        "shop_slug": user.shop_slug,
        "barber_id": user.barber_id,
        "can_accept_payments": (
            user.role == "owner"
            or user.can_accept_payments
        ),
        "is_active": user.is_active,
        "created_at": (
            user.created_at.isoformat()
            if user.created_at
            else None
        ),
    }


def validate_barber_for_shop(
    db: Session,
    shop_slug: str,
    barber_id: Optional[str],
) -> Optional[Barber]:
    if not barber_id:
        return None

    barber = (
        db.query(Barber)
        .filter(
            Barber.id == barber_id,
            Barber.shop_slug == shop_slug,
        )
        .first()
    )

    if not barber:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The selected staff/provider does not belong "
                "to this shop."
            ),
        )

    return barber


def get_shop_team_member(
    db: Session,
    current_user: User,
    user_id: str,
) -> User:
    team_member = (
        db.query(User)
        .filter(
            User.id == user_id,
            User.shop_id == current_user.shop_id,
            User.shop_slug == current_user.shop_slug,
        )
        .first()
    )

    if not team_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found.",
        )

    return team_member


@router.get("")
def list_team_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    users = (
        db.query(User)
        .filter(
            User.shop_id == current_user.shop_id,
            User.shop_slug == current_user.shop_slug,
        )
        .order_by(
            User.role.asc(),
            User.name.asc(),
        )
        .all()
    )

    return {
        "success": True,
        "team": [
            team_member_response(user)
            for user in users
        ],
    }


@router.post("")
def create_team_member(
    payload: TeamMemberCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    name = payload.name.strip()
    email = payload.email.strip().lower()

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name is required.",
        )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required.",
        )

    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters.",
        )

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account already exists for this email.",
        )

    validate_barber_for_shop(
        db,
        current_user.shop_slug,
        payload.barber_id,
    )

    user = User(
        shop_id=current_user.shop_id,
        shop_slug=current_user.shop_slug,
        name=name,
        email=email,
        password_hash=hash_password(payload.password),
        role="staff",
        barber_id=payload.barber_id,
        can_accept_payments=payload.can_accept_payments,
        is_active=True,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The team member could not be created.",
        )

    return {
        "success": True,
        "team_member": team_member_response(user),
    }


@router.patch("/{user_id}")
def update_team_member(
    user_id: str,
    payload: TeamMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    team_member = get_shop_team_member(
        db,
        current_user,
        user_id,
    )

    if team_member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Owner access cannot be changed from "
                "the Team page."
            ),
        )

    if payload.name is not None:
        name = payload.name.strip()

        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name is required.",
            )

        team_member.name = name

    if payload.barber_id is not None:
        validate_barber_for_shop(
            db,
            current_user.shop_slug,
            payload.barber_id,
        )

        team_member.barber_id = payload.barber_id

    if payload.can_accept_payments is not None:
        team_member.can_accept_payments = (
            payload.can_accept_payments
        )

    if payload.is_active is not None:
        team_member.is_active = payload.is_active

    try:
        db.commit()
        db.refresh(team_member)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The team member could not be updated.",
        )

    return {
        "success": True,
        "team_member": team_member_response(team_member),
    }


@router.post("/{user_id}/deactivate")
def deactivate_team_member(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    team_member = get_shop_team_member(
        db,
        current_user,
        user_id,
    )

    if team_member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The shop owner cannot be deactivated here.",
        )

    team_member.is_active = False

    try:
        db.commit()
        db.refresh(team_member)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The team member could not be deactivated.",
        )

    return {
        "success": True,
        "team_member": team_member_response(team_member),
    }


@router.post("/{user_id}/activate")
def activate_team_member(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owner(current_user)

    team_member = get_shop_team_member(
        db,
        current_user,
        user_id,
    )

    if team_member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The shop owner is already active.",
        )

    team_member.is_active = True

    try:
        db.commit()
        db.refresh(team_member)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The team member could not be activated.",
        )

    return {
        "success": True,
        "team_member": team_member_response(team_member),
    }
