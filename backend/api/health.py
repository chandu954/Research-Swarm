"""Health, readiness, and database diagnostics endpoints."""

import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from backend.api.common import ensure_app_state
from backend.core.registry import get_plugin_registry

router = APIRouter(tags=["health"])


# ── Health ──────────────────────────────────────────────────────


@router.get("/health")
async def health_check(request: Request):
    ensure_app_state(request.app)
    registry = request.app.state.registry
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
        provider_checks["openrouter"] = (
            "ok" if os.getenv("OPENROUTER_API_KEY") else "unconfigured"
        )

    return {
        "status": "healthy" if db_ok is True else "degraded",
        "version": "3.0.0",
        "uptime": time.time() - request.app.state.start_time,
        "tools_available": len(registry.list_tools()),
        "providers": list(get_plugin_registry().list_types()),
        "checks": provider_checks,
    }


@router.get("/debug/db")
async def debug_db(request: Request):
    """Debug: test DB tables and run migration."""
    ensure_app_state(request.app)
    from sqlalchemy import select
    from sqlalchemy import text as sa_text

    from backend.db.models import User
    from backend.db.session import _engine, get_session

    async with _engine.begin() as conn:
        rows = await conn.execute(
            sa_text(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'users'"
            )
        )
        cols = [r[0] for r in rows.fetchall()]

    r = {"columns": cols, "ok": True}

    try:
        async for session in get_session():
            await session.execute(select(User).limit(1))
            break
        r["select_ok"] = True
    except Exception as e:
        r["select_ok"] = False
        r["select_error"] = str(e)

    return r


@router.get("/ready")
async def ready_check(request: Request):
    """Lightweight readiness probe (no auth, fast)."""
    ensure_app_state(request.app)
    db_ok = True
    try:
        from backend.db.session import get_session

        async for session in get_session():
            await session.execute(select(func.now()))
            break
    except Exception as e:
        db_ok = str(e)
    if db_ok is True:
        return {"status": "ready"}
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "detail": f"Database: {db_ok}"},
    )
