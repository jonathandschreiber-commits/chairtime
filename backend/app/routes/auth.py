import os
import re
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.schemas import SignupCreate, UserCreate, UserLogin


router = APIRouter()

password_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

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


def normalize_slug(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")

    return slug


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(
    password: str,
    stored_hash: str,
) -> bool:
    try:
        return password_context.verify(
            password,
            stored_hash,
        )
    except (TypeError, ValueError):
        return False


def create_access_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_MINUTES
    )

    payload = {
        "sub": str(user.id),
        "shop_slug": user.shop_slug,
        "role": user.role,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


def user_response(user: User) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "shop_id": user.shop_id,
        "shop_slug": user.shop_slug,
        "role": user.role,
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
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

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user or not user.is_active:
        raise unauthorized_error

    return user


@router.post("/signup")
def signup(
    payload: SignupCreate,
    db: Session = Depends(get_db),
):
    business_name = payload.business_name.strip()
    owner_name = payload.owner_name.strip()
    email = payload.email.strip().lower()

    if not business_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business name is required.",
        )

    if not owner_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your name is required.",
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

    shop_slug = normalize_slug(business_name)

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid business name is required.",
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

    existing_shop = (
        db.query(Shop)
        .filter(Shop.slug == shop_slug)
        .first()
    )

    if existing_shop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A business with this URL already exists. "
                "Please use a slightly different business name."
            ),
        )

    business_type = payload.business_type.strip().lower()

    if not business_type:
        business_type = "service_business"

    shop = Shop(
        slug=shop_slug,
        name=business_name,
        business_type=business_type,
        phone=payload.phone,
        timezone=payload.timezone,
    )

    try:
        db.add(shop)

        # Flush creates the shop ID without permanently committing yet.
        # This lets the shop and owner be created together as one transaction.
        db.flush()

        user = User(
            shop_id=shop.id,
            shop_slug=shop.slug,
            name=owner_name,
            email=email,
            password_hash=hash_password(payload.password),
            role="owner",
            is_active=True,
        )

        db.add(user)

        db.commit()

        db.refresh(shop)
        db.refresh(user)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The account could not be created because the "
                "email address or business URL is already in use."
            ),
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The account could not be created.",
        )

    access_token = create_access_token(user)

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
        "user": user_response(user),
        "shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
            "business_type": shop.business_type,
            "phone": shop.phone,
            "timezone": shop.timezone,
        },
    }


@router.post("/register")
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()
    name = payload.name.strip()

    shop_slug = (
        payload.shop_slug.strip().lower()
        if payload.shop_slug
        else ""
    )

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

    if not shop_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shop slug is required.",
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

    user = User(
        shop_id=payload.shop_id,
        shop_slug=shop_slug,
        name=name,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The account could not be created.",
        )

    access_token = create_access_token(user)

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
        "user": user_response(user),
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
            headers={"WWW-Authenticate": "Bearer"},
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
        "user": user_response(user),
    }


@router.get("/me")
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": str(current_user.id),
        "name": current_user.name,
        "email": current_user.email,
        "shop_id": current_user.shop_id,
        "shop_slug": current_user.shop_slug,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }
