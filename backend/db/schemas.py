"""Pydantic schemas for API request/response validation."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


# ── Auth ───────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str
    exp: float
    type: str = "access"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


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
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Conversations ──────────────────────────────────────────────

class ConversationCreate(BaseModel):
    title: Optional[str] = None


class ConversationResponse(BaseModel):
    id: str
    title: Optional[str] = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: str
    title: Optional[str] = None
    messages: list["MessageResponse"] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Messages ───────────────────────────────────────────────────

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Documents ──────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    size_bytes: int
    mime_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Research ───────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    document_ids: list[str] = Field(default_factory=list)
    conversation_id: Optional[str] = None
    llm_provider: Optional[str] = Field(default=None, description="ollama or openrouter")
    planner_model: Optional[str] = None
    research_model: Optional[str] = None
    document_model: Optional[str] = None
    answer_model: Optional[str] = None
    openrouter_key: Optional[str] = None
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
