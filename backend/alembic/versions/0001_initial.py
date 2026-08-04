"""Initial migration: complete multi-tenant baseline (squashed).

This is the corrected baseline for a fresh production database. It replaces
the original 0001/0002 chain, which could not run end-to-end:

- `workspaces` / `workspace_members` were referenced by 0002 but never created.
- `user_sessions` referenced `user_devices` before it existed.
- ID types drifted between VARCHAR(36) and UUID across the chain.

Every table uses a single canonical ID type (UUID, matching the SQLAlchemy
models), tables are created in foreign-key-safe order, and JSON columns use
portable `sa.JSON` (models use SQLAlchemy's generic JSON) so the chain is
verifiable on both PostgreSQL and SQLite.

Revision ID: 0001
Revises: None
Create Date: 2026-08-04 00:00:00.000000
"""
from __future__ import annotations
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Single canonical ID type for the whole schema (matches db/models.py).
ID = UUID(as_uuid=False)


def _id() -> sa.Column:
    return sa.Column("id", ID, primary_key=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    # ── Users ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        _id(),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("google_id", sa.String(255), unique=True, nullable=True),
        sa.Column("github_id", sa.String(255), unique=True, nullable=True),
        sa.Column("microsoft_id", sa.String(255), unique=True, nullable=True),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mfa_secret", sa.String(255), nullable=True),
        sa.Column("mfa_recovery_codes", sa.Text(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_ip", sa.String(45), nullable=True),
        *_timestamps(),
    )

    # ── User Devices (before sessions: sessions FK -> devices) ────────
    op.create_table(
        "user_devices",
        _id(),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("device_name", sa.String(255), nullable=True),
        sa.Column("device_type", sa.String(50), nullable=True),
        sa.Column("trusted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("trusted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ip", sa.String(45), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_devices_user", "user_devices", ["user_id"])

    # ── User Sessions ─────────────────────────────────────────────────
    op.create_table(
        "user_sessions",
        _id(),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("refresh_token_hash", sa.String(255), nullable=False, index=True),
        sa.Column("device_id", ID, sa.ForeignKey("user_devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_sessions_user_active", "user_sessions", ["user_id", "is_active"])

    # ── Organizations ─────────────────────────────────────────────────
    op.create_table(
        "organizations",
        _id(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("owner_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("settings", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
    )

    # ── Organization Members ──────────────────────────────────────────
    op.create_table(
        "organization_members",
        _id(),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("permissions", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )
    op.create_index("ix_org_members_org_user", "organization_members", ["organization_id", "user_id"])

    # ── Workspaces ────────────────────────────────────────────────────
    op.create_table(
        "workspaces",
        _id(),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("settings", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("vector_db_namespace", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("organization_id", "slug", name="uq_workspace_org_slug"),
    )
    op.create_index("ix_workspaces_org", "workspaces", ["organization_id"])

    # ── Workspace Members ─────────────────────────────────────────────
    op.create_table(
        "workspace_members",
        _id(),
        sa.Column("workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("permissions", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )
    op.create_index("ix_workspace_members_ws_user", "workspace_members", ["workspace_id", "user_id"])

    # ── Projects ──────────────────────────────────────────────────────
    op.create_table(
        "projects",
        _id(),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("settings", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_project_ws_slug"),
    )
    op.create_index("ix_projects_workspace", "projects", ["workspace_id"])

    # ── Collections ───────────────────────────────────────────────────
    op.create_table(
        "collections",
        _id(),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("project_id", ID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        *_timestamps(),
    )
    op.create_index("ix_collections_project", "collections", ["project_id"])

    # ── Conversations ─────────────────────────────────────────────────
    op.create_table(
        "conversations",
        _id(),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("project_id", ID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_favorited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="workspace"),
        sa.Column("share_token", sa.String(64), unique=True, nullable=True),
        sa.Column("source_conversation_id", ID, nullable=True),
        sa.Column("agent_metrics_cache", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_conversations_user_updated", "conversations", ["user_id", "updated_at"])
    op.create_index("ix_conversations_org", "conversations", ["organization_id"])
    op.create_index("ix_conversations_workspace", "conversations", ["workspace_id"])
    op.create_index("ix_conversations_project", "conversations", ["project_id"])

    # ── Messages ──────────────────────────────────────────────────────
    op.create_table(
        "messages",
        _id(),
        sa.Column("conversation_id", ID, sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("parent_id", ID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])

    # ── Documents ─────────────────────────────────────────────────────
    op.create_table(
        "documents",
        _id(),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("project_id", ID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("storage_backend", sa.String(50), nullable=False, server_default="local"),
        sa.Column("vector_collection", sa.String(255), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("has_ocr", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("auto_tags", sa.JSON(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("embedding_version", sa.String(20), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_documents_org", "documents", ["organization_id"])
    op.create_index("ix_documents_workspace", "documents", ["workspace_id"])
    op.create_index("ix_documents_project", "documents", ["project_id"])
    op.create_index("ix_documents_user", "documents", ["user_id"])

    # ── Document Versions ─────────────────────────────────────────────
    op.create_table(
        "document_versions",
        _id(),
        sa.Column("document_id", ID, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("created_by", ID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "version_number", name="uq_doc_version"),
    )
    op.create_index("ix_doc_versions_doc", "document_versions", ["document_id"])

    # ── Document Chunks ───────────────────────────────────────────────
    op.create_table(
        "document_chunks",
        _id(),
        sa.Column("document_id", ID, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_doc_chunks_doc_index", "document_chunks", ["document_id", "chunk_index"])

    # ── Research Tasks ────────────────────────────────────────────────
    op.create_table(
        "research_tasks",
        _id(),
        sa.Column("conversation_id", ID, sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("project_id", ID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("plan", sa.JSON(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("logs", sa.JSON(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("sources", sa.JSON(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("model_usage", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("cost_estimate", sa.Float(), nullable=True),
        sa.Column("token_count", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_research_tasks_status", "research_tasks", ["status"])
    op.create_index("ix_research_tasks_conversation", "research_tasks", ["conversation_id"])
    op.create_index("ix_research_tasks_org", "research_tasks", ["organization_id"])

    # ── Knowledge Graph ───────────────────────────────────────────────
    op.create_table(
        "knowledge_graph_nodes",
        _id(),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("project_id", ID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("conversation_id", ID, sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("properties", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        *_timestamps(),
    )
    op.create_index("ix_kg_nodes_org", "knowledge_graph_nodes", ["organization_id"])
    op.create_index("ix_kg_nodes_conversation", "knowledge_graph_nodes", ["conversation_id"])

    op.create_table(
        "knowledge_graph_edges",
        _id(),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_node_id", ID, sa.ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("target_node_id", ID, sa.ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("relation_type", sa.String(100), nullable=False),
        sa.Column("properties", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_kg_edges_source", "knowledge_graph_edges", ["source_node_id"])
    op.create_index("ix_kg_edges_target", "knowledge_graph_edges", ["target_node_id"])

    # ── Memory (multi-level) ──────────────────────────────────────────
    op.create_table(
        "memories",
        _id(),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("project_id", ID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("importance", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "scope", "key", name="uq_memory_user_scope_key"),
    )
    op.create_index("ix_memories_scope", "memories", ["scope"])
    op.create_index("ix_memories_org", "memories", ["organization_id"])

    # ── Notifications ─────────────────────────────────────────────────
    op.create_table(
        "notifications",
        _id(),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("data", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])
    op.create_index("ix_notifications_created", "notifications", ["created_at"])

    # ── Audit Logs ────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        _id(),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("details", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_org_action", "audit_logs", ["organization_id", "action"])
    op.create_index("ix_audit_logs_created", "audit_logs", ["created_at"])

    # ── API Keys ──────────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        _id(),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("permissions", sa.JSON(), server_default=sa.text("'[]'"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_api_keys_org", "api_keys", ["organization_id"])

    # ── Billing Records ───────────────────────────────────────────────
    op.create_table(
        "billing_records",
        _id(),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column("tokens_in", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("tokens_out", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("storage_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("api_calls", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("compute_seconds", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("billed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_billing_org_period", "billing_records", ["organization_id", "created_at"])

    # ── Tags ──────────────────────────────────────────────────────────
    op.create_table(
        "tags",
        _id(),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(7), nullable=False, server_default="#6366f1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "name", name="uq_tag_org_name"),
    )

    op.create_table(
        "tag_assignments",
        _id(),
        sa.Column("tag_id", ID, sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tag_id", "resource_type", "resource_id", name="uq_tag_assignment"),
    )
    op.create_index("ix_tag_assignments_resource", "tag_assignments", ["resource_type", "resource_id"])

    # ── Bookmarks ─────────────────────────────────────────────────────
    op.create_table(
        "bookmarks",
        _id(),
        sa.Column("user_id", ID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "resource_type", "resource_id", name="uq_bookmark"),
    )
    op.create_index("ix_bookmarks_user", "bookmarks", ["user_id"])

    # ── Providers ─────────────────────────────────────────────────────
    op.create_table(
        "providers",
        _id(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("provider_key", sa.String(100), nullable=False),
        sa.Column("config", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("organization_id", ID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("created_by", ID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_providers_org", "providers", ["organization_id"])
    op.create_index("ix_providers_type", "providers", ["provider_type"])


def downgrade() -> None:
    op.drop_table("providers")
    op.drop_index("ix_bookmarks_user", table_name="bookmarks")
    op.drop_table("bookmarks")
    op.drop_index("ix_tag_assignments_resource", table_name="tag_assignments")
    op.drop_table("tag_assignments")
    op.drop_table("tags")
    op.drop_index("ix_billing_org_period", table_name="billing_records")
    op.drop_table("billing_records")
    op.drop_index("ix_api_keys_org", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_audit_logs_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_org_action", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_notifications_created", table_name="notifications")
    op.drop_index("ix_notifications_user_read", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_memories_org", table_name="memories")
    op.drop_index("ix_memories_scope", table_name="memories")
    op.drop_table("memories")
    op.drop_index("ix_kg_edges_target", table_name="knowledge_graph_edges")
    op.drop_index("ix_kg_edges_source", table_name="knowledge_graph_edges")
    op.drop_table("knowledge_graph_edges")
    op.drop_index("ix_kg_nodes_conversation", table_name="knowledge_graph_nodes")
    op.drop_index("ix_kg_nodes_org", table_name="knowledge_graph_nodes")
    op.drop_table("knowledge_graph_nodes")
    op.drop_index("ix_research_tasks_org", table_name="research_tasks")
    op.drop_index("ix_research_tasks_conversation", table_name="research_tasks")
    op.drop_index("ix_research_tasks_status", table_name="research_tasks")
    op.drop_table("research_tasks")
    op.drop_index("ix_doc_chunks_doc_index", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_doc_versions_doc", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_user", table_name="documents")
    op.drop_index("ix_documents_project", table_name="documents")
    op.drop_index("ix_documents_workspace", table_name="documents")
    op.drop_index("ix_documents_org", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_project", table_name="conversations")
    op.drop_index("ix_conversations_workspace", table_name="conversations")
    op.drop_index("ix_conversations_org", table_name="conversations")
    op.drop_index("ix_conversations_user_updated", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_collections_project", table_name="collections")
    op.drop_table("collections")
    op.drop_index("ix_projects_workspace", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_workspace_members_ws_user", table_name="workspace_members")
    op.drop_table("workspace_members")
    op.drop_index("ix_workspaces_org", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index("ix_org_members_org_user", table_name="organization_members")
    op.drop_table("organization_members")
    op.drop_table("organizations")
    op.drop_index("ix_user_sessions_user_active", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_user_devices_user", table_name="user_devices")
    op.drop_table("user_devices")
    op.drop_table("users")
