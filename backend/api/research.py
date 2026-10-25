"""Research execution, streaming, cancellation, and entity extraction."""

import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.entity_extractor import extract_entities
from backend.api.common import ensure_app_state, resolve_pdf_paths
from backend.api.research_persistence import finalize_supabase_run
from backend.api.stream import event_stream, make_log
from backend.auth.dependencies import get_current_user
from backend.auth.tenant import TenantContext, resolve_tenant_dependencies
from backend.core.ratelimit import limiter
from backend.db.models import User
from backend.db.schemas import ExtractEntitiesRequest, ResearchRequest, ResearchResponse
from backend.db.session import get_session
from backend.tools.tracer import get_tracer

router = APIRouter(tags=["research"])


# ═══════════════════════════════════════════════════════════════
# RESEARCH
# ═══════════════════════════════════════════════════════════════


@router.post("/research", response_model=ResearchResponse)
@limiter.limit("10/minute")
async def run_research(
    request: Request,
    body: ResearchRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    ensure_app_state(request.app)
    task_id = body.stream_task_id or str(uuid.uuid4())
    conversation_id = body.conversation_id or str(uuid.uuid4())
    start_time = time.time()
    user_id = current_user.id
    logger.info(
        f"[{task_id}] Research by user={user_id} org={ctx.organization_id}: {body.query[:100]}..."
    )

    pdf_paths = await resolve_pdf_paths(session, body.document_ids, ctx.organization_id)
    graph = request.app.state.graph
    request.app.state.stream_manager.get_or_create_stream(
        task_id, owner_user_id=user_id
    )

    # Phase 4: mirror this run into Supabase for the workspace UI + realtime.
    sb_session_id: Optional[str] = None
    sb_user_id: Optional[str] = None
    try:
        from backend.core.supabase import (
            create_session as sb_create_session,
            get_profile,
            insert_message as sb_insert_message,
        )

        sb_profile = get_profile(str(user_id))
        if sb_profile:
            sb_user_id = sb_profile["id"]
            row = sb_create_session(
                user_id=sb_user_id,
                title=body.query[:120],
                prompt=body.query,
                mode=body.mode or "quick",
                debate_enabled=bool(body.debate_mode),
            )
            sb_session_id = row["id"]
            sb_insert_message(session_id=sb_session_id, role="user", content=body.query)
            request.app.state.stream_manager.attach_persistence(
                task_id, supabase_user_id=sb_user_id, session_id=sb_session_id
            )
            request.app.state.stream_manager.push_log(
                task_id,
                make_log("system", "session", "created", sb_session_id),
            )
    except Exception as exc:  # pragma: no cover - resilience path
        logger.warning(f"[{task_id}] supabase session init skipped: {exc}")

    try:
        initial_state = {
            "query": body.query,
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
            "llm_provider": body.llm_provider,
            "planner_model": body.planner_model,
            "research_model": body.research_model,
            "document_model": body.document_model,
            "answer_model": body.answer_model,
            "openrouter_key": None,
            "debate_mode": body.debate_mode,
            "debate_perspectives": body.debate_perspectives,
            "debate_result": None,
            "has_evidence": False,
            "evidence_summary": None,
            "answer_mode": "normal",
            "fallback_reason": None,
        }
        tracer = get_tracer()
        tracer.start_trace(task_id, body.query)
        result = None
        run_status = "failed"

        # Run the graph as a tracked background task so a cancellation can
        # terminate in-flight LLM/provider work (and so client disconnects
        # cannot strand a half-finished run with no terminal state).
        graph_task = asyncio.create_task(
            graph.ainvoke(
                initial_state, config={"configurable": {"thread_id": task_id}}
            )
        )
        request.app.state.stream_manager.register_task(task_id, graph_task)
        try:
            with tracer.span("research_graph", "graph", span_type="node"):
                result = await graph_task
            run_status = _normalize_run_status(result)
        except asyncio.CancelledError:
            run_status = "cancelled"
            raise
        finally:
            tracer.end_trace(run_status)

        execution_time = time.time() - start_time
        request.app.state.stream_manager.push_log(
            task_id,
            make_log(
                "system",
                "status",
                run_status,
                (
                    "Research finished"
                    if run_status == "completed"
                    else "Research failed to complete"
                ),
            ),
        )
        request.app.state.stream_manager.close_stream(task_id)

        if sb_session_id:
            finalize_supabase_run(
                session_id=sb_session_id,
                user_id=sb_user_id,
                result=result or {},
                query=body.query,
                execution_time=execution_time,
            )

        return ResearchResponse(
            task_id=task_id,
            conversation_id=conversation_id,
            query=body.query,
            supabase_session_id=sb_session_id,
            answer=result.get("answer"),
            sources=result.get("sources", []),
            plan=result.get("plan", []),
            logs=result.get("logs", []),
            status=run_status,
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
    except asyncio.CancelledError:
        logger.info(f"[{task_id}] Research cancelled")
        request.app.state.stream_manager.push_log(
            task_id,
            make_log("system", "cancelled", "cancelled", "Research cancelled"),
        )
        request.app.state.stream_manager.close_stream(task_id)
        if sb_session_id:
            try:
                from backend.core.supabase import update_session

                update_session(sb_session_id, status="cancelled", error=None)
            except Exception as exc:  # pragma: no cover
                logger.warning(f"[{task_id}] supabase cancel persist skipped: {exc}")
        raise
    except Exception as e:
        logger.error(f"[{task_id}] Research failed: {e}")
        request.app.state.stream_manager.close_stream(task_id)
        if sb_session_id:
            try:
                from backend.core.supabase import log_activity, update_session

                update_session(sb_session_id, status="failed", error=str(e)[:500])
                log_activity(
                    user_id=sb_user_id,
                    action="research.failed",
                    entity_type="research_session",
                    entity_id=sb_session_id,
                    metadata={"query": body.query[:200]},
                )
            except Exception as exc:  # pragma: no cover
                logger.warning(f"[{task_id}] supabase failure persist skipped: {exc}")
        return ResearchResponse(
            task_id=task_id,
            conversation_id=conversation_id,
            query=body.query,
            status="failed",
            errors=[str(e)],
            execution_time=time.time() - start_time,
        )


def _normalize_run_status(result: Optional[Dict[str, Any]]) -> str:
    """Coerce a graph result into one of the terminal research statuses.

    ``completed`` / ``failed`` / ``cancelled`` pass through. Anything else
    (including a run that ended without ever reporting a status) is marked
    ``failed`` so no path can leave a run permanently stuck in
    ``running``.
    """
    status = (result or {}).get("status", "")
    if status in ("completed", "failed", "cancelled"):
        return status
    if isinstance(result, dict):
        result["status"] = "failed"
        errors = result.setdefault("errors", [])
        note = "Research ended without a terminal status and was marked failed"
        if note not in [str(e) for e in errors]:
            errors.append(note)
    return "failed"


@router.post("/research/{task_id}/cancel")
async def cancel_research_task(
    task_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Cancel an in-flight research run.

    Cancellation is restricted to the owner of the task stream. The
    background graph task is cancelled so in-flight LLM/provider work
    terminates; the run handler persists the run as ``cancelled``.
    """
    ensure_app_state(request.app)
    stream_mgr = request.app.state.stream_manager
    owner = stream_mgr.get_owner(task_id)
    if owner and owner != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner of this task")
    task = stream_mgr.get_task(task_id)
    if task is None or task.done():
        return {"status": "cancelled", "task_id": task_id, "already_done": True}
    task.cancel()
    logger.info(f"[{task_id}] Cancel requested by user {current_user.id}")
    return {"status": "cancelled", "task_id": task_id}


@router.get("/research/stream/{task_id}")
async def subscribe_research_stream(
    task_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Subscribe to the SSE log stream for a research task.

    Streams are owned by the user who started the task: subscribing to
    another user's task id is rejected so logs (which may contain the
    research query) never leak cross-tenant.
    """
    ensure_app_state(request.app)
    stream_mgr = request.app.state.stream_manager
    if not stream_mgr.has_stream(task_id):
        raise HTTPException(status_code=404, detail="Unknown task stream")
    owner = stream_mgr.get_owner(task_id)
    if owner and owner != current_user.id:
        raise HTTPException(status_code=403, detail="Not the owner of this task stream")
    log_queue = stream_mgr.get_stream(task_id)
    return StreamingResponse(
        event_stream(task_id, log_queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/research/stream")
async def research_stream(
    request: Request,
    query: str = Query(..., min_length=1),
    conversation_id: Optional[str] = Query(None),
    document_ids: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    ensure_app_state(request.app)
    task_id = str(uuid.uuid4())
    conv_id = conversation_id or str(uuid.uuid4())
    doc_ids = [d.strip() for d in document_ids.split(",") if d.strip()]
    pdf_paths = await resolve_pdf_paths(session, doc_ids, ctx.organization_id)
    stream_mgr = request.app.state.stream_manager
    log_queue = stream_mgr.create_stream(task_id, owner_user_id=current_user.id)
    stream_mgr.push_log(
        task_id, make_log("planner", "analyze_query", "running", query[:100])
    )

    async def run_and_stream():
        try:
            initial_state = {
                "query": query,
                "conversation_id": conv_id,
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
                "execution_start": time.time(),
                "agent_metrics": {},
                "stream_task_id": task_id,
                "llm_provider": None,
                "planner_model": None,
                "research_model": None,
                "document_model": None,
                "answer_model": None,
                "openrouter_key": None,
                "debate_mode": False,
                "debate_perspectives": None,
                "debate_result": None,
                "has_evidence": False,
                "evidence_summary": None,
                "answer_mode": "normal",
                "fallback_reason": None,
            }
            graph = request.app.state.graph
            await graph.ainvoke(
                initial_state, config={"configurable": {"thread_id": task_id}}
            )
            stream_mgr.push_log(
                task_id,
                make_log("system", "complete", "completed", "Execution finished"),
            )
        except asyncio.CancelledError:
            logger.info(f"Research stream {task_id} cancelled")
            stream_mgr.push_log(
                task_id,
                make_log("system", "cancelled", "failed", "Client disconnected"),
            )
        except Exception as e:
            stream_mgr.push_log(task_id, make_log("system", "error", "failed", str(e)))
        finally:
            stream_mgr.close_stream(task_id)

    async def stream_with_cleanup():
        """Stream SSE events while the research task runs in the background.

        On client disconnect the generator is cancelled: the background task
        is cancelled too and awaited (with a hard timeout) so in-flight LLM
        calls terminate instead of leaking past disconnect.
        """
        task = asyncio.create_task(run_and_stream())
        stream_mgr.register_task(task_id, task)
        try:
            async for event in event_stream(task_id, log_queue):
                yield event
        except asyncio.CancelledError:
            task.cancel()
            raise
        finally:
            if not task.done():
                task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            stream_mgr.unregister_task(task_id, task)
            stream_mgr.close_stream(task_id)

    return StreamingResponse(
        stream_with_cleanup(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/research/extract-entities")
@limiter.limit("30/minute")
async def research_extract_entities(
    request: Request,
    body: ExtractEntitiesRequest,
    current_user: User = Depends(get_current_user),
):
    ensure_app_state(request.app)
    result = await extract_entities(
        text=body.text,
        llm_provider=body.llm_provider,
        model=body.model,
    )
    return result
