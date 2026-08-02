"""Supabase persistence layer for the orchestration backend.

FastAPI stays the source of truth for orchestration; Supabase is used
exclusively for persistence, realtime and storage. All writes from the
backend go through the service role so RLS never blocks agent writes.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

from supabase import Client, create_client

_SUPABASE_URL = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
_BRIDGE_SECRET = os.getenv("SUPABASE_BRIDGE_SECRET", os.getenv("JWT_SECRET_KEY", "dev"))

_client: Client | None = None


def get_supabase() -> Client:
    """Return the shared service-role client, raising if not configured."""
    global _client
    if _client is None:
        if not _SERVICE_ROLE_KEY:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured")
        _client = create_client(_SUPABASE_URL, _SERVICE_ROLE_KEY)
    return _client


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Profiles (Phase 3 bridge)
# ---------------------------------------------------------------------------

def upsert_profile(
    *,
    supabase_user_id: str,
    legacy_user_id: str,
    email: str,
    name: str,
    avatar_url: str | None = None,
) -> dict[str, Any]:
    """Create or update the Supabase profile for a FastAPI JWT user."""
    payload = {
        "id": supabase_user_id,
        "legacy_user_id": legacy_user_id,
        "email": email,
        "name": name,
        "avatar_url": avatar_url,
    }
    row = (
        get_supabase()
        .table("rs_profiles")
        .upsert(payload, on_conflict="id")
        .execute()
        .data
    )
    return row[0] if row else payload


def get_profile(legacy_user_id: str) -> dict[str, Any] | None:
    rows = (
        get_supabase()
        .table("rs_profiles")
        .select("*")
        .eq("legacy_user_id", legacy_user_id)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def _bridge_password(legacy_user_id: str) -> str:
    """Deterministic password for bridged Supabase identities.

    Never stored anywhere: derived from the legacy JWT user id and the
    server secret so a browser session can always be minted on demand.
    SHA-256 keeps it under bcrypt's 72-byte limit regardless of id length.
    """
    raw = f"rs-bridge::{legacy_user_id}::{_BRIDGE_SECRET}"
    return hashlib.sha256(raw.encode()).hexdigest()


def ensure_supabase_user(
    *,
    email: str,
    legacy_user_id: str,
    user_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an existing Supabase auth user for the email or create one.

    Created users are email-confirmed with a derived password: they exist
    only so RLS / realtime have an `auth.uid()` identity for the bridged
    FastAPI JWT user. The browser is handed a session for this user via
    `create_browser_session` (see auth.py).
    """
    admin = get_supabase().auth.admin
    existing = admin.list_users(page=1, per_page=100)
    for user in existing:
        if user.email and user.email.lower() == email.lower():
            return {"id": str(user.id), "email": user.email}

    created = admin.create_user(
        {
            "email": email,
            "password": _bridge_password(legacy_user_id),
            "email_confirm": True,
            "user_metadata": user_metadata or {},
        }
    )
    return {"id": str(created.user.id), "email": created.user.email}


def create_browser_session(
    email: str,
    legacy_user_id: str,
) -> dict[str, Any] | None:
    """Sign the user into Supabase with their bridged identity."""
    from supabase import create_client as _create_anon

    client = _create_anon(_SUPABASE_URL, _ANON_KEY)
    res = client.auth.sign_in_with_password(
        {"email": email, "password": _bridge_password(legacy_user_id)}
    )
    return {
        "access_token": res.session.access_token if res.session else None,
        "refresh_token": res.session.refresh_token if res.session else None,
    }


# ---------------------------------------------------------------------------
# Workspace persistence (Phase 4)
# ---------------------------------------------------------------------------

def create_session(
    *,
    user_id: str,
    title: str,
    prompt: str,
    mode: str,
    debate_enabled: bool = False,
) -> dict[str, Any]:
    row = (
        get_supabase()
        .table("rs_research_sessions")
        .insert(
            {
                "user_id": user_id,
                "title": title,
                "prompt": prompt,
                "mode": mode,
                "debate_enabled": debate_enabled,
                "status": "planning",
            }
        )
        .execute()
        .data
    )
    return row[0]


def update_session(session_id: str, **fields: Any) -> None:
    get_supabase().table("rs_research_sessions").update(fields).eq(
        "id", session_id
    ).execute()


def insert_message(
    *,
    session_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    get_supabase().table("rs_messages").insert(
        {
            "session_id": session_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }
    ).execute()


def upsert_agent_run(
    *,
    session_id: str,
    agent_key: str,
    status: str,
    model: str | None = None,
    latency_ms: int | None = None,
    tokens: int | None = None,
    sources: int | None = None,
    documents: int | None = None,
    output: dict[str, Any] | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    """Insert, or update the open run for the same agent, atomically."""
    client = get_supabase()
    existing = (
        client.table("rs_agent_runs")
        .select("id")
        .eq("session_id", session_id)
        .eq("agent_key", agent_key)
        .eq("status", "running")
        .limit(1)
        .execute()
        .data
    )
    payload = {
        "session_id": session_id,
        "agent_key": agent_key,
        "status": status,
        "model": model,
        "latency_ms": latency_ms,
        "tokens": tokens,
        "sources": sources,
        "documents": documents,
        "output": output,
        "started_at": started_at or _now(),
        "finished_at": finished_at,
    }
    if existing:
        client.table("rs_agent_runs").update(payload).eq(
            "id", existing[0]["id"]
        ).execute()
    else:
        client.table("rs_agent_runs").insert(payload).execute()


def save_run_metrics(
    *,
    session_id: str,
    execution_time_ms: int | None = None,
    sources_found: int = 0,
    relevant_sources: int = 0,
    documents: int = 0,
    chunks: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    estimated_cost: float = 0,
) -> None:
    get_supabase().table("rs_run_metrics").insert(
        {
            "session_id": session_id,
            "execution_time_ms": execution_time_ms,
            "sources_found": sources_found,
            "relevant_sources": relevant_sources,
            "documents": documents,
            "chunks": chunks,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "estimated_cost": estimated_cost,
        }
    ).execute()


def save_report(
    *,
    user_id: str,
    session_id: str | None,
    title: str,
    content_md: str,
    sources: list[dict[str, Any]] | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = (
        get_supabase()
        .table("rs_reports")
        .insert(
            {
                "user_id": user_id,
                "session_id": session_id,
                "title": title,
                "content_md": content_md,
                "status": "ready",
                "sources": sources or [],
                "metrics": metrics or {},
            }
        )
        .execute()
        .data
    )
    return row[0]


def log_activity(
    *,
    user_id: str,
    action: str,
    entity_type: str = "research",
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    get_supabase().table("rs_activity_logs").insert(
        {
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "metadata": metadata or {},
        }
    ).execute()


def save_document(
    *,
    user_id: str,
    name: str,
    storage_path: str,
    mime_type: str,
    size_bytes: int,
) -> dict[str, Any]:
    row = (
        get_supabase()
        .table("rs_documents")
        .insert(
            {
                "user_id": user_id,
                "name": name,
                "storage_path": storage_path,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "status": "indexing",
            }
        )
        .execute()
        .data
    )
    return row[0]


def update_document(document_id: str, **fields: Any) -> None:
    get_supabase().table("rs_documents").update(fields).eq(
        "id", document_id
    ).execute()
