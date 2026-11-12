"""Email-based password recovery for existing DayTello accounts."""

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from html import escape

import httpx
import redis
from sqlalchemy import Column, DateTime, ForeignKey, String, update

from app.database import Base, SessionLocal
from app.models import User

logger = logging.getLogger(__name__)
TOKEN_LIFETIME = timedelta(minutes=20)


class PasswordReset(Base):
    __tablename__ = "user_password_resets"

    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    token_hash = Column(String(64), unique=True)
    account_hash = Column(String(64))
    expires_at = Column(DateTime)
    completed_at = Column(DateTime)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _account_hash(user):
    return _digest(f"{user.email}\n{user.password_hash}")


def session_fingerprint(user, secret):
    return hmac.new(secret.encode(), f"session:{user.password_hash}".encode(), "sha256").hexdigest()


def allow_reset_request(email):
    # Apply the same limits to every address before looking up an account.
    with redis.from_url(
        os.environ["REDIS_URL"], socket_connect_timeout=2, socket_timeout=2
    ) as client:
        minute = int(datetime.now(timezone.utc).timestamp()) // 60
        key = f"daytello:password-reset:minute:{minute}"
        with client.pipeline() as pipeline:
            count, _ = pipeline.incr(key).expire(key, 120).execute()
        if count > 60:
            return False
        return bool(client.set(
            f"daytello:password-reset:email:{_digest(email)}", "1", ex=120, nx=True
        ))


def issue_password_reset(email):
    try:
        with SessionLocal() as db:
            user = db.query(User).filter_by(email=email, is_active=True).with_for_update().one_or_none()
            if user is None:
                return

            token = secrets.token_urlsafe(32)
            delivery = db.get(PasswordReset, user.id)
            if delivery is None:
                delivery = PasswordReset(user_id=user.id)
                db.add(delivery)
            delivery.token_hash = _digest(token)
            delivery.account_hash = _account_hash(user)
            delivery.expires_at = _now() + TOKEN_LIFETIME
            db.commit()

        # Keep the token out of HTTP request URLs and web server access logs.
        link = f"https://www.daytello.com/login/reset-password#token={token}"
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
            json={
                "from": "DayTello <welcome@updates.daytello.com>",
                "reply_to": "info@daytello.com",
                "to": [email],
                "subject": "Reset your DayTello password",
                "html": (
                    "<p>Someone requested a new password for your DayTello account.</p>"
                    f'<p><a href="{escape(link)}">Reset your password</a></p>'
                    "<p>This link expires in 20 minutes and can be used once. "
                    "If you did not request this, you can ignore this email.</p>"
                ),
                "text": (
                    f"Reset your DayTello password: {link}\n\n"
                    "This link expires in 20 minutes and can be used once. "
                    "If you did not request this, you can ignore this email."
                ),
            },
            timeout=8,
        )
        if not response.is_success:
            logger.warning("Password reset email returned HTTP %s", response.status_code)
    except Exception as exc:
        logger.error("Password reset email failed (%s)", type(exc).__name__)


def consume_password_reset(db, token, password, hash_password):
    token_hash = _digest(token)
    user_id = db.query(PasswordReset.user_id).filter_by(token_hash=token_hash).scalar()
    if user_id is None:
        return False
    user = db.query(User).filter_by(id=user_id, is_active=True).with_for_update().one_or_none()
    delivery = db.get(PasswordReset, user_id)
    if (
        user is None or delivery is None or delivery.token_hash != token_hash
        or delivery.expires_at <= _now() or delivery.account_hash != _account_hash(user)
    ):
        return False

    new_hash = hash_password(password)
    now = _now()
    consumed = db.execute(
        update(PasswordReset)
        .where(PasswordReset.user_id == user_id, PasswordReset.token_hash == token_hash,
               PasswordReset.expires_at > now)
        .values(token_hash=None, account_hash=None, expires_at=None, completed_at=now)
    )
    if consumed.rowcount != 1:
        db.rollback()
        return False

    changed = db.execute(
        update(User)
        .where(User.id == user_id, User.is_active.is_(True),
               User.email == user.email, User.password_hash == user.password_hash)
        .values(password_hash=new_hash)
    )
    if changed.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True
