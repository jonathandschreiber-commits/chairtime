from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BlockedTime
from app.schemas import BlockedTimeCreate

router = APIRouter()


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
def list_blocked_times(
    shop_slug: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(BlockedTime)

    if shop_slug:
        query = query.filter(
            BlockedTime.shop_slug == shop_slug
        )

    return query.all()


@router.delete("/blocked-times/{blocked_time_id}")
def delete_blocked_time(
    blocked_time_id: str,
    db: Session = Depends(get_db),
):
    blocked_time = (
        db.query(BlockedTime)
        .filter(BlockedTime.id == blocked_time_id)
        .first()
    )

    if not blocked_time:
        raise HTTPException(
            status_code=404,
            detail="Blocked time not found",
        )

    db.delete(blocked_time)
    db.commit()

    return {
        "message": "Blocked time deleted",
    }