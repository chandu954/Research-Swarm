"""Shared helpers used by the API routers."""

import hashlib
import hmac
import os
import re
import time
import unicodedata
from typing import Optional

from fastapi import Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.graph import create_research_graph
from backend.agents.memory import get_memory
from backend.api.stream import get_stream_manager
from backend.auth.jwt import get_jwt_secret
from backend.auth.tenant import TenantContext
from backend.core.registry import get_plugin_registry
from backend.db.models import AuditLog, Document
from backend.tools.registry import get_registry


UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")
for _directory in [UPLOAD_DIR, "./data/chroma_db", "./data/memory", "./data/logs"]:
    os.makedirs(_directory, exist_ok=True)


def slugify(name: str) -> str:
    """Create a URL-safe slug, falling back to ``org`` for empty input."""
    normalized = unicodedata.normalize("NFKD", name.lower().replace(" ", "-"))
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9-]", "", ascii_str)
    return (slug or "org")[:80]


def ensure_app_state(app) -> None:
    """Populate process-wide singletons for direct route invocation in tests."""
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


def get_cors_origins() -> list[str]:
    default = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000"
    origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", default).split(",")
        if origin.strip()
    ]
    if "*" in origins:
        raise RuntimeError(
            "CORS_ORIGINS must not contain '*' together with allow_credentials=True — "
            "list exact production origins instead"
        )
    return origins


async def log_audit(
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
    entry = AuditLog(
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
    session.add(entry)


def sign_document_download(doc_id: str, org_id: str, expires: int) -> str:
    """HMAC-SHA256 signature binding doc_id + org_id + expiry."""
    message = f"{doc_id}:{org_id}:{expires}".encode()
    return hmac.new(get_jwt_secret().encode(), message, hashlib.sha256).hexdigest()


def verify_document_download(doc_id: str, org_id: str, expires: int, sig: str) -> bool:
    """Verify an HMAC signature and its expiry window."""
    if not sig or not expires:
        return False
    now = int(time.time())
    if expires < now or expires > now + 3600:
        return False
    expected = sign_document_download(doc_id, org_id, expires)
    return hmac.compare_digest(expected, sig)


async def resolve_pdf_paths(
    session: AsyncSession,
    document_ids: list[str],
    organization_id: str,
) -> list[str]:
    """Resolve document UUIDs to filesystem paths, enforcing tenant ownership."""
    if not document_ids:
        return []
    paths = []
    for doc_id in document_ids:
        result = await session.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.organization_id == organization_id,
                Document.is_deleted.is_(False),
            )
        )
        doc = result.scalar_one_or_none()
        if doc and doc.storage_path and os.path.exists(doc.storage_path):
            paths.append(doc.storage_path)
        else:
            logger.warning(f"Document not found or missing on disk: {doc_id}")
    return paths
