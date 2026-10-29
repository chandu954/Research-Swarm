"""Authentication-related database models.

Split from backend/db/models.py into the backend/db/models/ package.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.db.session import Base


def _utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _uuid():
    import uuid

    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    google_id = Column(String(255), unique=True, nullable=True)
    github_id = Column(String(255), unique=True, nullable=True)
    microsoft_id = Column(String(255), unique=True, nullable=True)
    name = Column(String(255), nullable=False, default="")
    avatar_url = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(255), nullable=True)
    mfa_recovery_codes = Column(Text, nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    conversations = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    documents = relationship(
        "Document", back_populates="user", cascade="all, delete-orphan"
    )
    sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    devices = relationship(
        "UserDevice", back_populates="user", cascade="all, delete-orphan"
    )
    organization_memberships = relationship(
        "OrganizationMember", back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash = Column(String(255), nullable=False, index=True)
    device_id = Column(
        UUID(as_uuid=False),
        ForeignKey("user_devices.id", ondelete="SET NULL"),
        nullable=True,
    )
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="sessions")
    device = relationship("UserDevice", back_populates="sessions")

    __table_args__ = (
        Index("ix_user_sessions_user_active", "user_id", "is_active"),
    )


class UserDevice(Base):
    __tablename__ = "user_devices"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_name = Column(String(255), nullable=True)
    device_type = Column(String(50), nullable=True)
    trusted = Column(Boolean, default=False, nullable=False)
    trusted_at = Column(DateTime(timezone=True), nullable=True)
    last_ip = Column(String(45), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user = relationship("User", back_populates="devices")
    sessions = relationship(
        "UserSession", back_populates="device", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_user_devices_user", "user_id"),
    )
