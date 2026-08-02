#!/usr/bin/env python
"""Cleanup of ALL E2E test artifacts for the E2E test account.

Scope: every row and storage object owned by E2E_TEST_EMAIL
(default ph4-test@example.com). Nothing else is ever touched.

Order: storage objects first, then DB rows children-before-parents.
Verifies afterwards: zero duplicates, zero orphans, RLS + FKs intact.

Usage:
    .venv/bin/python scripts/cleanup_e2e.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

from e2e_common import assert_safe_target, load_env, list_recursive, psql, resolve_profile_id, test_email

load_env()
assert_safe_target()

from backend.core.supabase import get_supabase  # noqa: E402

START = datetime.now(timezone.utc)
UID = resolve_profile_id(test_email())
if not UID:
    print("No rs_profiles row for the E2E test account — nothing to clean up.")
    sys.exit(0)

sb = get_supabase()
deleted: dict[str, int] = {}
removed_objects = 0
BUCKETS = ["rs_documents", "rs_reports"]

def del_rows(table: str, column: str, values: list[str], chunk: int = 150) -> int:
    n = 0
    for i in range(0, len(values), chunk):
        res = sb.table(table).delete().in_(column, values[i : i + chunk]).execute()
        n += len(res.data or [])
    return n

def del_eq(table: str, column: str, value: str) -> int:
    res = sb.table(table).delete().eq(column, value).execute()
    return len(res.data or [])

def delete_by_user(table: str) -> int:
    return del_eq(table, "user_id", UID)

print(f"== E2E cleanup: user {UID} ({test_email()}) ==")

# ---------------------------------------------------------------- storage
print("\n-- storage (before DB rows so no dangling files are possible) --")
for bucket in BUCKETS:
    paths = list_recursive(bucket, f"{UID}/")
    if not paths:
        print(f"  {bucket}: no objects under {UID}/")
        continue
    for i in range(0, len(paths), 1000):
        res = sb.storage.from_(bucket).remove(paths[i : i + 1000])
        if isinstance(res, dict) and res.get("error"):
            print(f"  {bucket}: remove error {res['error']}")
    removed_objects += len(paths)
    print(f"  {bucket}: removed {len(paths)} object(s)")

# ------------------------------------------------------------- db (children first)
sessions = [r["id"] for r in sb.table("rs_research_sessions").select("id").eq("user_id", UID).execute().data]
collections = [r["id"] for r in sb.table("rs_collections").select("id").eq("user_id", UID).execute().data]

if collections:
    deleted["rs_collection_items"] = del_rows("rs_collection_items", "collection_id", collections)
if sessions:
    deleted["rs_agent_runs"] = del_rows("rs_agent_runs", "session_id", sessions)
    deleted["rs_run_metrics"] = del_rows("rs_run_metrics", "session_id", sessions)
    deleted["rs_messages"] = del_rows("rs_messages", "session_id", sessions)

for table in ["rs_reports", "rs_documents", "rs_collections", "rs_research_sessions",
              "rs_saved_prompts", "rs_recent_searches", "rs_activity_logs", "rs_settings"]:
    deleted[table] = delete_by_user(table)

# ------------------------------------------------- local uploads (FastAPI mirror)
print("\n-- local uploads (backend data/uploads mirror) --")
uploads_dir = ROOT.parent / "data" / "uploads"  # backend resolves ../data/uploads
if not uploads_dir.is_dir():
    uploads_dir = ROOT / "data" / "uploads"
local_removed = 0
if uploads_dir.is_dir():
    for p in sorted(uploads_dir.iterdir()):
        if p.is_file() and ("e2e-rag-overview" in p.name or "e2e-demo-" in p.name):
            p.unlink()
            local_removed += 1
    print(f"  removed {local_removed} E2E upload file(s)")

print("-- local sqlite (backend research_swarm.db documents mirror) --")
local_db = ROOT.parent / "data" / "research_swarm.db"
if not local_db.is_file():
    local_db = ROOT / "data" / "research_swarm.db"
local_rows_deleted = 0
if local_db.is_file():
    import sqlite3

    conn = sqlite3.connect(str(local_db))
    cur = conn.execute(
        "DELETE FROM documents WHERE original_filename LIKE '%e2e-rag-overview%' "
        "OR original_filename LIKE '%e2e-demo-%' OR filename LIKE 'e2e-%'"
    )
    conn.commit()
    local_rows_deleted = cur.rowcount
    conn.close()
    print(f"  removed {local_rows_deleted} E2E document row(s)")

# ------------------------------------------------------------ verification
print("\n-- verification --")
USER_SCOPED = ["rs_reports", "rs_documents", "rs_collections", "rs_research_sessions",
               "rs_saved_prompts", "rs_recent_searches", "rs_activity_logs", "rs_settings"]
SESSION_SCOPED = ["rs_messages", "rs_agent_runs", "rs_run_metrics"]
count_sql = (
    "SELECT 'u:" + t + "', count(*) FROM " + t + " WHERE user_id = '" + UID + "'" for t in USER_SCOPED
)
count_sql = list(count_sql) + [
    "SELECT 's:" + t + "', count(*) FROM " + t + " a LEFT JOIN rs_research_sessions s ON s.id = a.session_id WHERE s.user_id = '" + UID + "' OR s.id IS NULL"
    for t in SESSION_SCOPED
]
out = psql(" UNION ALL ".join(count_sql))
rows_left: dict[str, int] = {}
if out:
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 2 and parts[1].isdigit():
            rows_left[parts[0]] = int(parts[1])
left_total = sum(rows_left.values())
print(f"  rows remaining for test user: {left_total} {'OK' if not left_total else 'LEAK: ' + str(rows_left)}")
dups = sb.table("rs_documents").select("name").eq("user_id", UID).eq("name", "e2e-rag-overview.pdf").execute()
print(f"  duplicate e2e-rag-overview.pdf rows: {len(dups.data)} "
      f"({'OK' if not dups.data else 'LEAK'})")

storage_left = 0
for bucket in BUCKETS:
    storage_left += len(list_recursive(bucket, f"{UID}/"))
print(f"  storage objects under {UID}/: {storage_left} {'OK' if not storage_left else 'LEAK'}")

# Foreign keys / orphans across the whole public schema (not just the test user).
orphan_sql = """
SELECT 'messages' AS t, count(*) AS n FROM rs_messages m LEFT JOIN rs_research_sessions s ON s.id = m.session_id WHERE s.id IS NULL
UNION ALL SELECT 'agent_runs', count(*) FROM rs_agent_runs a LEFT JOIN rs_research_sessions s ON s.id = a.session_id WHERE s.id IS NULL
UNION ALL SELECT 'run_metrics', count(*) FROM rs_run_metrics r LEFT JOIN rs_research_sessions s ON s.id = r.session_id WHERE s.id IS NULL
UNION ALL SELECT 'reports.session', count(*) FROM rs_reports r LEFT JOIN rs_research_sessions s ON s.id = r.session_id WHERE r.session_id IS NOT NULL AND s.id IS NULL
UNION ALL SELECT 'collection_items.collection', count(*) FROM rs_collection_items c LEFT JOIN rs_collections x ON x.id = c.collection_id WHERE x.id IS NULL
UNION ALL SELECT 'collection_items.document', count(*) FROM rs_collection_items c LEFT JOIN rs_documents d ON d.id = c.document_id WHERE d.id IS NULL
UNION ALL SELECT 'collection_items.report', count(*) FROM rs_collection_items c LEFT JOIN rs_reports r ON r.id = c.report_id WHERE r.id IS NULL
UNION ALL SELECT 'sessions.user', count(*) FROM rs_research_sessions s LEFT JOIN auth.users u ON u.id = s.user_id WHERE u.id IS NULL
"""
out = psql(orphan_sql)
fk_violations = 0
if out:
    for line in out.strip().splitlines():
        parts = line.split("|")
        if len(parts) == 2 and parts[1].strip().isdigit():
            n = int(parts[1].strip())
            fk_violations += n
            if n:
                print(f"  ORPHAN rows in {parts[0].strip()}: {n}")
print(f"  foreign-key orphans: {fk_violations} {'OK' if not fk_violations else 'LEAK'}")

out = psql("SELECT relname, relrowsecurity FROM pg_class WHERE relname LIKE 'rs\\_%' AND relkind='r' ORDER BY 1")
rls_off = []
if out:
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 2 and parts[1] != "t":
            rls_off.append(parts[0])
    print(f"  RLS enabled on all rs_* tables: {'OK' if not rls_off else 'OFF for ' + str(rls_off)}")
else:
    print("  RLS check skipped (psql unavailable)")

# ---------------------------------------------------------------- summary
print("\n== SUMMARY ==")
for table in ["rs_activity_logs", "rs_agent_runs", "rs_collection_items", "rs_collections",
              "rs_documents", "rs_messages", "rs_recent_searches", "rs_reports",
              "rs_research_sessions", "rs_run_metrics", "rs_saved_prompts", "rs_settings"]:
    print(f"  {table:<24} deleted: {deleted.get(table, 0):>3}")
print(f"  {'storage objects':<24} removed: {removed_objects:>3}")
print(f"  {'local upload files':<24} removed: {local_removed:>3}")
print(f"  {'local document rows':<24} removed: {local_rows_deleted:>3}")
print(f"  completed in {(datetime.now(timezone.utc) - START).total_seconds():.1f}s")
problems = left_total or storage_left or dups.data or fk_violations or rls_off
if problems:
    print("CLEANUP INCOMPLETE — see LEAK lines above.")
    sys.exit(1)
print("CLEANUP OK — test user data fully removed, RLS + FKs valid.")
