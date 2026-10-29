"""Package init for backend.db.models package.

Re-exports all models for backward compatibility.
"""

from backend.db.session import Base
from backend.db.models.activity import (
    APIKey,
    AuditLog,
    BillingRecord,
    Bookmark,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    Memory,
    Notification,
    Provider,
    ResearchTask,
    Tag,
    TagAssignment,
)
from backend.db.models.auth import User, UserDevice, UserSession
from backend.db.models.base import SoftDeleteMixin, TenantMixin, _utcnow, _uuid
from backend.db.models.content import (
    Collection,
    Conversation,
    Document,
    DocumentChunk,
    DocumentVersion,
    Message,
)
from backend.db.models.org import (
    Organization,
    OrganizationMember,
    Project,
    Workspace,
    WorkspaceMember,
)

__all__ = [
    "Base",
    "SoftDeleteMixin",
    "TenantMixin",
    "_utcnow",
    "_uuid",
    "User",
    "UserSession",
    "UserDevice",
    "Organization",
    "OrganizationMember",
    "Workspace",
    "WorkspaceMember",
    "Project",
    "Collection",
    "Conversation",
    "Message",
    "Document",
    "DocumentVersion",
    "DocumentChunk",
    "ResearchTask",
    "KnowledgeGraphNode",
    "KnowledgeGraphEdge",
    "Memory",
    "Notification",
    "AuditLog",
    "APIKey",
    "BillingRecord",
    "Tag",
    "TagAssignment",
    "Bookmark",
    "Provider",
]
