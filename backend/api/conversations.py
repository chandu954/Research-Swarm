"""Conversation CRUD endpoints scoped to the authenticated tenant."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.common import log_audit
from backend.auth.dependencies import get_current_user
from backend.auth.tenant import TenantContext, resolve_tenant_dependencies
from backend.db.models import Conversation, Message, User
from backend.db.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
from backend.db.session import get_session

router = APIRouter(tags=["conversations"])


# ═══════════════════════════════════════════════════════════════
# CONVERSATIONS (tenant-aware)
# ═══════════════════════════════════════════════════════════════


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    ws_id: Optional[str] = Query(None, alias="workspace_id"),
    proj_id: Optional[str] = Query(None, alias="project_id"),
    archived: bool = Query(False),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    q = select(Conversation).where(
        Conversation.organization_id == ctx.organization_id,
        Conversation.is_deleted.is_(False),
        Conversation.is_archived == archived,
    )
    if ctx.workspace_id:
        q = q.where(Conversation.workspace_id == ctx.workspace_id)
    elif ws_id:
        q = q.where(Conversation.workspace_id == ws_id)
    if proj_id:
        q = q.where(Conversation.project_id == proj_id)
    if search:
        q = q.where(Conversation.title.ilike(f"%{search}%"))
    q = q.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)

    result = await session.execute(q)
    conversations = result.scalars().all()

    responses = []
    for conv in conversations:
        msg_count = await session.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == conv.id)
        )
        responses.append(
            ConversationResponse(
                id=conv.id,
                title=conv.title,
                description=conv.description,
                is_archived=conv.is_archived,
                is_pinned=conv.is_pinned,
                is_favorited=conv.is_favorited,
                visibility=conv.visibility,
                message_count=msg_count or 0,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )
    return responses


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    conv = Conversation(
        user_id=current_user.id,
        organization_id=ctx.organization_id,
        workspace_id=ctx.workspace_id,
        project_id=body.project_id or ctx.project_id,
        title=body.title or "New Conversation",
    )
    session.add(conv)
    await session.flush()

    await log_audit(
        session,
        "conversation.created",
        "conversation",
        conv.id,
        {"title": conv.title},
        ctx,
    )

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        message_count=0,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("/conversations/{conv_id}", response_model=ConversationDetail)
async def get_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.organization_id == ctx.organization_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages_result = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == conv.id,
        )
        .order_by(Message.created_at)
    )
    messages = messages_result.scalars().all()

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        description=conv.description,
        messages=[MessageResponse.model_validate(m) for m in messages],
        is_archived=conv.is_archived,
        is_pinned=conv.is_pinned,
        is_favorited=conv.is_favorited,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.patch("/conversations/{conv_id}", response_model=ConversationResponse)
async def update_conversation(
    conv_id: str,
    body: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.organization_id == ctx.organization_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if body.title is not None:
        conv.title = body.title
    if body.description is not None:
        conv.description = body.description
    if body.is_archived is not None:
        conv.is_archived = body.is_archived
    if body.is_pinned is not None:
        conv.is_pinned = body.is_pinned
    if body.is_favorited is not None:
        conv.is_favorited = body.is_favorited
    if body.visibility is not None:
        conv.visibility = body.visibility
    await session.flush()
    return ConversationResponse.model_validate(conv)


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.organization_id == ctx.organization_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.is_deleted = True
    conv.deleted_at = datetime.now(timezone.utc)
    await session.flush()
    await log_audit(session, "conversation.deleted", "conversation", conv_id, {}, ctx)
    return {"status": "deleted"}
