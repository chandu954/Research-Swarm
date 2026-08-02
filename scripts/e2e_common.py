"""Shared helpers for the e2e cleanup/seed scripts.

Safe by default: refuses to touch anything unless SUPABASE_URL points at a
local development instance (or E2E_FORCE=1 is set).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_ENV = ROOT / "backend" / ".env"


def load_env() -> None:
    """Load backend/.env into the process environment (never overrides)."""
    if not BACKEND_ENV.exists():
        return
    for line in BACKEND_ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


def assert_safe_target() -> None:
    """Abort unless we are pointed at a local Supabase instance."""
    url = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
    if os.environ.get("E2E_FORCE") == "1":
        return
    host = url.split("://")[-1].split("/")[0]
    if ":" in host:
        host = host.rsplit(":", 1)[0]
    if host not in ("127.0.0.1", "localhost", "0.0.0.0"):
        print(f"ABORT: SUPABASE_URL={url} is not a local dev instance.", file=sys.stderr)
        print("Set E2E_FORCE=1 only if you really mean it.", file=sys.stderr)
        sys.exit(3)


def resolve_profile_id(email: str) -> str | None:
    """Resolve the auth uid for an email via rs_profiles."""
    sys.path.insert(0, str(ROOT / "backend"))
    from backend.core.supabase import get_supabase

    rows = get_supabase().table("rs_profiles").select("id").eq("email", email).execute()
    return rows.data[0]["id"] if rows.data else None


def test_email() -> str:
    return os.environ.get("E2E_TEST_EMAIL", "ph4-test@example.com")


def psql(sql: str) -> str | None:
    """Run a read-only diagnostic query through the local supabase postgres."""
    container = os.environ.get("SUPABASE_DB_CONTAINER", "supabase_db_resume-lm")
    try:
        out = subprocess.run(
            ["docker", "exec", container, "psql", "-U", "postgres", "-d", "postgres", "-t", "-c", sql],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode == 0:
            return out.stdout
    except Exception as exc:  # noqa: BLE001 - diagnostics only
        print(f"  (psql diagnostics unavailable: {exc})", file=sys.stderr)
    return None


def list_recursive(bucket: str, prefix: str, depth: int = 0) -> list[str]:
    """Return full object paths under prefix (files only)."""
    from backend.core.supabase import get_supabase

    if depth > 6:
        return []
    paths: list[str] = []
    items = get_supabase().storage.from_(bucket).list(prefix, {"limit": 1000})
    for item in items or []:
        if item.get("metadata"):
            paths.append(prefix + item["name"])
        else:
            paths.extend(list_recursive(bucket, prefix + item["name"] + "/", depth + 1))
    return paths
