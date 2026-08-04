# Backend Production-Readiness Audit

- **Date:** 2026-08-02
- **Scope:** `backend/` (FastAPI + LangGraph + async SQLAlchemy + Supabase bridge), read-only.
- **Method:** 4 independent parallel audits (architecture, API/security, DB/migrations, production ops) followed by targeted source verification of every Critical/High claim.
- **Status:** No code modified. All claims below verified against source at file:line.

---

## Executive summary

The backend is **not production-ready**. The architecture (modular layering, plugin registry, provider abstraction, RLS policies, async pipeline) is genuinely good and worth keeping, but there are **4 critical multi-tenant boundary failures**, a **broken migration chain**, and **zero automated tests**. Any one of the Critical items allows cross-tenant data access or account takeover on a shared deployment.

Estimated hardening effort: **1.5–2 weeks** of focused work before v1.0.

## Scores

| Category | Score | One-line rationale |
|---|---|---|
| Architecture & Design | 7.5/10 | Clean layering, plugin registry, provider abstraction, graph pipeline |
| Security | 3.0/10 | 4 verified tenant-boundary/token criticals; weak defaults |
| API & Auth compliance | 5.5/10 | Solid REST/SSE contract; inconsistent tenant binding, no rate limits |
| Performance & Resilience | 5.5/10 | Async throughout; sync Supabase on loop, fire-and-forget cancellation |
| Data integrity & migrations | 4.0/10 | Broken 0001→0002 chain, type drift, PK NULL semantics |
| Production readiness & ops | 5.0/10 | Docker/railway present; no secrets validation, no CI tests, no graceful shutdown |
| **Composite** | **≈ 5.1/10** | **Pre-1.0; not deployable for multi-tenant use as-is** |

---

## CRITICAL (fix before any shared deployment)

### C1. Cross-tenant org mutation (IDOR) — `api/organizations.py:249–339`
`add_member`, `update_member_role`, `remove_member`, `update_organization` all write against the **path** `org_id` while the permission check (`require_permission("manage_members")`) resolves the **request header** org context. A user holding `manage_members` in org A can operate on org B's members/org via the path parameter. Verified at `organizations.py:249–262` (endpoint takes `org_id: str` from path; membership created without asserting path `org_id == ctx.organization_id`).

**Fix:** single tenant source of truth. Resolve org from token/session only; assert `org_id == ctx.organization_id` at the top of every org endpoint (or drop the path param entirely and use the header).

### C2. Cross-tenant document access via research — `api/main.py:706–721`, `1544–1561`
`GET /research/stream` takes `document_ids` as **raw filenames in the shared `UPLOAD_DIR`** and reads any file that exists on disk — no `require_permission`, no user scoping. Any authenticated user can feed another user's uploaded filename and have the graph process it. The traversal guard (`main.py:713–719`) blocks `..` but not cross-tenant reads. `_resolve_pdf_paths` (`main.py:1544+`) likewise filters only on `is_deleted`, not on ownership.

**Fix:** resolve documents through the DB keyed by `(id, user_id)`; never touch `UPLOAD_DIR` paths directly in request scope; add `require_permission` to the endpoint.

### C3. Deterministic low-entropy bridge passwords — `core/supabase.py:20, 82–99`
Browser Supabase sessions are minted with `password = sha256("rs-bridge::{user_id}::{secret}")`, where `_BRIDGE_SECRET` **defaults to `"dev"`** (`supabase.py:20`). Offline-crackable in bulk from any leaked auth row, and every deployment that omits `JWT_SECRET_KEY` runs on the published default secret.

**Fix:** fail-closed startup validation (refuse to boot if secret unset in prod); store a random per-user secret server-side instead of deriving from the public user id; derive with Argon2id/bcrypt-style KDF.

### C4. Refresh tokens: no DB check, no rotation, no revocation — `api/auth.py:209–222`
`POST /refresh` validates the JWT signature only; it never consults the `UserSession` table (hash check, revocation, expiry) and issues a fresh access+refresh pair without rotating the old one. Stolen refresh tokens work until JWT expiry; "logout" and session revocation are effectively cosmetic.

**Fix:** verify `refresh_token_hash` against `UserSession`, rotate on use (reuse detection = revoke), enforce session TTL, and purge expired rows.

---

## HIGH

### H1. Migration chain is broken — `alembic/versions/0001_initial.py`, `0002_multi_tenant.py`
`0002` references a `workspaces` table that `0001` never creates; PK/FK types drift between `UUID` and `VARCHAR(36)` across models vs migrations. A fresh production `alembic upgrade head` fails. The working local DB was created by the Supabase SQL bootstrap instead.

**Fix:** rewrite `0001` as a correct baseline (single canonical type for ids), rebuild `0002`, and add a CI step that runs `alembic upgrade head` on an empty Postgres.

### H2. SSE cancellation is fire-and-forget — `api/main.py:764–775`
Client disconnect calls `task.cancel()` then `await asyncio.sleep(0)`; the graph task swallows `CancelledError` (logs and returns) and the coroutine is never awaited to completion. In-flight LLM calls can keep running/billing after disconnect. The POST variant (`main.py:507–514`) awaits inline so it stops promptly — only the GET stream path leaks.

**Fix:** `await task` with a short timeout after cancel; add a hard kill timeout; track running tasks in the StreamManager for shutdown.

### H3. No rate limiting anywhere — `api/auth.py`, `api/main.py`
No throttling on login/refresh, research, or entity extraction. Password brute force, refresh-token spraying, and provider-cost abuse are all unguarded.

**Fix:** token-bucket middleware (slowapi or in-house) with per-route limits and per-user/per-IP keys.

### H4. Default secrets deployable — `railway.toml:12–36`, `core/supabase.py:20`
`railway.toml` defines env vars with **no `JWT_SECRET_KEY` / `SUPABASE_BRIDGE_SECRET`**; combined with the `"dev"` fallback, a Railway deploy boots with the public default secret.

**Fix:** startup validation that fails fast on missing/placeholder secrets in non-dev environments; add the vars to `railway.toml`.

### H5. No central configuration module — `core/`, `api/`, `llm/`
Env vars are parsed ad hoc across modules with **conflicting defaults** (e.g. `LLM_PROVIDER` defaulting to `"ollama"` in one place and `"openrouter"` in another). Behavior silently differs by code path.

**Fix:** a single `core/config.py` (pydantic-settings) with one default per key, plus startup cross-validation.

### H6. Sync Supabase calls on the event loop — `core/supabase.py:51–140`, `api/stream.py:140–160`
`ensure_supabase_user`, `create_browser_session`, and the run-mirroring in StreamManager call the **blocking** Supabase client on the asyncio loop. Under load this stalls every in-flight research stream.

**Fix:** offload to a thread/executor or use the async client (httpx-based); make mirroring async and non-fatal to research.

### H7. Uploaded files have no lifecycle — `api/main.py:988–1001` and delete paths
Files accumulate in `UPLOAD_DIR` forever; `delete_document` removes the DB row but not the file. No per-user quota, no sweep, no S3.

**Fix:** delete storage on document delete; add quota enforcement and a periodic sweep task.

---

## MEDIUM

1. **Duplicate collection items allowed** — `rs_collection_items` composite PK `(collection_id, report_id, document_id)` with nullable `report_id`/`document_id`; NULLs never collide in Postgres, so identical "report-only" items can be inserted repeatedly; no `ON CONFLICT` handling (`supabase/migrations/20260802180000_rs_persistence.sql:112–119`).
2. **`metrics` reports per-type, not per-plugin** — `api/metrics.py:28` passes `ptype` to `is_configured`, so all plugins of a type share one boolean and a missing provider key is not surfaced.
3. **Research endpoint has no limits** — no cap on `document_ids` count, no max-runtime guard (`api/main.py:706–721`).
4. **Zero backend tests** — no `tests/` directory exists; auth, tenant binding, upload, and migration behavior are entirely unguarded.
5. **No request correlation IDs** — logs are not tenant-attributed and can't be stitched across a run; error paths can surface internals.
6. **`Dockerfile` unpinned** — unpinned base image and `pip install` without lockfile/hash pinning; supply-chain drift.
7. **WebSocket manager never prunes dead connections** — `api/websocket.py` ConnectionManager retains sockets until error; memory creep on long-lived deployments.
8. **Supabase session minted on every login** — `api/auth.py:52–79` calls `create_browser_session` even when the user already has one; extra auth traffic and churn.
9. **No graceful shutdown** — `StreamManager` state and pending mirrors are lost on SIGTERM; run persistence is fire-and-forget (`api/stream.py:140`).
10. **Path-traversal logging only** — upload `file_id` is `uuid4_ + filename` so traversal is neutralized, but rejected attempts aren't alarmed/audited (`api/main.py:995`).

---

## Strengths (keep these)

- **Modular layering:** `api/` (HTTP), `core/` (registry, providers, cache), `llm/` (provider impls), `db/`, `auth/` — clean seams, plugin registry working end-to-end.
- **RLS discipline:** scoped service-role usage, row-level policies per table, own-profile/collection policies in `supabase/migrations/20260802180000_rs_persistence.sql`.
- **Upload basics done right:** 50MB cap, `%PDF` magic check, uuid-prefixed names (traversal-safe), traversal attempts logged.
- **Async-first pipeline** with queue adapters, per-run trace spans, structured logs.
- **RBAC concept is sound** (roles, members, org context) — the binding, not the design, is broken.
- **No secrets committed**; seeded E2E data has a documented cleanup path.

---

## Recommended fix order (sprintable)

1. **Tenant binding** — C1 + C2 (single org source of truth; research scoped by user).
2. **Token/session hardening** — C4 (rotation, DB check, revocation) then C3 (secret validation, per-user secret).
3. **Migrations** — H1 rebuild baseline + CI `upgrade head` test.
4. **Cancellation & limits** — H2, H3, M3.
5. **Config module + secrets validation** — H5, H4.
6. **Tests** — M4: auth, tenant IDOR, upload adversarial, migration freshness; wire into CI.
7. **Ops** — H6, H7, M6–M9.
