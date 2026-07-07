from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Shop
from app.schemas import ShopCreate

router = APIRouter()


@router.post("/shops")
def create_shop(payload: ShopCreate, db: Session = Depends(get_db)):
    shop = Shop(**payload.model_dump())
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return shop


@router.get("/shops")
def list_shops(db: Session = Depends(get_db)):
    return db.query(Shop).all()