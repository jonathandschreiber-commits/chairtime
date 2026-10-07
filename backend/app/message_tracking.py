"""Durable outbound attribution. Never store recipients, bodies or credentials."""
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, String
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, SessionLocal
from app.models import Shop

logger = logging.getLogger(__name__)


class OutboundMessage(Base):
    __tablename__ = "outbound_message_tracking"
    id = Column(String, primary_key=True)
    shop_id = Column(String, nullable=True, index=True)
    shop_slug = Column(String, nullable=True)
    location_id = Column(String, nullable=False)
    message_type = Column(String, nullable=False, default="SMS")
    purpose = Column(String, nullable=False)
    source_id = Column(String, nullable=True)
    status = Column(String, nullable=False)
    message_id = Column(String, nullable=True)
    conversation_id = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    __table_args__ = (Index("ix_outbound_location_message", "location_id", "message_id"),)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def begin_sms(location_id, shop_id=None, shop_slug=None, purpose="diagnostic", source_id=None):
    # Commit independently before contacting the provider. A caller rollback must
    # not erase the link for an already accepted and potentially billed message.
    with SessionLocal() as db:
        shop = None
        if shop_id or shop_slug:
            query = db.query(Shop)
            query = query.filter(Shop.id == shop_id) if shop_id else query.filter(Shop.slug == shop_slug)
            shop = query.one_or_none()
            if not shop or (shop_slug and shop.slug != shop_slug):
                raise ValueError("SMS shop identity does not match")
        identity = str(uuid.uuid4())
        db.add(OutboundMessage(id=identity, shop_id=shop.id if shop else None,
            shop_slug=shop.slug if shop else None, location_id=location_id,
            message_type="SMS", purpose=purpose[:100], source_id=source_id,
            status="sending", created_at=utc_now(), updated_at=utc_now()))
        db.commit()
        return identity


def finish_sms(identity, status, provider=None):
    provider = provider if isinstance(provider, dict) else {}
    def safe_id(key):
        value = provider.get(key)
        return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,200}", value) else None
    try:
        with SessionLocal() as db:
            row = db.get(OutboundMessage, identity)
            if not row:
                return False
            row.status = status
            row.message_id = safe_id("messageId")
            row.conversation_id = safe_id("conversationId")
            row.updated_at = utc_now()
            db.commit()
        return True
    except SQLAlchemyError:
        # Do not resend an accepted message because attribution persistence failed.
        logger.error("SMS attribution update failed for attempt %s", identity)
        return False


def sms_reference(description):
    match = re.fullmatch(r"Outbound SMS:\s*Ref-([A-Za-z0-9_-]+)\s*", description, re.I)
    return match.group(1) if match else None


def sms_shop_matches(db, location_id, descriptions, shops):
    ids = {value for text in descriptions if (value := sms_reference(text))}
    by_id = {shop.id: shop.slug for shop in shops}
    candidates = {}
    # No send-date filter: a charge may settle in a later month.
    identities = sorted(ids)
    for offset in range(0, len(identities), 400):
        for row in db.query(OutboundMessage).filter(
            OutboundMessage.location_id == location_id,
            OutboundMessage.message_type == "SMS",
            OutboundMessage.status == "accepted",
            OutboundMessage.message_id.in_(identities[offset:offset + 400]),
        ).all():
            candidates.setdefault(row.message_id, set()).add(by_id.get(row.shop_id))
    # A collision or unknown shop stays shared; never infer from a contact/phone.
    return {identity: next(iter(slugs)) for identity, slugs in candidates.items()
            if len(slugs) == 1 and None not in slugs}


def tracking_summary(db, limit=10):
    rows = db.query(OutboundMessage).order_by(OutboundMessage.created_at.desc(), OutboundMessage.id).limit(limit).all()
    return [{"attempt_id": row.id, "shop_slug": row.shop_slug,
             "purpose": row.purpose, "location_id": row.location_id,
             "message_id": row.message_id, "status": row.status,
             "created_at": row.created_at.isoformat() + "Z"} for row in rows]
