# ResearchSwarm — Production Deployment

Target architecture (confirmed): **Vercel frontend** + **always-on backend
service (Railway or Render)** + **hosted Postgres** + **Supabase project**
(realtime/persistence mirror). The backend is intentionally NOT deployed to
Vercel Functions: it is a stateful, disk-backed service (see sections below).

---

## 1. What Railway/Render must provide

The backend process requires:

| Requirement | Why | Platform setup |
|---|---|---|
| **Persistent volume mounted at `/data`** | Local disk is the source of truth for: uploaded PDFs (`/data/uploads`), ChromaDB vector store (`/data/chroma_db`), conversation memory (`/data/memory`), trace/log files (`/data/logs`) | Railway: `[[volumes]] name="backend_data" mount="/data"` (already in `backend/railway.toml`). Render persistent disks equivalent. Without the volume every redeploy wipes uploads + vector index |
| **Postgres URL** (`DATABASE_URL`) | System-of-record DB (`backend/db/models.py`). Code defaults to SQLite for local dev — production must set `postgresql+asyncpg://...` (asyncpg pooling is already configured; `sslmode` is stripped automatically) | Railway Postgres / Render Postgres / Neon / Supabase. Run `alembic upgrade head` after deploy |
| **Always-on runtime** | In-memory state: SSE `StreamManager` queues, WebSocket `WorkingRoom`s, rate-limit buckets, LangGraph `MemorySaver` checkpoints, plugin configuration. Restarting kills in-flight streams/connections | Railway: `restartPolicyType = "ON_FAILURE"`. Both platforms keep the container warm |
| **Port** | Render injects `$PORT`; Railway uses the `[service] port = 8000` | `backend/Dockerfile` now runs `uvicorn ... --port "${PORT:-8000}"` |
| **Health checks** | `/health` + `/ready` | Railway: `[service]`; Render: `healthCheckPath: /health` (in `render.yaml`) |

Without a persistent volume, PDF uploads and ChromaDB retrieval will not
survive restarts — this is the #1 deploy-time failure mode for this app.

## 2. Secrets (server-side only — never `NEXT_PUBLIC_*`)

Set on the backend host: `ENVIRONMENT=production` (engages the fail-closed
startup validation), `JWT_SECRET_KEY` (≥32 chars), `JWT_SECRET_KEYS_ROTATION`
(optional), `OPENROUTER_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`SUPABASE_JWT_SECRET`, `SUPABASE_BRIDGE_SECRET`, `DATABASE_URL`,
`ENCRYPTION_KEY`,
Google/GitHub/Microsoft OAuth client IDs + secrets (redirect URIs must be
the deployed backend, e.g. `https://<api-host>/auth/google/callback`),
plugin tokens (`GITHUB_TOKEN`, `NOTION_TOKEN`, `SLACK_TOKEN`).

`backend/core/config.validate_secrets()` refuses to boot when
`ENVIRONMENT=production` with weak or missing secrets — in particular it
rejects a local `SUPABASE_URL` (`127.0.0.1` / `localhost`) and missing
service-role configuration — get this right before the first deploy.

## 3. CORS

`CORS_ORIGINS` is a deployment-time decision. Defaults are local-dev origins
only; there is no hardcoded production domain, and `*` with credentials is
rejected at boot. Set it to the exact frontend origin(s), e.g.:

```bash
https://research-swarm.vercel.app
```

The same list gates WebSocket handshakes (`Origin` header) for
`/ws/workspace/{id}`.

## 4. Vercel (frontend) envs

| Variable | Scope | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Production + Preview | Required. No fallback in production builds — a missing value raises a clear configuration error instead of pointing at localhost |
| `NEXT_PUBLIC_SUPABASE_URL` | Production + Preview | Public Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Production + Preview | Publishable anon key only |

See `frontend/.env.example` for documented names. Never put the
service-role key in a `NEXT_PUBLIC_*` variable.

## 5. Persistent disk inventory (what lives in `/data`)

| Path | Written by | Loss on restart |
|---|---|---|
| `/data/uploads` | `POST /upload` (`api/main.py`) | Uploaded PDFs unreadable → download 404s |
| `/data/chroma_db` | ChromaDB `PersistentClient` | RAG over documents breaks; embeddings re-created empty |
| `/data/memory` | ConversationMemory (JSON) | Semantic memory reset |
| `/data/logs` | logging + tracer | Traces/logs lost |
| `research_swarm.db` | SQLite (dev/tests only) | N/A in prod (Postgres is the DB) |

## 6. Deploy sequence

1. Provision Postgres + Supabase project; run backend migrations (`alembic upgrade head`)
2. Deploy backend to Railway/Render with volume + envs; verify `GET /health`
3. Set `CORS_ORIGINS` on the backend to the real frontend domain
4. Deploy frontend to Vercel with the three public envs
5. Run the post-deployment smoke tests (see `docs/audit/PRODUCTION_AUDIT.md` §8)