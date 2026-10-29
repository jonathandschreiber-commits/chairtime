import os
import re
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Security,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, Field

from app.voicemail_models import DayTelloVoicemailShopSettings
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop, User
from app.schemas import SignupCreate, UserLogin


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

    # Apostrophes should disappear rather than become
    # separators: "Mike's" -> "mikes".
    slug = re.sub(
        r"['’]",
        "",
        slug,
    )

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        slug,
    )
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
    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=ACCESS_TOKEN_MINUTES
        )
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


def is_platform_admin(user: User) -> bool:
    # Privilege is configured on the server, never by signup or a browser flag.
    allowed = {email.strip().lower() for email in
               os.getenv("PLATFORM_ADMIN_EMAILS", "").split(",") if email.strip()}
    return bool(user.is_active and str(user.email or "").strip().lower() in allowed)


def user_response(user: User) -> dict:
    role = str(
        user.role or ""
    ).strip().lower()

    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "shop_id": user.shop_id,
        "shop_slug": user.shop_slug,
        "role": role,
        "barber_id": user.barber_id,
        "can_accept_payments": (
            role == "owner"
            or bool(
                user.can_accept_payments
            )
        ),
        "is_active": user.is_active,
        "platform_admin": is_platform_admin(user),
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    unauthorized_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=(
            "Invalid or expired authentication token."
        ),
        headers={
            "WWW-Authenticate": "Bearer"
        },
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
        .filter(
            User.id == user_id
        )
        .first()
    )

    if (
        not user
        or not user.is_active
    ):
        raise unauthorized_error

    return user


@router.post("/signup")
def signup(
    payload: SignupCreate,
    db: Session = Depends(get_db),
):
    business_name = (
        payload.business_name.strip()
    )

    owner_name = (
        payload.owner_name.strip()
    )

    email = (
        payload.email.strip().lower()
    )

    if not business_name:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "Business name is required."
            ),
        )

    if not owner_name:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail="Your name is required.",
        )

    if not email:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail="Email is required.",
        )

    if len(payload.password) < 8:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "Password must be at least "
                "8 characters."
            ),
        )

    requested_slug = (
        payload.slug.strip()
        if payload.slug
        else business_name
    )

    shop_slug = normalize_slug(
        requested_slug
    )

    if not shop_slug:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "Please choose a valid "
                "business URL."
            ),
        )

    existing_user = (
        db.query(User)
        .filter(
            User.email == email
        )
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "An account already exists "
                "for this email."
            ),
        )

    existing_shop = (
        db.query(Shop)
        .filter(
            Shop.slug == shop_slug
        )
        .first()
    )

    if existing_shop:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "That business URL is already "
                "in use. Please choose a "
                "slightly different URL."
            ),
        )

    business_type = (
        payload.business_type
        .strip()
        .lower()
    )

    if not business_type:
        business_type = (
            "service_business"
        )

    shop = Shop(
        slug=shop_slug,
        name=business_name,
        business_type=business_type,
        phone=payload.phone,
        timezone=payload.timezone,
    )

    try:
        db.add(shop)

        # Flush creates the shop ID
        # without permanently committing.
        # This lets the shop and owner
        # be created together as one
        # transaction.
        db.flush()

        user = User(
            shop_id=shop.id,
            shop_slug=shop.slug,
            name=owner_name,
            email=email,
            password_hash=hash_password(
                payload.password
            ),
            role="owner",
            barber_id=None,
            can_accept_payments=False,
            is_active=True,
        )

        db.add(user)

        db.commit()

        db.refresh(shop)
        db.refresh(user)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "The account could not be "
                "created because the email "
                "address or business URL is "
                "already in use."
            ),
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The account could not "
                "be created."
            ),
        )

    access_token = create_access_token(
        user
    )

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": (
            ACCESS_TOKEN_MINUTES * 60
        ),
        "user": user_response(user),
        "shop": {
            "id": str(shop.id),
            "slug": shop.slug,
            "name": shop.name,
            "business_type": (
                shop.business_type
            ),
            "phone": shop.phone,
            "timezone": shop.timezone,
        },
    }


@router.post("/login")
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
):
    email = (
        payload.email
        .strip()
        .lower()
    )

    user = (
        db.query(User)
        .filter(
            User.email == email
        )
        .first()
    )

    if (
        not user
        or not verify_password(
            payload.password,
            user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Invalid email or password."
            ),
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    if not user.is_active:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "This account is inactive."
            ),
        )

    access_token = create_access_token(
        user
    )

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": (
            ACCESS_TOKEN_MINUTES * 60
        ),
        "user": user_response(user),
    }


@router.get("/me")
def read_current_user(
    current_user: User = Depends(
        get_current_user
    ),
):
    return user_response(
        current_user
    )


# The isolated voicemail test database contains an existing Bob's Shop
# record, including historical voicemail data, but no user created through
# signup. This is a *one-time recovery path*, not normal store onboarding.
# Never enable it for production or for arbitrary shop slugs.
class TestOwnerClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=72)
    invite_code: str = Field(min_length=1, max_length=256)


@router.post("/test-claim-existing-shop")
def test_claim_existing_shop(
    payload: TestOwnerClaim,
    db: Session = Depends(get_db),
):
    """One-use invite that attaches an owner to *existing* Bob's Shop.

    It never creates a Shop, changes voicemail routing, or grants platform
    admin privileges. No output ever contains the invitation secret.
    """
    if os.getenv("DAYTELLO_VOICEMAIL_TEST_ONLY") != "true":
        raise HTTPException(404, "Not found")

    invite = os.getenv("DAYTELLO_TEST_OWNER_INVITE_CODE", "")
    if len(invite) < 32:
        # Fail closed until a unique high-entropy invitation is supplied
        # through the isolated Railway environment.
        raise HTTPException(404, "Not found")

    # Compare fixed-size digests so arbitrary input characters are safe.
    expected = hashlib.sha256(invite.encode("utf-8")).digest()
    provided = hashlib.sha256(payload.invite_code.encode("utf-8")).digest()
    if not secrets.compare_digest(expected, provided):
        raise HTTPException(403, "Invalid invitation")

    # Check prerequisites before making any database changes.
    try:
        get_jwt_secret()
    except RuntimeError:
        raise HTTPException(503, "Test login is not configured")

    owner_name = payload.owner_name.strip()
    email = payload.email.strip().lower()
    if not owner_name or not re.fullmatch(r"[^\\s@]+@[^\\s@]+\\.[^\\s@]+", email):
        raise HTTPException(422, "Enter a valid name and email")
    if len(payload.password.encode("utf-8")) > 72:
        raise HTTPException(422, "Password must be at most 72 bytes")

    # Lock the existing shop row on PostgreSQL. Concurrent claims must
    # not create multiple owners for the same pre-existing test record.
    shop = (
        db.query(Shop)
        .filter(Shop.slug == "bobs-shop")
        .with_for_update()
        .one_or_none()
    )
    if shop is None or not shop.ai_voice_enabled:
        raise HTTPException(409, "The existing Bob's Shop is not ready")

    location_id = os.getenv("HIGHLEVEL_LOCATION_ID", "")
    prefs = db.get(DayTelloVoicemailShopSettings, shop.id)
    if (
        not location_id
        or shop.highlevel_location_id != location_id
        or prefs is None
        or prefs.location_id != location_id
        or not prefs.receiving_number
    ):
        raise HTTPException(409, "Existing voicemail configuration not verified")

    if db.query(User).filter(
        User.shop_id == shop.id, User.role == "owner"
    ).first():
        raise HTTPException(409, "Bob's Shop already has an owner")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "This email is already in use")

    user = User(
        shop_id=shop.id,
        shop_slug=shop.slug,
        name=owner_name,
        email=email,
        password_hash=hash_password(payload.password),
        role="owner",
        barber_id=None,
        can_accept_payments=False,
        is_active=True,
    )
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Unable to enroll owner; account already exists")
    except Exception:
        db.rollback()
        raise HTTPException(500, "Unable to enroll test owner")

    return {
        "success": True,
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
        "user": user_response(user),
    }
