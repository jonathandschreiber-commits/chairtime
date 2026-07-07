from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Barber
from app.schemas import BarberCreate, BarberUpdate

router = APIRouter()


@router.post("/barbers")
def create_barber(payload: BarberCreate, db: Session = Depends(get_db)):
    barber = Barber(**payload.model_dump())
    db.add(barber)
    db.commit()
    db.refresh(barber)
    return barber


@router.get("/barbers")
def list_barbers(
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Barber)

    if shop_slug:
        query = query.filter(Barber.shop_slug == shop_slug)

    return query.all()


@router.delete("/barbers/{barber_id}")
def delete_barber(barber_id: str, db: Session = Depends(get_db)):
    barber = db.query(Barber).filter(Barber.id == barber_id).first()

    if not barber:
        raise HTTPException(status_code=404, detail="Barber not found")

    db.delete(barber)
    db.commit()
    return {"message": "Barber deleted"}


@router.patch("/barbers/{barber_id}")
def update_barber(
    barber_id: str,
    payload: BarberUpdate,
    db: Session = Depends(get_db),
):
    barber = db.query(Barber).filter(Barber.id == barber_id).first()

    if not barber:
        raise HTTPException(status_code=404, detail="Barber not found")

    updates = payload.model_dump(exclude_unset=True)

    for key, value in updates.items():
        setattr(barber, key, value)

    db.commit()
    db.refresh(barber)
    return barber