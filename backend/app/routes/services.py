from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Service
from app.schemas import ServiceCreate, ServiceUpdate

router = APIRouter()


@router.post("/services")
def create_service(payload: ServiceCreate, db: Session = Depends(get_db)):
    service = Service(**payload.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("/services")
def list_services(
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Service)

    if shop_slug:
        query = query.filter(Service.shop_slug == shop_slug)

    return query.all()


@router.delete("/services")
def delete_all_services(db: Session = Depends(get_db)):
    db.query(Service).delete()
    db.commit()
    return {"message": "All services deleted"}


@router.delete("/services/{service_id}")
def delete_service(service_id: str, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == service_id).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    db.delete(service)
    db.commit()
    return {"message": "Service deleted"}


@router.patch("/services/{service_id}")
def update_service(
    service_id: str,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
):
    service = db.query(Service).filter(Service.id == service_id).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    updates = payload.model_dump(exclude_unset=True)

    for key, value in updates.items():
        setattr(service, key, value)

    db.commit()
    db.refresh(service)
    return service