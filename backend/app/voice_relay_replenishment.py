"""Keep one verified unassigned Twilio relay available in production."""
import logging
import os

from fastapi import HTTPException
from sqlalchemy import text

from app.database import SessionLocal
from app.voice_relay_mode import production_relay_enabled
from app.voice_relay_models import DayTelloVoiceRelayReservePurchase
from app.voice_relay_provider import VoiceRelayNumberProvider
from app.voice_relay_provisioning import _check_number_conflicts

logger = logging.getLogger(__name__)


def reserve_replenishment_enabled():
    return (
        production_relay_enabled()
        and os.getenv("DAYTELLO_VOICE_RELAY_AUTO_REPLENISH_ENABLED") == "true"
        and os.getenv("DAYTELLO_VOICE_RELAY_PURCHASE_ENABLED") == "true"
    )


def ensure_production_relay_reserve():
    if not reserve_replenishment_enabled():
        return
    with SessionLocal() as db:
        if db.get_bind().dialect.name != "postgresql":
            raise HTTPException(503, "Relay replenishment requires PostgreSQL")
        db.execute(text("SELECT pg_advisory_xact_lock(193720337, 1)"))
        provider = VoiceRelayNumberProvider()
        pending = db.get(DayTelloVoiceRelayReservePurchase, "production")
        if pending is not None:
            if not provider.find_verified_reserve(pending.relay_number):
                raise HTTPException(503, "Production relay purchase requires reconciliation")
            db.delete(pending)
            db.flush()
        for number in provider.list_reserved_relay_numbers():
            try:
                _check_number_conflicts(db, None, number)
                if provider.find_verified_reserve(number):
                    db.commit()
                    return
            except HTTPException as exc:
                if exc.status_code != 409:
                    raise

        number = provider.prepare_reserve_purchase()
        db.add(DayTelloVoiceRelayReservePurchase(id="production", relay_number=number))
        # Persist the exact purchase intent before contacting Twilio. A restart
        # or timeout can reconcile this number without ordering another one.
        db.commit()
        provider.purchase_reserve(number)
        db.execute(text("SELECT pg_advisory_xact_lock(193720337, 1)"))
        pending = db.get(DayTelloVoiceRelayReservePurchase, "production")
        if pending is not None and pending.relay_number == number:
            db.delete(pending)
        db.commit()


def replenish_production_relay_reserve():
    try:
        ensure_production_relay_reserve()
    except Exception:
        logger.exception("Production relay reserve replenishment failed")
