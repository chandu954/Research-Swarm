"""Organization, workspace, and project database models.

Split from backend/db/models.py into the backend/db/models/ package.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
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


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)
    owner_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    settings = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    owner = relationship("User", backref="owned_organizations")
    members = relationship(
        "OrganizationMember", back_populates="organization", cascade="all, delete-orphan"
    )
    workspaces = relationship(
        "Workspace", back_populates="organization", cascade="all, delete-orphan"
    )
    api_keys = relationship(
        "APIKey", back_populates="organization", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_organizations_slug", "slug", unique=True),
    )


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    organization_id = Column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), default="member", nullable=False)
    permissions = Column(JSON, default=dict)
    joined_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="organization_memberships")

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "user_id", name="uq_org_member"
        ),
        Index("ix_org_members_org_user", "organization_id", "user_id"),
    )


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    organization_id = Column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    settings = Column(JSON, default=dict)
    vector_db_namespace = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    owner = relationship("User", backref="owned_workspaces")
    members = relationship(
        "WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan"
    )
    organization = relationship("Organization", back_populates="workspaces")
    projects = relationship(
        "Project", back_populates="workspace", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "slug", name="uq_workspace_org_slug"
        ),
        Index("ix_workspaces_org", "organization_id"),
    )


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workspace_id = Column(
        UUID(as_uuid=False),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), default="member", nullable=False)
    permissions = Column(JSON, default=dict)
    joined_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", backref="workspace_memberships")

    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "user_id", name="uq_workspace_member"
        ),
        Index("ix_workspace_members_ws_user", "workspace_id", "user_id"),
    )


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    organization_id = Column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        UUID(as_uuid=False),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    settings = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    owner = relationship("User", backref="owned_projects")
    workspace = relationship("Workspace", back_populates="projects")
    collections = relationship(
        "Collection", back_populates="project", cascade="all, delete-orphan"
    )
    conversations = relationship(
        "Conversation", back_populates="project", cascade="all, delete-orphan"
    )
    documents = relationship(
        "Document", back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "slug", name="uq_project_ws_slug"
        ),
        Index("ix_projects_workspace", "workspace_id"),
    )
