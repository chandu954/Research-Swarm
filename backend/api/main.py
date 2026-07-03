"""FastAPI server for ResearchSwarm AI — Multi-Tenant Platform."""
from __future__ import annotations
import os, time, uuid, asyncio, json
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import (
    Depends, FastAPI, UploadFile, File, HTTPException,
    Query, Request, WebSocket, WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from loguru import logger

from backend.agents.graph import create_research_graph
from backend.agents.entity_extractor import extract_entities
from backend.agents.memory import get_memory
from backend.api.stream import get_stream_manager, make_log, event_stream
from backend.api.auth import router as auth_router
from backend.api.organizations import router as org_router
from backend.api.websocket import get_workspace_manager, Connection
from backend.tools.registry import get_registry
from backend.db.session import init_db, close_db, get_session
from backend.db.models import (
    User, Conversation, Message, Document, ResearchTask,
    Organization, OrganizationMember,
    Workspace, WorkspaceMember,
    Project, AuditLog, APIKey, BillingRecord, Notification,
)
from backend.db.schemas import (
    ResearchRequest, ResearchResponse,
    ConversationCreate, ConversationResponse, ConversationDetail,
    ConversationUpdate, MessageResponse,
    DocumentResponse, DocumentVersionResponse,
    PluginConfigRequest, PluginStatus,
    NotificationResponse, APIKeyCreate, APIKeyResponse, APIKeyFullResponse,
    AuditLogResponse, BillingUsageResponse,
    SearchRequest, SearchResult,
    ExtractEntitiesRequest,
    ProviderCreate, ProviderUpdate, ProviderResponse, ProviderListResponse,
)
from backend.auth.dependencies import get_current_user, get_optional_user
from backend.auth.tenant import resolve_tenant_dependencies, resolve_optional_tenant, TenantContext
from backend.plugins.registry import get_plugin_registry
from backend.plugins.github import GitHubPlugin
from backend.plugins.notion import NotionPlugin
from backend.plugins.slack import SlackPlugin
from backend.providers.registry import get_provider_registry

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")
for d in [UPLOAD_DIR, "./data/chroma_db", "./data/memory", "./data/logs"]:
    os.makedirs(d, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ResearchSwarm AI starting up")
    app.state.start_time = time.time()
    await init_db()
    app.state.graph = create_research_graph()
    app.state.memory = get_memory()
    app.state.registry = get_registry()
    app.state.stream_manager = get_stream_manager()
    try:
        tools = app.state.registry.list_tools()
        logger.info(f"Tools registered: {[t.name for t in tools]}")
    except Exception as e:
        logger.warning(f"Tool listing failed: {e}")

    plugin_reg = get_plugin_registry()
    plugin_reg.register(GitHubPlugin(config={"token": os.getenv("GITHUB_TOKEN", "")}))
    plugin_reg.register(NotionPlugin(config={"token": os.getenv("NOTION_TOKEN", "")}))
    plugin_reg.register(SlackPlugin(config={"token": os.getenv("SLACK_TOKEN", "")}))
    logger.info("Built-in plugins registered")
    app.state.plugin_registry = plugin_reg

    prov_reg = get_provider_registry()
    prov_reg.initialize_builtins()
    app.state.provider_registry = prov_reg

    yield
    await close_db()
    logger.info("ResearchSwarm AI shutting down")


def _ensure_app_state() -> None:
    if not hasattr(app.state, "start_time"):
        app.state.start_time = time.time()
    if not hasattr(app.state, "graph"):
        app.state.graph = create_research_graph()
    if not hasattr(app.state, "memory"):
        app.state.memory = get_memory()
    if not hasattr(app.state, "registry"):
        app.state.registry = get_registry()
    if not hasattr(app.state, "stream_manager"):
        app.state.stream_manager = get_stream_manager()
    if not hasattr(app.state, "plugin_registry"):
        app.state.plugin_registry = get_plugin_registry()


app = FastAPI(
    title="ResearchSwarm AI",
    description="Multi-Agent Research Operating System — Multi-Tenant Platform",
    version="3.0.0",
    lifespan=lifespan,
)

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

cors_origins = os.getenv("CORS_ORIGINS", "https://research-swarm-omega.vercel.app,http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        import uuid
        request_id = str(uuid.uuid4())
    start = time.time()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        duration_ms = round((time.time() - start) * 1000, 2)
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        logger.debug(f"[{request_id}] {request.method} {request.url.path} → {response.status_code} ({duration_ms}ms)")
        return response
    except Exception as exc:
        logger.error(f"[{request_id}] {request.method} {request.url.path} → error: {exc}")
        duration_ms = round((time.time() - start) * 1000, 2)
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "Something went wrong while processing your request.",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id, "X-Response-Time-Ms": str(duration_ms)},
        )


@app.exception_handler(Exception)
async def global_fallback(request: Request, exc):
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(f"[{request_id}] Global fallback: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "Something went wrong while processing your request.",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )

app.include_router(auth_router)
app.include_router(org_router)


# ── Health ──────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    _ensure_app_state()
    registry = app.state.registry
    db_ok = True
    try:
        from backend.db.session import get_session
        async for session in get_session():
            await session.execute(select(func.now()))
            break
    except Exception as e:
        db_ok = str(e)

    # Check LLM provider connectivity
    llm_provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
    provider_checks: dict[str, str] = {
        "database": "ok" if db_ok is True else f"error: {db_ok}",
    }

    if llm_provider == "ollama":
        try:
            import httpx
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{ollama_url}/api/tags")
                provider_checks["ollama"] = "ok" if r.status_code == 200 else "error"
        except Exception:
            provider_checks["ollama"] = "error"
    else:
        provider_checks["openrouter"] = "ok" if os.getenv("OPENROUTER_API_KEY") else "unconfigured"

    return {
        "status": "healthy" if db_ok is True else "degraded",
        "version": "3.0.0",
        "uptime": time.time() - app.state.start_time,
        "tools_available": len(registry.list_tools()),
        "providers": list(get_provider_registry().list_all().keys()),
        "checks": provider_checks,
    }


# ── Audit Logging Helper ────────────────────────────────────────

async def _log_audit(
    session,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ctx: Optional[TenantContext] = None,
    request: Optional[Request] = None,
):
    if not ctx:
        return
    log = AuditLog(
        organization_id=ctx.organization_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    session.add(log)


# ═══════════════════════════════════════════════════════════════
# RESEARCH
# ═══════════════════════════════════════════════════════════════

@app.post("/research", response_model=ResearchResponse)
async def run_research(
    request: ResearchRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    _ensure_app_state()
    task_id = request.stream_task_id or str(uuid.uuid4())
    conversation_id = request.conversation_id or str(uuid.uuid4())
    start_time = time.time()
    user_id = current_user.id
    logger.info(f"[{task_id}] Research by user={user_id} org={ctx.organization_id}: {request.query[:100]}...")

    pdf_paths = await _resolve_pdf_paths(session, request.document_ids)
    graph = app.state.graph
    app.state.stream_manager.get_or_create_stream(task_id)

    try:
        initial_state = {
            "query": request.query,
            "conversation_id": conversation_id,
            "plan": [],
            "plan_reasoning": None,
            "web_results": [],
            "document_chunks": [],
            "answer": None,
            "sources": [],
            "errors": [],
            "status": "running",
            "logs": [],
            "pdf_paths": pdf_paths,
            "execution_start": start_time,
            "agent_metrics": {},
            "stream_task_id": task_id,
            "llm_provider": request.llm_provider,
            "planner_model": request.planner_model,
            "research_model": request.research_model,
            "document_model": request.document_model,
            "answer_model": request.answer_model,
            "openrouter_key": request.openrouter_key,
            "debate_mode": request.debate_mode,
            "debate_perspectives": request.debate_perspectives,
            "debate_result": None,
            "has_evidence": False,
            "evidence_summary": None,
            "answer_mode": "normal",
            "fallback_reason": None,
        }
        result = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": task_id}})
        execution_time = time.time() - start_time
        app.state.stream_manager.close_stream(task_id)

        return ResearchResponse(
            task_id=task_id,
            conversation_id=conversation_id,
            query=request.query,
            answer=result.get("answer"),
            sources=result.get("sources", []),
            plan=result.get("plan", []),
            logs=result.get("logs", []),
            status=result.get("status", "completed"),
            errors=result.get("errors", []),
            execution_time=execution_time,
            plan_reasoning=result.get("plan_reasoning"),
            agent_metrics=result.get("agent_metrics", {}),
            cost_estimate=result.get("cost_estimate"),
            token_count=result.get("token_count"),
            debate=result.get("debate_result"),
            answer_mode=result.get("answer_mode", "normal"),
            evidence_summary=result.get("evidence_summary"),
            has_evidence=result.get("has_evidence", False),
        )
    except Exception as e:
        logger.error(f"[{task_id}] Research failed: {e}")
        app.state.stream_manager.close_stream(task_id)
        return ResearchResponse(
            task_id=task_id,
            conversation_id=conversation_id,
            query=request.query,
            status="failed",
            errors=[str(e)],
            execution_time=time.time() - start_time,
        )


@app.get("/research/stream/{task_id}")
async def subscribe_research_stream(task_id: str):
    _ensure_app_state()
    stream_mgr = app.state.stream_manager
    log_queue = stream_mgr.get_or_create_stream(task_id)
    return StreamingResponse(
        event_stream(task_id, log_queue),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.get("/research/stream")
async def research_stream(
    query: str = Query(..., min_length=1),
    conversation_id: Optional[str] = Query(None),
    document_ids: str = Query(default=""),
    current_user: Optional[User] = Depends(get_optional_user),
):
    _ensure_app_state()
    task_id = str(uuid.uuid4())
    conv_id = conversation_id or str(uuid.uuid4())
    doc_ids = [d.strip() for d in document_ids.split(",") if d.strip()]
    pdf_paths = []
    for d in doc_ids:
        resolved = os.path.normpath(os.path.join(UPLOAD_DIR, d))
        if not resolved.startswith(os.path.normpath(UPLOAD_DIR)):
            logger.warning(f"Rejected path traversal attempt: {d}")
            continue
        if os.path.exists(resolved):
            pdf_paths.append(resolved)
    stream_mgr = app.state.stream_manager
    log_queue = stream_mgr.create_stream(task_id)
    stream_mgr.push_log(task_id, make_log("planner", "analyze_query", "running", query[:100]))

    async def run_and_stream():
        try:
            initial_state = {
                "query": query, "conversation_id": conv_id,
                "plan": [], "plan_reasoning": None,
                "web_results": [], "document_chunks": [],
                "answer": None, "sources": [], "errors": [],
                "status": "running", "logs": [], "pdf_paths": pdf_paths,
                "execution_start": time.time(), "agent_metrics": {},
                "stream_task_id": task_id,
                "llm_provider": None, "planner_model": None,
                "research_model": None, "document_model": None,
                "answer_model": None, "openrouter_key": None,
                "debate_mode": False, "debate_perspectives": None,
                "debate_result": None,
                "has_evidence": False, "evidence_summary": None,
                "answer_mode": "normal", "fallback_reason": None,
            }
            graph = app.state.graph
            await graph.ainvoke(initial_state, config={"configurable": {"thread_id": task_id}})
            stream_mgr.push_log(task_id, make_log("system", "complete", "completed", "Execution finished"))
        except asyncio.CancelledError:
            logger.info(f"Research stream {task_id} cancelled")
            stream_mgr.push_log(task_id, make_log("system", "cancelled", "failed", "Client disconnected"))
        except Exception as e:
            stream_mgr.push_log(task_id, make_log("system", "error", "failed", str(e)))
        finally:
            stream_mgr.close_stream(task_id)

    async def stream_with_cleanup():
        task = asyncio.create_task(run_and_stream())
        try:
            async for event in event_stream(task_id, log_queue):
                yield event
        except asyncio.CancelledError:
            task.cancel()
            raise
        finally:
            if not task.done():
                task.cancel()
            await asyncio.sleep(0)

    return StreamingResponse(
        stream_with_cleanup(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/research/extract-entities")
async def research_extract_entities(request: ExtractEntitiesRequest):
    _ensure_app_state()
    result = await extract_entities(
        text=request.text,
        llm_provider=request.llm_provider,
        model=request.model,
    )
    return result


# ═══════════════════════════════════════════════════════════════
# CONVERSATIONS (tenant-aware)
# ═══════════════════════════════════════════════════════════════

@app.get("/conversations", response_model=list[ConversationResponse])
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
        Conversation.is_deleted == False,
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
        responses.append(ConversationResponse(
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
        ))
    return responses


@app.post("/conversations", response_model=ConversationResponse, status_code=201)
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

    await _log_audit(session, "conversation.created", "conversation", conv.id,
                     {"title": conv.title}, ctx)

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        message_count=0,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@app.get("/conversations/{conv_id}", response_model=ConversationDetail)
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
        select(Message).where(
            Message.conversation_id == conv.id,
        ).order_by(Message.created_at)
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


@app.patch("/conversations/{conv_id}", response_model=ConversationResponse)
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


@app.delete("/conversations/{conv_id}")
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
    await _log_audit(session, "conversation.deleted", "conversation", conv_id, {}, ctx)
    return {"status": "deleted"}


# ═══════════════════════════════════════════════════════════════
# DOCUMENTS (tenant-aware)
# ═══════════════════════════════════════════════════════════════

@limiter.limit("30/minute")
@app.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 50MB")

    file_id = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, file_id)
    try:
        content = await file.read()

        if not content[:4] == b"%PDF":
            raise HTTPException(status_code=400, detail="Invalid file format. Only PDF files are accepted")

        with open(file_path, "wb") as f:
            f.write(content)

        doc = Document(
            user_id=current_user.id,
            organization_id=ctx.organization_id,
            workspace_id=ctx.workspace_id,
            project_id=ctx.project_id,
            filename=file_id,
            original_filename=file.filename,
            size_bytes=len(content),
            mime_type="application/pdf",
            storage_path=file_path,
            storage_backend="local",
        )
        session.add(doc)
        await session.flush()

        await _log_audit(session, "document.uploaded", "document", doc.id,
                         {"filename": file.filename, "size": len(content)}, ctx)

        return {"document_id": doc.id, "filename": file.filename, "size": len(content), "status": "uploaded"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail="Failed to upload document")


@app.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    search: Optional[str] = Query(None),
    include_deleted: bool = Query(False),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    q = select(Document).where(Document.organization_id == ctx.organization_id)
    if not include_deleted:
        q = q.where(Document.is_deleted == False)
    if ctx.project_id:
        q = q.where(Document.project_id == ctx.project_id)
    elif ctx.workspace_id:
        q = q.where(Document.workspace_id == ctx.workspace_id)
    if search:
        q = q.where(
            or_(
                Document.original_filename.ilike(f"%{search}%"),
                Document.filename.ilike(f"%{search}%"),
            )
        )
    q = q.order_by(Document.created_at.desc())

    result = await session.execute(q)
    return [DocumentResponse.model_validate(d) for d in result.scalars().all()]


@app.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.organization_id == ctx.organization_id,
            Document.is_deleted == False,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@app.get("/documents/{doc_id}/versions", response_model=list[DocumentVersionResponse])
async def get_document_versions(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    doc_result = await session.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.organization_id == ctx.organization_id,
            Document.is_deleted == False,
        )
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")
    from backend.db.models import DocumentVersion
    result = await session.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == doc_id,
        ).order_by(DocumentVersion.version_number.desc())
    )
    return [DocumentVersionResponse.model_validate(v) for v in result.scalars().all()]


@app.delete("/documents/{doc_id}")
async def soft_delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.organization_id == ctx.organization_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_deleted = True
    doc.deleted_at = datetime.now(timezone.utc)
    await session.flush()
    await _log_audit(session, "document.deleted", "document", doc_id, {}, ctx)
    return {"status": "deleted"}


@app.post("/documents/{doc_id}/restore")
async def restore_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.organization_id == ctx.organization_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_deleted = False
    doc.deleted_at = None
    await session.flush()
    return {"status": "restored"}


# ═══════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════

@app.get("/notifications", response_model=list[NotificationResponse])
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
        q = q.where(Notification.is_read == False)
    q = q.order_by(Notification.created_at.desc()).limit(limit)
    result = await session.execute(q)
    return [NotificationResponse.model_validate(n) for n in result.scalars().all()]


@app.post("/notifications/{notif_id}/read")
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


@app.post("/notifications/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import update as sa_update
    await session.execute(
        sa_update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    await session.flush()
    return {"status": "all_read"}


# ═══════════════════════════════════════════════════════════════
# SEARCH (global, tenant-scoped)
# ═══════════════════════════════════════════════════════════════

@app.post("/search", response_model=list[SearchResult])
async def global_search(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    results = []
    pattern = f"%{body.query}%"

    if "conversations" in body.resource_types:
        conv_q = select(Conversation).where(
            Conversation.organization_id == ctx.organization_id,
            Conversation.is_deleted == False,
            Conversation.title.ilike(pattern),
        ).limit(body.limit)
        conv_result = await session.execute(conv_q)
        for conv in conv_result.scalars().all():
            results.append(SearchResult(
                resource_type="conversation",
                resource_id=conv.id,
                title=conv.title or "Untitled",
                snippet=conv.description or "",
                score=0.9,
                created_at=conv.created_at,
            ))

    if "documents" in body.resource_types:
        doc_q = select(Document).where(
            Document.organization_id == ctx.organization_id,
            Document.is_deleted == False,
            or_(
                Document.original_filename.ilike(pattern),
                Document.summary.ilike(pattern) if Document.summary else False,
            ),
        ).limit(body.limit)
        doc_result = await session.execute(doc_q)
        for doc in doc_result.scalars().all():
            results.append(SearchResult(
                resource_type="document",
                resource_id=doc.id,
                title=doc.original_filename,
                snippet=doc.summary or "",
                score=0.8,
                created_at=doc.created_at,
            ))

    if "messages" in body.resource_types:
        msg_q = select(Message).join(
            Conversation, Message.conversation_id == Conversation.id,
        ).where(
            Conversation.organization_id == ctx.organization_id,
            Conversation.is_deleted == False,
            Message.content.ilike(pattern),
        ).limit(body.limit)
        msg_result = await session.execute(msg_q)
        for msg in msg_result.scalars().all():
            results.append(SearchResult(
                resource_type="message",
                resource_id=msg.id,
                title=f"Message in {msg.conversation_id[:8]}...",
                snippet=msg.content[:200],
                score=0.7,
                created_at=msg.created_at,
            ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:body.limit]


# ═══════════════════════════════════════════════════════════════
# BILLING
# ═══════════════════════════════════════════════════════════════

@app.get("/billing/usage", response_model=BillingUsageResponse)
async def get_billing_usage(
    org_id: str = Query(..., alias="organization_id"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
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

@app.get("/api-keys", response_model=list[APIKeyResponse])
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


@app.post("/api-keys", response_model=APIKeyFullResponse, status_code=201)
async def create_api_key(
    body: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    import secrets, hashlib
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

    await _log_audit(session, "apikey.created", "api_key", api_key.id,
                     {"name": body.name}, ctx)

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


@app.delete("/api-keys/{key_id}")
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
    await _log_audit(session, "apikey.deleted", "api_key", key_id, {}, ctx)
    return {"status": "deleted"}


# ═══════════════════════════════════════════════════════════════
# AUDIT LOGS
# ═══════════════════════════════════════════════════════════════

@app.get("/audit-logs", response_model=list[AuditLogResponse])
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

@app.get("/models")
async def list_models():
    import httpx
    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
    registry = get_provider_registry()

    async with httpx.AsyncClient(timeout=10.0) as client:
        if provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                return {"provider": "openrouter", "models": [], "error": "No API key configured"}
            try:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                models = sorted(set(m["id"] for m in data.get("data", [])))
                return {"provider": "openrouter", "models": models, "count": len(models)}
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
            # Check registry for custom LLM providers
            all_providers = registry.list_llms()
            return {"provider": provider, "models": [], "available_providers": list(all_providers.keys())}


async def _resolve_pdf_paths(session: AsyncSession, document_ids: list[str]) -> list[str]:
    """Resolve document UUIDs to absolute filesystem paths via DB lookup."""
    if not document_ids:
        return []
    paths = []
    for doc_id in document_ids:
        result = await session.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.is_deleted == False,
            )
        )
        doc = result.scalar_one_or_none()
        if doc and doc.storage_path and os.path.exists(doc.storage_path):
            paths.append(doc.storage_path)
        else:
            logger.warning(f"Document not found or missing on disk: {doc_id}")
    return paths


# ═══════════════════════════════════════════════════════════════
# WEBSOCKET (Real-time Collaboration)
# ═══════════════════════════════════════════════════════════════

@app.websocket("/ws/workspace/{workspace_id}")
async def workspace_ws(workspace_id: str, ws: WebSocket):
    from backend.auth.jwt import decode_token as _decode_ws_token
    protocols = ws.headers.get("sec-websocket-protocol", "")
    parts = [p.strip() for p in protocols.split(",")] if protocols else []
    token = ""
    if len(parts) >= 2 and parts[0] == "research-swarm":
        token = parts[1]
    if not token:
        token = ws.query_params.get("token", "")
    user_id = ws.query_params.get("user_id", "")

    payload = _decode_ws_token(token)
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001, reason="Authentication required")
        return

    token_user_id = payload.get("sub")
    if user_id and user_id != token_user_id:
        await ws.close(code=4001, reason="User ID mismatch")
        return

    resolved_user_id = token_user_id or "anonymous"
    user_name = payload.get("name", "Anonymous")

    ws_user = None
    async for _ws_session in get_session():
        ws_result = await _ws_session.execute(
            select(Workspace).where(Workspace.id == workspace_id, Workspace.is_active == True)
        )
        workspace = ws_result.scalar_one_or_none()
        if not workspace:
            await ws.close(code=4004, reason="Workspace not found")
            return

        user_result = await _ws_session.execute(
            select(User).where(User.id == resolved_user_id, User.is_active == True)
        )
        ws_user = user_result.scalar_one_or_none()
        if not ws_user:
            await ws.close(code=4001, reason="User not found")
            return

        if not ws_user.is_superuser:
            member_result = await _ws_session.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == resolved_user_id,
                )
            )
            if not member_result.scalar_one_or_none():
                await ws.close(code=4003, reason="Not a member of this workspace")
                return
        break  # only one iteration needed

    await ws.accept()

    mgr = get_workspace_manager()
    room = mgr.get_or_create(workspace_id)
    conn = Connection(ws, resolved_user_id, user_name)
    room.add(conn)
    await mgr.broadcast_presence(workspace_id)

    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    finally:
        mgr.disconnect(workspace_id, resolved_user_id)


# ═══════════════════════════════════════════════════════════════
# PLUGINS
# ═══════════════════════════════════════════════════════════════

@app.get("/plugins", response_model=list[PluginStatus])
async def list_plugins():
    registry = get_plugin_registry()
    return [
        PluginStatus(
            name=spec.name,
            configured=registry.is_configured(spec.name),
            actions=spec.actions,
        )
        for spec in registry.list_plugins()
    ]


@app.post("/plugins/{name}/configure")
async def configure_plugin(name: str, req: PluginConfigRequest, current_user: User = Depends(get_current_user)):
    registry = get_plugin_registry()
    try:
        plugin = registry.get(name)
        plugin.config.update(req.config)
        plugin._initialized = False
        logger.info(f"Plugin '{name}' configured")
        return {"status": "configured", "name": name}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")


@app.post("/plugins/{name}/execute")
async def execute_plugin(name: str, action: str = Query(...), current_user: User = Depends(get_current_user), request: Request = None):
    registry = get_plugin_registry()
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        result = registry.execute(name, action, **body)
        return {"status": "ok", "name": name, "action": action, "result": result}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# PROVIDERS
# ═══════════════════════════════════════════════════════════════

@app.get("/providers", response_model=ProviderListResponse)
async def list_providers():
    registry = get_provider_registry()
    return ProviderListResponse(
        builtin=registry.list_all(),
        custom=[],
    )


@app.get("/providers/types")
async def list_provider_types():
    """Return available built-in providers grouped by type."""
    registry = get_provider_registry()
    return registry.list_all()


@app.post("/providers", response_model=ProviderResponse)
async def create_provider(
    req: ProviderCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    existing = await session.execute(
        select(Provider).where(
            Provider.organization_id == ctx.organization_id,
            Provider.name == req.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Provider '{req.name}' already exists")

    provider = Provider(
        name=req.name,
        provider_type=req.provider_type,
        provider_key=req.provider_key,
        config=req.config,
        organization_id=ctx.organization_id,
        created_by=current_user.id,
    )
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    return provider


@app.get("/providers/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: str,
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Provider).where(
            Provider.id == provider_id,
            Provider.organization_id == ctx.organization_id,
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@app.patch("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: str,
    req: ProviderUpdate,
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Provider).where(
            Provider.id == provider_id,
            Provider.organization_id == ctx.organization_id,
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if req.name is not None:
        provider.name = req.name
    if req.config is not None:
        provider.config = req.config
    if req.is_active is not None:
        provider.is_active = req.is_active

    await session.commit()
    await session.refresh(provider)
    return provider


@app.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: str,
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Provider).where(
            Provider.id == provider_id,
            Provider.organization_id == ctx.organization_id,
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    await session.delete(provider)
    await session.commit()
    return {"status": "deleted"}



