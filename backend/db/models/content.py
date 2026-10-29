"""Content-related database models (collection, conversation, message, document).

Split from backend/db/models.py into the backend/db/models/ package.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
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


class Collection(Base):
    __tablename__ = "collections"

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
    project_id = Column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    owner = relationship("User", backref="owned_collections")
    project = relationship("Project", back_populates="collections")

    __table_args__ = (
        Index("ix_collections_project", "project_id"),
    )


class Conversation(Base):
    __tablename__ = "conversations"

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
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    is_archived = Column(Boolean, default=False, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    is_favorited = Column(Boolean, default=False, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    visibility = Column(String(20), default="workspace", nullable=False)
    share_token = Column(String(64), unique=True, nullable=True)
    source_conversation_id = Column(UUID(as_uuid=False), nullable=True)
    agent_metrics_cache = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    user = relationship("User", back_populates="conversations")
    project = relationship("Project", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    research_tasks = relationship(
        "ResearchTask", back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_conversations_user_updated", "user_id", "updated_at"),
        Index("ix_conversations_org", "organization_id"),
        Index("ix_conversations_workspace", "workspace_id"),
        Index("ix_conversations_project", "project_id"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    conversation_id = Column(
        UUID(as_uuid=False),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(JSON, default=list)
    metadata_ = Column("metadata", JSON, default=dict)
    parent_id = Column(UUID(as_uuid=False), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )


class Document(Base):
    __tablename__ = "documents"

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
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    storage_path = Column(Text, nullable=False)
    storage_backend = Column(String(50), default="local")
    vector_collection = Column(String(255), nullable=True)
    language = Column(String(10), nullable=True)
    page_count = Column(Integer, nullable=True)
    has_ocr = Column(Boolean, default=False, nullable=False)
    summary = Column(Text, nullable=True)
    auto_tags = Column(JSON, default=list)
    embedding_version = Column(String(20), nullable=True)
    checksum = Column(String(64), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    user = relationship("User", back_populates="documents")
    project = relationship("Project", back_populates="documents")
    versions = relationship(
        "DocumentVersion", back_populates="document", cascade="all, delete-orphan"
    )
    chunks = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_documents_org", "organization_id"),
        Index("ix_documents_workspace", "workspace_id"),
        Index("ix_documents_project", "project_id"),
        Index("ix_documents_user", "user_id"),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    document_id = Column(
        UUID(as_uuid=False),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    storage_path = Column(Text, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    checksum = Column(String(64), nullable=True)
    change_summary = Column(Text, nullable=True)
    created_by = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    document = relationship("Document", back_populates="versions")
    creator = relationship("User")

    __table_args__ = (
        UniqueConstraint(
            "document_id", "version_number", name="uq_doc_version"
        ),
        Index("ix_doc_versions_doc", "document_id"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    document_id = Column(
        UUID(as_uuid=False),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    embedding_id = Column(String(255), nullable=True)
    page_number = Column(Integer, nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("ix_doc_chunks_doc_index", "document_id", "chunk_index"),
    )
