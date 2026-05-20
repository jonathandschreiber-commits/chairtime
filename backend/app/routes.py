from datetime import timedelta, date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Barber, Service, AvailabilityRule, Appointment, Shop, BlockedTime
from app.schemas import (
    BarberCreate,
    ServiceCreate,
    AvailabilityCreate,
    AppointmentCreate,
    ShopCreate,
    BlockedTimeCreate ,
)
from app.scheduling import has_overlap, generate_available_slots

router = APIRouter()


@router.post("/barbers")
def create_barber(payload: BarberCreate, db: Session = Depends(get_db)):
    barber = Barber(**payload.model_dump())

    db.add(barber)
    db.commit()
    db.refresh(barber)

    return barber


@router.get("/barbers")
def list_barbers(db: Session = Depends(get_db)):
    return db.query(Barber).all()


@router.post("/services")
def create_service(payload: ServiceCreate, db: Session = Depends(get_db)):
    service = Service(**payload.model_dump())

    db.add(service)
    db.commit()
    db.refresh(service)

    return service


@router.get("/services")
def list_services(db: Session = Depends(get_db)):
    return db.query(Service).all()


@router.post("/availability-rules")
def create_availability_rule(
    payload: AvailabilityCreate,
    db: Session = Depends(get_db)
):
    rule = AvailabilityRule(**payload.model_dump())

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return rule


@router.get("/availability")
def get_availability(
    barber_id: str,
    service_id: str,
    target_date: date,
    db: Session = Depends(get_db),
):
    slots = generate_available_slots(
        db,
        barber_id,
        service_id,
        target_date,
    )

    return {"slots": slots}


@router.post("/appointments")
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
):
    service = db.query(Service).filter(
        Service.id == payload.service_id
    ).first()

    if not service:
        raise HTTPException(
            status_code=404,
            detail="Service not found",
        )

    end_datetime = payload.start_datetime + timedelta(
        minutes=service.duration_minutes
    )

    overlap = has_overlap(
        db,
        payload.barber_id,
        payload.start_datetime,
        end_datetime,
    )

    if overlap:
        raise HTTPException(
            status_code=409,
            detail="Time slot already booked",
        )

    appointment = Appointment(
        barber_id=payload.barber_id,
        service_id=payload.service_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        start_datetime=payload.start_datetime,
        end_datetime=end_datetime,
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return appointment


@router.get("/appointments")
def list_appointments(db: Session = Depends(get_db)):
    return db.query(Appointment).all()

@router.patch("/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: str,
    db: Session = Depends(get_db),
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id
    ).first()

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    appointment.status = "cancelled"

    db.commit()
    db.refresh(appointment)

    return appointment

@router.delete("/services")
def delete_all_services(db: Session = Depends(get_db)):
    db.query(Service).delete()
    db.commit()
    return {"message": "All services deleted"}

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

@router.post("/blocked-times")
def create_blocked_time(
    payload: BlockedTimeCreate,
    db: Session = Depends(get_db),
):
    blocked_time = BlockedTime(**payload.model_dump())

    db.add(blocked_time)
    db.commit()
    db.refresh(blocked_time)

    return blocked_time


@router.get("/blocked-times")
def list_blocked_times(db: Session = Depends(get_db)):
    return db.query(BlockedTime).all()

@router.delete("/barbers/{barber_id}")
def delete_barber(barber_id: str, db: Session = Depends(get_db)):
    barber = db.query(Barber).filter(Barber.id == barber_id).first()

    if not barber:
        raise HTTPException(status_code=404, detail="Barber not found")

    db.delete(barber)
    db.commit()

    return {"message": "Barber deleted"}


@router.delete("/services/{service_id}")
def delete_service(service_id: str, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == service_id).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    db.delete(service)
    db.commit()

    return {"message": "Service deleted"}


@router.delete("/blocked-times/{blocked_time_id}")
def delete_blocked_time(
    blocked_time_id: str,
    db: Session = Depends(get_db),
):
    blocked_time = db.query(BlockedTime).filter(
        BlockedTime.id == blocked_time_id
    ).first()

    if not blocked_time:
        raise HTTPException(status_code=404, detail="Blocked time not found")

    db.delete(blocked_time)
    db.commit()

    return {"message": "Blocked time deleted"}