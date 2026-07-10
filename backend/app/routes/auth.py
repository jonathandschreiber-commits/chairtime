from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin

router = APIRouter(tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str):
    return pwd_context.verify(password, password_hash)


@router.post("/register")
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(User)
        .filter(User.email == payload.email.lower())
        .first()
    )

    if existing:
        raise HTTPException(status_code=400, detail="Email already exists.")

    user = User(
        shop_id=payload.shop_id,
        shop_slug=payload.shop_slug,
        name=payload.name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "user_id": user.id,
        "shop_slug": user.shop_slug,
    }


@router.post("/login")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .filter(User.email == payload.email.lower())
        .first()
    )

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return {
        "success": True,
        "user_id": user.id,
        "shop_slug": user.shop_slug,
        "name": user.name,
        "role": user.role,
    }