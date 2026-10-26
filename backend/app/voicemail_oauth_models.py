"""Private, encrypted OAuth installation and one-time initiation state."""

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class DayTelloOAuthState(Base):
    __tablename__ = "daytello_oauth_states"

    state_digest = Column(String(64), primary_key=True)
    initiated_by_user_id = Column(String(128), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)


class DayTelloOAuthInstallation(Base):
    __tablename__ = "daytello_oauth_installations"

    location_id = Column(String(128), primary_key=True)
    encrypted_access_token = Column(Text, nullable=False)
    encrypted_refresh_token = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    granted_scope = Column(Text, nullable=False)
    installed_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
