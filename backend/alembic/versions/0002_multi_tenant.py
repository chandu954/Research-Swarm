"""Multi-tenant schema: organizations, projects, expanded auth, KG, audit, billing

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-03 12:00:00.000000
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Users: expand with OAuth + MFA fields ──────────────────────────
    op.add_column("users", sa.Column("github_id", sa.String(255), unique=True, nullable=True))
    op.add_column("users", sa.Column("microsoft_id", sa.String(255), unique=True, nullable=True))
    op.add_column("users", sa.Column("is_superuser", sa.Boolean(), default=False, nullable=False))
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), default=False, nullable=False))
    op.add_column("users", sa.Column("mfa_secret", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_login_ip", sa.String(45), nullable=True))
    op.alter_column("users", "hashed_password", existing_type=sa.String(255), nullable=True)

    # ── User Sessions ──────────────────────────────────────────────────
    op.create_table("user_sessions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("refresh_token_hash", sa.String(255), nullable=False, index=True),
        sa.Column("device_id", UUID(as_uuid=False), sa.ForeignKey("user_devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_sessions_user_active", "user_sessions", ["user_id", "is_active"])

    # ── User Devices ───────────────────────────────────────────────────
    op.create_table("user_devices",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("device_name", sa.String(255), nullable=True),
        sa.Column("device_type", sa.String(50), nullable=True),
        sa.Column("trusted", sa.Boolean(), default=False, nullable=False),
        sa.Column("trusted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ip", sa.String(45), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_devices_user", "user_devices", ["user_id"])

    # ── Organizations ──────────────────────────────────────────────────
    op.create_table("organizations",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column("owner_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("settings", JSONB, default=dict),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── Organization Members ───────────────────────────────────────────
    op.create_table("organization_members",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(20), default="member", nullable=False),
        sa.Column("permissions", JSONB, default=dict),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )
    op.create_index("ix_org_members_org_user", "organization_members", ["organization_id", "user_id"])

    # ── Workspaces: add organization_id ────────────────────────────────
    op.add_column("workspaces", sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True))
    op.add_column("workspaces", sa.Column("slug", sa.String(255), nullable=True))
    op.add_column("workspaces", sa.Column("description", sa.Text, nullable=True))
    op.add_column("workspaces", sa.Column("settings", JSONB, default=dict))
    op.add_column("workspaces", sa.Column("vector_db_namespace", sa.String(255), nullable=True))
    op.add_column("workspaces", sa.Column("is_active", sa.Boolean(), default=True, nullable=False))
    op.create_index("ix_workspaces_org", "workspaces", ["organization_id"])
    op.create_unique_constraint("uq_workspace_org_slug", "workspaces", ["organization_id", "slug"])

    # ── Workspace Members: add permissions ─────────────────────────────
    op.add_column("workspace_members", sa.Column("permissions", JSONB, default=dict))
    op.drop_index("ix_workspace_members_unique", table_name="workspace_members")
    op.create_unique_constraint("uq_workspace_member", "workspace_members", ["workspace_id", "user_id"])
    op.create_index("ix_workspace_members_ws_user", "workspace_members", ["workspace_id", "user_id"])

    # ── Projects ───────────────────────────────────────────────────────
    op.create_table("projects",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("owner_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("settings", JSONB, default=dict),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_project_ws_slug"),
    )
    op.create_index("ix_projects_workspace", "projects", ["workspace_id"])

    # ── Collections ────────────────────────────────────────────────────
    op.create_table("collections",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=False), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("owner_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_collections_project", "collections", ["project_id"])

    # ── Conversations: add tenant fields ───────────────────────────────
    op.add_column("conversations", sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True))
    op.add_column("conversations", sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True))
    op.add_column("conversations", sa.Column("project_id", UUID(as_uuid=False), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True))
    op.add_column("conversations", sa.Column("description", sa.Text, nullable=True))
    op.add_column("conversations", sa.Column("is_archived", sa.Boolean(), default=False, nullable=False))
    op.add_column("conversations", sa.Column("is_pinned", sa.Boolean(), default=False, nullable=False))
    op.add_column("conversations", sa.Column("is_favorited", sa.Boolean(), default=False, nullable=False))
    op.add_column("conversations", sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False))
    op.add_column("conversations", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversations", sa.Column("visibility", sa.String(20), default="workspace", nullable=False))
    op.add_column("conversations", sa.Column("share_token", sa.String(64), unique=True, nullable=True))
    op.add_column("conversations", sa.Column("source_conversation_id", UUID(as_uuid=False), nullable=True))
    op.add_column("conversations", sa.Column("agent_metrics_cache", JSONB, default=dict))
    op.create_index("ix_conversations_org", "conversations", ["organization_id"])
    op.create_index("ix_conversations_workspace", "conversations", ["workspace_id"])
    op.create_index("ix_conversations_project", "conversations", ["project_id"])

    # ── Messages: add parent_id ────────────────────────────────────────
    op.add_column("messages", sa.Column("parent_id", UUID(as_uuid=False), nullable=True))

    # ── Documents: add tenant + enhanced fields ────────────────────────
    op.add_column("documents", sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True))
    op.add_column("documents", sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True))
    op.add_column("documents", sa.Column("project_id", UUID(as_uuid=False), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True))
    op.add_column("documents", sa.Column("language", sa.String(10), nullable=True))
    op.add_column("documents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("has_ocr", sa.Boolean(), default=False, nullable=False))
    op.add_column("documents", sa.Column("summary", sa.Text, nullable=True))
    op.add_column("documents", sa.Column("auto_tags", JSONB, default=list))
    op.add_column("documents", sa.Column("embedding_version", sa.String(20), nullable=True))
    op.add_column("documents", sa.Column("checksum", sa.String(64), nullable=True))
    op.add_column("documents", sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False))
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_documents_org", "documents", ["organization_id"])
    op.create_index("ix_documents_workspace", "documents", ["workspace_id"])
    op.create_index("ix_documents_project", "documents", ["project_id"])

    # ── Document Versions ──────────────────────────────────────────────
    op.create_table("document_versions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=False), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "version_number", name="uq_doc_version"),
    )
    op.create_index("ix_doc_versions_doc", "document_versions", ["document_id"])

    # ── Document Chunks ───────────────────────────────────────────────
    op.create_table("document_chunks",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=False), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("metadata", JSONB, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_doc_chunks_doc_index", "document_chunks", ["document_id", "chunk_index"])

    # ── Research Tasks: add tenant fields ─────────────────────────────
    op.add_column("research_tasks", sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True))
    op.add_column("research_tasks", sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True))
    op.add_column("research_tasks", sa.Column("project_id", UUID(as_uuid=False), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True))
    op.add_column("research_tasks", sa.Column("model_usage", JSONB, default=dict))
    op.add_column("research_tasks", sa.Column("cost_estimate", sa.Float(), nullable=True))
    op.add_column("research_tasks", sa.Column("token_count", sa.BigInteger(), nullable=True))
    op.create_index("ix_research_tasks_org", "research_tasks", ["organization_id"])

    # ── Knowledge Graph ───────────────────────────────────────────────
    op.create_table("knowledge_graph_nodes",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("project_id", UUID(as_uuid=False), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("conversation_id", UUID(as_uuid=False), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("properties", JSONB, default=dict),
        sa.Column("confidence", sa.Float(), default=1.0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kg_nodes_org", "knowledge_graph_nodes", ["organization_id"])
    op.create_index("ix_kg_nodes_conversation", "knowledge_graph_nodes", ["conversation_id"])

    op.create_table("knowledge_graph_edges",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_node_id", UUID(as_uuid=False), sa.ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("target_node_id", UUID(as_uuid=False), sa.ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("relation_type", sa.String(100), nullable=False),
        sa.Column("properties", JSONB, default=dict),
        sa.Column("confidence", sa.Float(), default=1.0),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kg_edges_source", "knowledge_graph_edges", ["source_node_id"])
    op.create_index("ix_kg_edges_target", "knowledge_graph_edges", ["target_node_id"])

    # ── Memory (multi-level) ──────────────────────────────────────────
    op.create_table("memories",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("project_id", UUID(as_uuid=False), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", JSONB, nullable=False),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("importance", sa.Float(), default=0.5),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "scope", "key", name="uq_memory_user_scope_key"),
    )
    op.create_index("ix_memories_scope", "memories", ["scope"])
    op.create_index("ix_memories_org", "memories", ["organization_id"])

    # ── Notifications ─────────────────────────────────────────────────
    op.create_table("notifications",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("data", JSONB, default=dict),
        sa.Column("is_read", sa.Boolean(), default=False, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])
    op.create_index("ix_notifications_created", "notifications", ["created_at"])

    # ── Audit Logs ────────────────────────────────────────────────────
    op.create_table("audit_logs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("details", JSONB, default=dict),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_org_action", "audit_logs", ["organization_id", "action"])
    op.create_index("ix_audit_logs_created", "audit_logs", ["created_at"])

    # ── API Keys ──────────────────────────────────────────────────────
    op.create_table("api_keys",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("permissions", JSONB, default=list),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_api_keys_org", "api_keys", ["organization_id"])

    # ── Billing Records ───────────────────────────────────────────────
    op.create_table("billing_records",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column("tokens_in", sa.BigInteger(), default=0),
        sa.Column("tokens_out", sa.BigInteger(), default=0),
        sa.Column("storage_bytes", sa.BigInteger(), default=0),
        sa.Column("api_calls", sa.Integer(), default=0),
        sa.Column("compute_seconds", sa.Float(), default=0.0),
        sa.Column("estimated_cost", sa.Float(), default=0.0),
        sa.Column("currency", sa.String(3), default="USD"),
        sa.Column("billed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_billing_org_period", "billing_records", ["organization_id", "created_at"])

    # ── Tags ──────────────────────────────────────────────────────────
    op.create_table("tags",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(7), default="#6366f1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_tag_org_name"),
    )

    op.create_table("tag_assignments",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("tag_id", UUID(as_uuid=False), sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tag_id", "resource_type", "resource_id", name="uq_tag_assignment"),
    )
    op.create_index("ix_tag_assignments_resource", "tag_assignments", ["resource_type", "resource_id"])

    # ── Bookmarks ────────────────────────────────────────────────────
    op.create_table("bookmarks",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "resource_type", "resource_id", name="uq_bookmark"),
    )
    op.create_index("ix_bookmarks_user", "bookmarks", ["user_id"])


def downgrade() -> None:
    op.drop_table("bookmarks")
    op.drop_table("tag_assignments")
    op.drop_table("tags")
    op.drop_table("billing_records")
    op.drop_table("api_keys")
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("memories")
    op.drop_table("knowledge_graph_edges")
    op.drop_table("knowledge_graph_nodes")
    op.drop_index("ix_research_tasks_org", table_name="research_tasks")
    op.drop_column("research_tasks", "token_count")
    op.drop_column("research_tasks", "cost_estimate")
    op.drop_column("research_tasks", "model_usage")
    op.drop_column("research_tasks", "project_id")
    op.drop_column("research_tasks", "workspace_id")
    op.drop_column("research_tasks", "organization_id")
    op.drop_table("document_chunks")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_project", table_name="documents")
    op.drop_index("ix_documents_workspace", table_name="documents")
    op.drop_index("ix_documents_org", table_name="documents")
    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "is_deleted")
    op.drop_column("documents", "checksum")
    op.drop_column("documents", "embedding_version")
    op.drop_column("documents", "auto_tags")
    op.drop_column("documents", "summary")
    op.drop_column("documents", "has_ocr")
    op.drop_column("documents", "page_count")
    op.drop_column("documents", "language")
    op.drop_column("documents", "project_id")
    op.drop_column("documents", "workspace_id")
    op.drop_column("documents", "organization_id")
    op.drop_column("messages", "parent_id")
    op.drop_index("ix_conversations_project", table_name="conversations")
    op.drop_index("ix_conversations_workspace", table_name="conversations")
    op.drop_index("ix_conversations_org", table_name="conversations")
    op.drop_column("conversations", "agent_metrics_cache")
    op.drop_column("conversations", "source_conversation_id")
    op.drop_column("conversations", "share_token")
    op.drop_column("conversations", "visibility")
    op.drop_column("conversations", "deleted_at")
    op.drop_column("conversations", "is_deleted")
    op.drop_column("conversations", "is_favorited")
    op.drop_column("conversations", "is_pinned")
    op.drop_column("conversations", "is_archived")
    op.drop_column("conversations", "description")
    op.drop_column("conversations", "project_id")
    op.drop_column("conversations", "workspace_id")
    op.drop_column("conversations", "organization_id")
    op.drop_table("collections")
    op.drop_index("ix_projects_workspace", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_workspace_members_ws_user", table_name="workspace_members")
    op.drop_constraint("uq_workspace_member", "workspace_members")
    op.drop_column("workspace_members", "permissions")
    op.drop_constraint("uq_workspace_org_slug", "workspaces")
    op.drop_index("ix_workspaces_org", table_name="workspaces")
    op.drop_column("workspaces", "is_active")
    op.drop_column("workspaces", "vector_db_namespace")
    op.drop_column("workspaces", "settings")
    op.drop_column("workspaces", "description")
    op.drop_column("workspaces", "slug")
    op.drop_column("workspaces", "organization_id")
    op.drop_table("organization_members")
    op.drop_table("organizations")
    op.drop_index("ix_user_devices_user", table_name="user_devices")
    op.drop_table("user_devices")
    op.drop_index("ix_user_sessions_user_active", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_column("users", "last_login_ip")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "mfa_secret")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "is_superuser")
    op.drop_column("users", "microsoft_id")
    op.drop_column("users", "github_id")
