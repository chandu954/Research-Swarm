"""Notifications, global search, billing, API keys, audit, and model catalog."""

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.common import log_audit
from backend.auth.dependencies import get_current_user
from backend.auth.tenant import TenantContext, resolve_tenant_dependencies
from backend.db.models import (
    APIKey,
    AuditLog,
    BillingRecord,
    Conversation,
    Document,
    Message,
    Notification,
    User,
)
from backend.db.schemas import (
    APIKeyCreate,
    APIKeyFullResponse,
    APIKeyResponse,
    AuditLogResponse,
    BillingUsageResponse,
    NotificationResponse,
    SearchRequest,
    SearchResult,
)
from backend.db.session import get_session

router = APIRouter(tags=["workspace"])


# ═══════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    include_read: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    q = select(Notification).where(
        Notification.user_id == current_user.id,
        Notification.organization_id == ctx.organization_id,
    )
    if not include_read:
        q = q.where(Notification.is_read.is_(False))
    q = q.order_by(Notification.created_at.desc()).limit(limit)
    result = await session.execute(q)
    return [NotificationResponse.model_validate(n) for n in result.scalars().all()]


@router.post("/notifications/{notif_id}/read")
async def mark_notification_read(
    notif_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Notification).where(
            Notification.id == notif_id,
            Notification.user_id == current_user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    notif.read_at = datetime.now(timezone.utc)
    await session.flush()
    return {"status": "read"}


@router.post("/notifications/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import update as sa_update

    await session.execute(
        sa_update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    await session.flush()
    return {"status": "all_read"}


# ═══════════════════════════════════════════════════════════════
# SEARCH (global, tenant-scoped)
# ═══════════════════════════════════════════════════════════════


@router.post("/search", response_model=list[SearchResult])
async def global_search(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    results = []
    pattern = f"%{body.query}%"

    if "conversations" in body.resource_types:
        conv_q = (
            select(Conversation)
            .where(
                Conversation.organization_id == ctx.organization_id,
                Conversation.is_deleted.is_(False),
                Conversation.title.ilike(pattern),
            )
            .limit(body.limit)
        )
        conv_result = await session.execute(conv_q)
        for conv in conv_result.scalars().all():
            results.append(
                SearchResult(
                    resource_type="conversation",
                    resource_id=conv.id,
                    title=conv.title or "Untitled",
                    snippet=conv.description or "",
                    score=0.9,
                    created_at=conv.created_at,
                )
            )

    if "documents" in body.resource_types:
        doc_q = (
            select(Document)
            .where(
                Document.organization_id == ctx.organization_id,
                Document.is_deleted.is_(False),
                or_(
                    Document.original_filename.ilike(pattern),
                    Document.summary.ilike(pattern) if Document.summary else False,
                ),
            )
            .limit(body.limit)
        )
        doc_result = await session.execute(doc_q)
        for doc in doc_result.scalars().all():
            results.append(
                SearchResult(
                    resource_type="document",
                    resource_id=doc.id,
                    title=doc.original_filename,
                    snippet=doc.summary or "",
                    score=0.8,
                    created_at=doc.created_at,
                )
            )

    if "messages" in body.resource_types:
        msg_q = (
            select(Message)
            .join(
                Conversation,
                Message.conversation_id == Conversation.id,
            )
            .where(
                Conversation.organization_id == ctx.organization_id,
                Conversation.is_deleted.is_(False),
                Message.content.ilike(pattern),
            )
            .limit(body.limit)
        )
        msg_result = await session.execute(msg_q)
        for msg in msg_result.scalars().all():
            results.append(
                SearchResult(
                    resource_type="message",
                    resource_id=msg.id,
                    title=f"Message in {msg.conversation_id[:8]}...",
                    snippet=msg.content[:200],
                    score=0.7,
                    created_at=msg.created_at,
                )
            )

    results.sort(key=lambda r: r.score, reverse=True)
    return results[: body.limit]


# ═══════════════════════════════════════════════════════════════
# BILLING
# ═══════════════════════════════════════════════════════════════


@router.get("/billing/usage", response_model=BillingUsageResponse)
async def get_billing_usage(
    organization_id: Optional[str] = Query(None, alias="organization_id"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    """Usage aggregates are scoped to the caller's authenticated tenant.

    The effective organization is derived from the user's membership via
    tenant resolution — a client-supplied organization_id is at most a
    consistency check, never an authority (rejects cross-org reads).
    """
    if organization_id and organization_id != ctx.organization_id:
        raise HTTPException(
            status_code=403,
            detail="Not a member of this organization",
        )
    org_id = ctx.organization_id
    result = await session.execute(
        select(
            func.coalesce(func.sum(BillingRecord.tokens_in), 0),
            func.coalesce(func.sum(BillingRecord.tokens_out), 0),
            func.coalesce(func.sum(BillingRecord.storage_bytes), 0),
            func.coalesce(func.sum(BillingRecord.api_calls), 0),
            func.coalesce(func.sum(BillingRecord.compute_seconds), 0.0),
            func.coalesce(func.sum(BillingRecord.estimated_cost), 0.0),
        ).where(BillingRecord.organization_id == org_id)
    )
    row = result.one()
    return BillingUsageResponse(
        tokens_in=row[0],
        tokens_out=row[1],
        storage_bytes=row[2],
        api_calls=row[3],
        compute_seconds=float(row[4]),
        estimated_cost=float(row[5]),
    )


# ═══════════════════════════════════════════════════════════════
# API KEYS
# ═══════════════════════════════════════════════════════════════


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(APIKey).where(
            APIKey.organization_id == ctx.organization_id,
        )
    )
    return [APIKeyResponse.model_validate(k) for k in result.scalars().all()]


@router.post("/api-keys", response_model=APIKeyFullResponse, status_code=201)
async def create_api_key(
    body: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    import hashlib
    import secrets

    raw_key = f"rs_{secrets.token_urlsafe(32)}"
    key_prefix = raw_key[:8]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    api_key = APIKey(
        organization_id=ctx.organization_id,
        user_id=current_user.id,
        name=body.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        permissions=body.permissions,
    )
    session.add(api_key)
    await session.flush()

    await log_audit(
        session, "apikey.created", "api_key", api_key.id, {"name": body.name}, ctx
    )

    resp = APIKeyFullResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=key_prefix,
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        raw_key=raw_key,
    )
    return resp


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.organization_id == ctx.organization_id,
        )
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.is_active = False
    await session.flush()
    await log_audit(session, "apikey.deleted", "api_key", key_id, {}, ctx)
    return {"status": "deleted"}


# ═══════════════════════════════════════════════════════════════
# AUDIT LOGS
# ═══════════════════════════════════════════════════════════════


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def get_audit_logs(
    action: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    q = select(AuditLog).where(AuditLog.organization_id == ctx.organization_id)
    if action:
        q = q.where(AuditLog.action == action)
    q = q.order_by(AuditLog.created_at.desc()).limit(limit)
    result = await session.execute(q)
    return [AuditLogResponse.model_validate(log) for log in result.scalars().all()]


# ═══════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════


@router.get("/models")
async def list_models():
    import httpx

    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()

    async with httpx.AsyncClient(timeout=10.0) as client:
        if provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                return {
                    "provider": "openrouter",
                    "models": [],
                    "error": "No API key configured",
                }
            try:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                models = sorted(set(m["id"] for m in data.get("data", [])))
                return {
                    "provider": "openrouter",
                    "models": models,
                    "count": len(models),
                }
            except Exception as e:
                logger.error(f"Failed to fetch OpenRouter models: {e}")
                return {"provider": "openrouter", "models": [], "error": str(e)}
        elif provider == "ollama":
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            try:
                resp = await client.get(f"{ollama_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                models = sorted(set(m["name"] for m in data.get("models", [])))
                return {"provider": "ollama", "models": models, "count": len(models)}
            except Exception as e:
                logger.error(f"Failed to fetch Ollama models: {e}")
                return {"provider": "ollama", "models": [], "error": str(e)}
        else:
            from backend.core.registry import get_plugin_registry

            plugin_registry = get_plugin_registry()
            return {
                "provider": provider,
                "models": [],
                "available_providers": plugin_registry.list_types(),
            }
