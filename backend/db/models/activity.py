"""Activity-related database models (research tasks, knowledge graph, memory, etc.).

Split from backend/db/models.py into the backend/db/models/ package.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
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


class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    conversation_id = Column(
        UUID(as_uuid=False),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        UUID(as_uuid=False),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    query = Column(Text, nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    plan = Column(JSON, default=list)
    logs = Column(JSON, default=list)
    sources = Column(JSON, default=list)
    result = Column(Text, nullable=True)
    model_usage = Column(JSON, default=dict)
    cost_estimate = Column(Float, nullable=True)
    token_count = Column(BigInteger, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(BigInteger, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="research_tasks")

    __table_args__ = (
        Index("ix_research_tasks_status", "status"),
        Index("ix_research_tasks_conversation", "conversation_id"),
        Index("ix_research_tasks_org", "organization_id"),
    )


class KnowledgeGraphNode(Base):
    __tablename__ = "knowledge_graph_nodes"

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
        nullable=True,
        index=True,
    )
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    conversation_id = Column(
        UUID(as_uuid=False),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    label = Column(String(500), nullable=False)
    entity_type = Column(String(100), nullable=True)
    properties = Column(JSON, default=dict)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_kg_nodes_org", "organization_id"),
        Index("ix_kg_nodes_conversation", "conversation_id"),
    )


class KnowledgeGraphEdge(Base):
    __tablename__ = "knowledge_graph_edges"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    organization_id = Column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_node_id = Column(
        UUID(as_uuid=False),
        ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id = Column(
        UUID(as_uuid=False),
        ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type = Column(String(100), nullable=False)
    properties = Column(JSON, default=dict)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_kg_edges_source", "source_node_id"),
        Index("ix_kg_edges_target", "target_node_id"),
    )


class Memory(Base):
    __tablename__ = "memories"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    workspace_id = Column(
        UUID(as_uuid=False),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    scope = Column(String(20), nullable=False)
    key = Column(String(255), nullable=False)
    value = Column(JSON, nullable=False)
    embedding_id = Column(String(255), nullable=True)
    importance = Column(Float, default=0.5)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "scope", "key", name="uq_memory_user_scope_key"
        ),
        Index("ix_memories_scope", "scope"),
        Index("ix_memories_org", "organization_id"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    type = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=True)
    data = Column(JSON, default=dict)
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
        Index("ix_notifications_created", "created_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

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
        nullable=True,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(255), nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_org_action", "organization_id", "action"),
        Index("ix_audit_logs_created", "created_at"),
    )


class APIKey(Base):
    __tablename__ = "api_keys"

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
    name = Column(String(255), nullable=False)
    key_prefix = Column(String(8), nullable=False)
    key_hash = Column(String(255), nullable=False)
    permissions = Column(JSON, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    organization = relationship("Organization", back_populates="api_keys")
    user = relationship("User")

    __table_args__ = (
        Index("ix_api_keys_org", "organization_id"),
    )


class BillingRecord(Base):
    __tablename__ = "billing_records"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    organization_id = Column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    workspace_id = Column(
        UUID(as_uuid=False),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    record_type = Column(String(50), nullable=False)
    tokens_in = Column(BigInteger, default=0)
    tokens_out = Column(BigInteger, default=0)
    storage_bytes = Column(BigInteger, default=0)
    api_calls = Column(Integer, default=0)
    compute_seconds = Column(Float, default=0.0)
    estimated_cost = Column(Float, default=0.0)
    currency = Column(String(3), default="USD")
    billed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_billing_org_period", "organization_id", "created_at"),
    )


class Tag(Base):
    __tablename__ = "tags"

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
        nullable=True,
        index=True,
    )
    name = Column(String(100), nullable=False)
    color = Column(String(7), default="#6366f1")
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", name="uq_tag_org_name"
        ),
    )


class TagAssignment(Base):
    __tablename__ = "tag_assignments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tag_id = Column(
        UUID(as_uuid=False),
        ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tag_id", "resource_type", "resource_id", name="uq_tag_assignment"
        ),
        Index("ix_tag_assignments_resource", "resource_type", "resource_id"),
    )


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(255), nullable=False)
    label = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "resource_type", "resource_id", name="uq_bookmark"
        ),
        Index("ix_bookmarks_user", "user_id"),
    )


class Provider(Base):
    __tablename__ = "providers"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    provider_type = Column(
        String(50), nullable=False, comment="llm, search, or embedding"
    )
    provider_key = Column(
        String(100),
        nullable=False,
        comment="Registered provider key (e.g. openrouter, duckduckgo)",
    )
    config = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)
    organization_id = Column(
        UUID(as_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_by = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_providers_org", "organization_id"),
        Index("ix_providers_type", "provider_type"),
    )
