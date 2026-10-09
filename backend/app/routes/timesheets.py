"""Owner-only scheduled timesheets with compensation and approved snapshots."""
import json
import hashlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Integer, Date, DateTime, Text, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import Base, get_db
from app.models import Barber, AvailabilityRule, BlockedTime, ShopBlockedTime, generate_uuid
from app.routes.auth import get_current_user
from app.timesheet_calculations import calculate_week, compensation

router = APIRouter()


class TimesheetWeek(Base):
    __tablename__ = 'timesheet_weeks'
    __table_args__ = (UniqueConstraint('shop_slug', 'week_start', name='uq_timesheet_shop_week'),)
    id = Column(String, primary_key=True, default=generate_uuid)
    shop_slug = Column(String, nullable=False, index=True)
    week_start = Column(Date, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default='draft')
    snapshot = Column(Text, nullable=False)
    updated_by = Column(String, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    approved_at = Column(DateTime, nullable=True)


class WorkerPay(BaseModel):
    barber_id: str = Field(min_length=1, max_length=100)
    paid_hours: Decimal = Field(ge=0, le=168, max_digits=5, decimal_places=2)
    hourly_rate: Decimal = Field(ge=0, le=10000, max_digits=7, decimal_places=2)
    commission: Decimal = Field(ge=0, le=1000000, max_digits=9, decimal_places=2)


class SaveWeek(BaseModel):
    revision: int = Field(ge=0)
    schedule_token: str = Field(pattern=r"^[a-f0-9]{64}$")
    workers: list[WorkerPay] = Field(max_length=500)
    approve: bool = False


class ReopenWeek(BaseModel):
    revision: int = Field(ge=1)


def owner_shop(shop_slug, user):
    if str(user.role or '').lower() != 'owner' or str(user.shop_slug or '').lower() != shop_slug.lower():
        raise HTTPException(403, 'Only this shop owner can view or change timesheets.')
    return shop_slug.lower()


def valid_week(value):
    if value.weekday() != 0:
        raise HTTPException(400, 'Choose a Monday for the week start.')
    if not 2020 <= value.year <= 2100:
        raise HTTPException(400, 'Choose a week between 2020 and 2100.')
    return value


def saved_week(db, slug, week, lock=False):
    query = db.query(TimesheetWeek).filter(TimesheetWeek.shop_slug == slug, TimesheetWeek.week_start == week)
    return (query.with_for_update() if lock else query).first()


def build_report(db, slug, week, saved=None):
    if saved and saved.status == 'approved':
        result = json.loads(saved.snapshot)
    else:
        settings = {r['barber_id']: r for r in json.loads(saved.snapshot)['workers']} if saved else {}
        # Carry the last saved rate forward; additional paid hours and commission are weekly.
        previous = db.query(TimesheetWeek).filter(TimesheetWeek.shop_slug == slug,
                    TimesheetWeek.week_start < week).order_by(TimesheetWeek.week_start.desc()).first()
        rates = {r['barber_id']: r['hourly_rate'] for r in json.loads(previous.snapshot)['workers']} if previous else {}
        workers = db.query(Barber).filter(Barber.shop_slug == slug).order_by(Barber.name, Barber.id).all()
        ids = [w.id for w in workers]
        rules = db.query(AvailabilityRule).filter(AvailabilityRule.barber_id.in_(ids),
                    (AvailabilityRule.shop_slug == slug) | AvailabilityRule.shop_slug.is_(None)).all() if ids else []
        start, end = datetime.combine(week, datetime.min.time()), datetime.combine(week+timedelta(days=7), datetime.min.time())
        staff_blocks = db.query(BlockedTime).filter(BlockedTime.barber_id.in_(ids),
                    (BlockedTime.shop_slug == slug) | BlockedTime.shop_slug.is_(None),
                    BlockedTime.start_datetime < end, BlockedTime.end_datetime > start).all() if ids else []
        shop_blocks = db.query(ShopBlockedTime).filter(ShopBlockedTime.shop_slug == slug,
                    ShopBlockedTime.start_datetime < end, ShopBlockedTime.end_datetime > start).all()
        result = {'shop_slug': slug, 'week_start': week.isoformat(),
                  'week_end': (week+timedelta(days=6)).isoformat(), 'workers': []}
        for worker in workers:
            blocks = [{'start': b.start_datetime, 'end': b.end_datetime, 'reason': b.reason,
                       'scope': 'Shop' if isinstance(b, ShopBlockedTime) else 'Staff'}
                      for b in [*shop_blocks, *(b for b in staff_blocks if b.barber_id == worker.id)]]
            base = calculate_week(week, [r for r in rules if r.barber_id == worker.id], blocks)
            setting = settings.get(worker.id, {})
            result['workers'].append(compensation({**base, 'barber_id': worker.id, 'name': worker.name,
                 'timezone': worker.timezone or 'America/New_York'}, setting.get('paid_hours', '0'),
                 setting.get('hourly_rate', rates.get(worker.id, '0')), setting.get('commission', '0')))
    basis = [{k: w[k] for k in ('barber_id', 'name', 'timezone', 'days')} for w in result['workers']]
    schedule_token = hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()
    return {**result, 'schedule_token': schedule_token, 'revision': saved.revision if saved else 0,
            'status': saved.status if saved else 'draft',
            'updated_at': saved.updated_at.isoformat()+'Z' if saved else None,
            'approved_at': saved.approved_at.isoformat()+'Z' if saved and saved.approved_at else None}


@router.get('/{shop_slug}')
def report(shop_slug: str, week_start: date, response: Response,
           user=Depends(get_current_user), db: Session=Depends(get_db)):
    slug = owner_shop(shop_slug, user)
    week = valid_week(week_start)
    response.headers['Cache-Control'] = 'no-store'
    return build_report(db, slug, week, saved_week(db, slug, week))


@router.put('/{shop_slug}')
def save(shop_slug: str, week_start: date, payload: SaveWeek,
         user=Depends(get_current_user), db: Session=Depends(get_db)):
    slug, week = owner_shop(shop_slug, user), valid_week(week_start)
    existing = saved_week(db, slug, week, True)
    if (existing.revision if existing else 0) != payload.revision:
        raise HTTPException(409, 'This week changed in another window. Reload before saving.')
    if existing and existing.status == 'approved':
        raise HTTPException(409, 'Reopen this approved week before editing.')
    result = build_report(db, slug, week, existing)
    if payload.schedule_token != result['schedule_token']:
        raise HTTPException(409, 'Scheduled hours or blocked time changed. Reload and review this week before saving.')
    by_id = {w.barber_id: w for w in payload.workers}
    if len(by_id) != len(payload.workers) or set(by_id) != {w['barber_id'] for w in result['workers']}:
        raise HTTPException(409, 'The staff list changed or contains an invalid worker. Reload before saving.')
    result['workers'] = [compensation(w, str(by_id[w['barber_id']].paid_hours),
                          str(by_id[w['barber_id']].hourly_rate), str(by_id[w['barber_id']].commission))
                         for w in result['workers']]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    record = existing or TimesheetWeek(shop_slug=slug, week_start=week)
    record.revision = payload.revision+1
    record.status = 'approved' if payload.approve else 'draft'
    record.snapshot = json.dumps(result)
    record.updated_by, record.updated_at = user.id, now
    record.approved_at = now if payload.approve else None
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This week was saved in another window. Reload before saving.')
    return build_report(db, slug, week, record)


@router.post('/{shop_slug}/reopen')
def reopen(shop_slug: str, week_start: date, payload: ReopenWeek,
           user=Depends(get_current_user), db: Session=Depends(get_db)):
    slug, week = owner_shop(shop_slug, user), valid_week(week_start)
    record = saved_week(db, slug, week, True)
    if not record or record.revision != payload.revision or record.status != 'approved':
        raise HTTPException(409, 'This approved week changed. Reload before reopening.')
    record.status, record.approved_at = 'draft', None
    record.revision += 1
    record.updated_by, record.updated_at = user.id, datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return build_report(db, slug, week, record)
