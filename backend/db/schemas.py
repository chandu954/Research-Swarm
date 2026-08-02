"""Pydantic schemas for API request/response validation."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


# ── Auth ─────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str
    exp: float
    type: str = "access"
    org_id: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    supabase_access_token: Optional[str] = None
    supabase_refresh_token: Optional[str] = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: Optional[str] = None
    is_active: bool = True
    mfa_enabled: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Tenant Context ───────────────────────────────────────────────

class TenantContext(BaseModel):
    organization_id: str
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None
    user_id: str
    role: str = "member"
    permissions: dict[str, Any] = {}


# ── Organizations ────────────────────────────────────────────────

class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    owner_id: str
    member_count: int = 0
    is_active: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    avatar_url: Optional[str] = None


# ── Organization Members ─────────────────────────────────────────

class MemberRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    RESEARCHER = "researcher"
    VIEWER = "viewer"


class MemberResponse(BaseModel):
    id: str
    user_id: str
    name: str = ""
    email: str = ""
    role: str = "member"
    joined_at: datetime

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    email: EmailStr
    role: MemberRole = MemberRole.RESEARCHER


class UpdateMemberRoleRequest(BaseModel):
    role: MemberRole


# ── Workspaces ───────────────────────────────────────────────────

class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=255, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str = ""
    description: Optional[str] = None
    organization_id: str
    owner_id: str
    member_count: int = 0
    is_active: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class WorkspaceMemberResponse(BaseModel):
    user_id: str
    name: str = ""
    email: str = ""
    role: str = "member"
    joined_at: datetime

    model_config = {"from_attributes": True}


# ── Projects ─────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=255, pattern=r"^[a-z0-9-]+$")
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    slug: str = ""
    description: Optional[str] = None
    organization_id: str
    workspace_id: str
    owner_id: str
    is_active: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


# ── Conversations ────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    title: Optional[str] = None
    project_id: Optional[str] = None


class ConversationResponse(BaseModel):
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    is_archived: bool = False
    is_pinned: bool = False
    is_favorited: bool = False
    visibility: str = "workspace"
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    messages: list["MessageResponse"] = []
    is_archived: bool = False
    is_pinned: bool = False
    is_favorited: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_archived: Optional[bool] = None
    is_pinned: Optional[bool] = None
    is_favorited: Optional[bool] = None
    visibility: Optional[str] = None


# ── Messages ─────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Documents ────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    size_bytes: int
    mime_type: str
    language: Optional[str] = None
    page_count: Optional[int] = None
    summary: Optional[str] = None
    auto_tags: list[str] = []
    is_deleted: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentVersionResponse(BaseModel):
    id: str
    version_number: int
    size_bytes: int
    change_summary: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Research ─────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    document_ids: list[str] = Field(default_factory=list)
    conversation_id: Optional[str] = None
    project_id: Optional[str] = None
    mode: str = Field(default="quick", description="Research mode: quick, deep, compare, summarize, verify")
    debate_mode: bool = Field(default=False, description="Enable AI Debate Mode with multiple perspective agents")
    debate_perspectives: Optional[list[str]] = Field(default=None, description="Specific perspective IDs to include")
    llm_provider: Optional[str] = Field(default=None, description="ollama or openrouter")
    planner_model: Optional[str] = None
    research_model: Optional[str] = None
    document_model: Optional[str] = None
    answer_model: Optional[str] = None
    stream_task_id: Optional[str] = Field(default=None, description="Client task id for live log streaming")


class ResearchResponse(BaseModel):
    task_id: str
    conversation_id: str
    query: str
    answer: Optional[str] = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    logs: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "completed"
    errors: list[str] = Field(default_factory=list)
    execution_time: float = 0.0
    plan_reasoning: Optional[str] = None
    agent_metrics: dict[str, Any] = Field(default_factory=dict)
    cost_estimate: Optional[float] = None
    token_count: Optional[int] = None
    debate: Optional[dict[str, Any]] = Field(default=None, description="Debate mode result with perspectives and judge verdict")
    answer_mode: str = Field(default="normal", description="normal | fallback | no_evidence")
    evidence_summary: Optional[dict[str, Any]] = Field(default=None, description="What evidence was retrieved")
    has_evidence: bool = False


# ── Plugin ───────────────────────────────────────────────────────

class PluginConfigRequest(BaseModel):
    name: str = Field(..., description="Plugin name")
    config: dict[str, Any] = Field(default_factory=dict)


class PluginStatus(BaseModel):
    name: str
    configured: bool
    actions: list[str] = Field(default_factory=list)
    error: Optional[str] = None


# ── Notifications ────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    body: Optional[str] = None
    data: dict[str, Any] = {}
    is_read: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# ── API Keys ─────────────────────────────────────────────────────

class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    permissions: list[str] = Field(default_factory=list)


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    is_active: bool = True
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyFullResponse(APIKeyResponse):
    raw_key: str = ""


# ── Audit Log ────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: dict[str, Any] = {}
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Provider ────────────────────────────────────────────────────

class ProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider_type: str = Field(..., pattern=r"^(llm|search|embedding)$")
    provider_key: str = Field(..., min_length=1, max_length=100)
    config: dict[str, Any] = {}


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class ProviderResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    provider_key: str
    config: dict[str, Any]
    is_active: bool
    organization_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProviderListResponse(BaseModel):
    builtin: dict[str, dict[str, Any]]
    custom: list[ProviderResponse]


# ── Billing ──────────────────────────────────────────────────────

class BillingUsageResponse(BaseModel):
    tokens_in: int = 0
    tokens_out: int = 0
    storage_bytes: int = 0
    api_calls: int = 0
    compute_seconds: float = 0.0
    estimated_cost: float = 0.0
    currency: str = "USD"


# ── Tags ─────────────────────────────────────────────────────────

class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str = "#6366f1"


class TagResponse(BaseModel):
    id: str
    name: str
    color: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Entity Extraction ─────────────────────────────────────────────

class ExtractEntitiesRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    llm_provider: Optional[str] = None
    model: Optional[str] = None


# ── Pagination ────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    offset: int = 0
    limit: int = 50


# ── Search ───────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    resource_types: list[str] = Field(default_factory=lambda: ["conversations", "documents", "reports", "messages"])
    limit: int = Field(default=20, ge=1, le=100)


class SearchResult(BaseModel):
    resource_type: str
    resource_id: str
    title: str
    snippet: str
    score: float
    created_at: Optional[datetime] = None
    url: Optional[str] = None
