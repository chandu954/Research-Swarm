"""FastAPI application factory and HTTP middleware for ResearchSwarm AI."""

# Load local configuration before application modules snapshot environment values.
# ruff: noqa: E402
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from slowapi.errors import RateLimitExceeded

from backend.agents.graph import create_research_graph
from backend.api.auth import router as auth_router
from backend.api.bootstrap import lifespan
from backend.api.bootstrap import register_builtin_plugins as _register_builtin_plugins
from backend.api.common import (
    ensure_app_state,
    get_cors_origins,
    sign_document_download,
    verify_document_download,
)
from backend.api.conversations import router as conversations_router
from backend.api.documents import router as documents_router
from backend.api.health import router as health_router
from backend.api.metrics import router as metrics_router
from backend.api.organizations import router as org_router
from backend.api.plugins import router as plugins_router
from backend.api.realtime import router as realtime_router
from backend.api.research import _normalize_run_status
from backend.api.research import router as research_router
from backend.api.workspace import router as workspace_router
from backend.api.workspaces import router as workspaces_router
from backend.core.ratelimit import limiter, rate_limit_exceeded_handler
from backend.core.registry import get_plugin_registry

app = FastAPI(
    title="ResearchSwarm AI",
    description="Multi-Agent Research Operating System — Multi-Tenant Platform",
    version="3.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start = time.time()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        duration_ms = round((time.time() - start) * 1000, 2)
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        logger.debug(
            f"[{request_id}] {request.method} {request.url.path} → "
            f"{response.status_code} ({duration_ms}ms)"
        )
        return response
    except Exception as exc:
        logger.error(
            f"[{request_id}] {request.method} {request.url.path} → error: {exc}"
        )
        duration_ms = round((time.time() - start) * 1000, 2)
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "Something went wrong while processing your request.",
                "request_id": request_id,
            },
            headers={
                "X-Request-ID": request_id,
                "X-Response-Time-Ms": str(duration_ms),
            },
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
app.include_router(workspaces_router)
app.include_router(metrics_router)
app.include_router(health_router)
app.include_router(research_router)
app.include_router(conversations_router)
app.include_router(documents_router)
app.include_router(workspace_router)
app.include_router(realtime_router)
app.include_router(plugins_router)

# Backwards-compatible re-exports for tests and external callers.
_ensure_app_state = ensure_app_state
_sign_document_download = sign_document_download
_verify_document_download = verify_document_download

__all__ = [
    "app",
    "create_research_graph",
    "get_plugin_registry",
    "_ensure_app_state",
    "_normalize_run_status",
    "_register_builtin_plugins",
    "_sign_document_download",
    "_verify_document_download",
]
