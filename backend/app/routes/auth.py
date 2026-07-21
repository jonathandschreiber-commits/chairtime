import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin

router = APIRouter()

password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer()

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 60 * 24 * 7


def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")

    if not secret:
        raise RuntimeError(
            "JWT_SECRET environment variable is missing."
        )

    return secret


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return password_hash.verify(password, stored_hash)


def create_access_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_MINUTES
    )

    payload = {
        "sub": user.id,
        "shop_slug": user.shop_slug,
        "role": user.role,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: Session = Depends(get_db),
):
    unauthorized_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials,
            get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise unauthorized_error

    except InvalidTokenError:
        raise unauthorized_error

    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise unauthorized_error

    return user


@router.post("/register")
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="An account already exists for this email.",
        )

    if len(payload.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters.",
        )

    user = User(
        shop_id=payload.shop_id,
        shop_slug=payload.shop_slug,
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(user)

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "shop_slug": user.shop_slug,
            "role": user.role,
        },
    }


@router.post("/login")
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user or not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    access_token = create_access_token(user)

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "shop_slug": user.shop_slug,
            "role": user.role,
        },
    }


@router.get("/me")
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "shop_id": current_user.shop_id,
        "shop_slug": current_user.shop_slug,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }