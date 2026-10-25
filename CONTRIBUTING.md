# Contributing to ResearchSwarm

This guide describes setup and verification commands for a clean checkout. A separate
clone of `main` at the current HEAD passed frozen frontend install, lint, typecheck,
coverage, and production build checks; that clone did not include this workspace's
uncommitted changes.

## Prerequisites

| Tool        | Version                          | Notes                                        |
| ----------- | -------------------------------- | -------------------------------------------- |
| Node.js     | 24.x | Required by `frontend/package.json` |
| pnpm        | 11.28.7 | Pinned by `frontend/package.json` |
| Python      | 3.12 | CI runtime; Python 3.14 is unverified |
| Docker      | any recent                       | Required for the local Supabase stack        |
| Supabase CLI | any recent | `supabase start` brings up the local stack |

## 1. Backend

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

Copy the template and fill in values:

```bash
cp backend/.env.example backend/.env
```

Required keys in `backend/.env`:

| Key                          | Purpose                                        |
| ---------------------------- | ---------------------------------------------- |
| `SUPABASE_URL`               | Local Supabase API, e.g. `http://127.0.0.1:54321` |
| `SUPABASE_ANON_KEY`          | Supabase anon key                              |
| `SUPABASE_SERVICE_ROLE_KEY`  | Service-role key (server-side writes)          |
| `SUPABASE_JWT_SECRET`        | Supabase JWT secret (auth bridging)            |
| `JWT_SECRET_KEY`             | Application JWT signing secret                 |
| `LLM_PROVIDER`               | `openrouter` (or `ollama`)                     |
| `OPENROUTER_API_KEY`         | Required when `LLM_PROVIDER=openrouter`        |
| `PLANNER_MODEL` / `RESEARCH_MODEL` / `DOCUMENT_MODEL` / `ANSWER_MODEL` / `EMBEDDING_MODEL` | Model routing |
| `UPLOAD_DIR`, `VECTOR_DB_PATH` | Local files: `data/uploads`, `data/chroma_db`  |

Start the API:

```bash
.venv/bin/uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

Health check: `curl http://127.0.0.1:8000/health`

## 2. Supabase (local)

```bash
supabase start        # from the repo root (supabase/config.toml, project "resume-lm")
```

- API: `http://127.0.0.1:54321`
- Migrations in `supabase/migrations/` apply automatically on start.
- Buckets used by the app: `rs_documents`, `rs_reports`, `rs_avatars`.

## 3. Frontend

```bash
cd frontend
pnpm install --frozen-lockfile
```

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key from supabase status>
```

Run:

```bash
pnpm dev              # http://localhost:3000
```

CORS note: the backend allows `http://localhost:3000` as an origin. Browse the app
via `localhost`, not `127.0.0.1`, or auth health checks will be blocked.

## 4. Demo data (E2E account)

A seeded test account and workspace make manual QA and E2E runs repeatable:

```bash
pnpm seed:e2e         # or: make seed-e2e       (idempotent, safe to re-run)
pnpm cleanup:e2e      # or: make cleanup-e2e    (removes only the test account's data)
```

- Email: `ph4-test@example.com`
- Password: `testpass123`
- The seed inserts a demo session, reports (with citations), documents, collection,
  metrics, and recent searches. Cleanup also handles the legacy local sqlite mirror
  and `data/uploads/`.

## 5. Tests

Backend checks (run from `backend/`, as in CI):

```bash
PYTHONPATH=.. ../.venv/bin/python -m pytest tests/ -v --cov=backend --cov-config=.coveragerc --cov-report=term-missing --cov-fail-under=90
```

Frontend checks (run from `frontend/`):

```bash
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test:coverage
pnpm test:e2e
pnpm build
```

## 6. Build from a clean checkout

```bash
git clone <repo-url> research-swarm && cd research-swarm/frontend
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test:coverage
pnpm build
```

If `pnpm install` warns about ignored build scripts (`sharp`, `unrs-resolver`),
approvals belong in `frontend/pnpm-workspace.yaml` (`allowBuilds`), not in
`package.json` — pnpm 11 no longer reads the `pnpm` field there.

## Checklist before opening a PR

- [ ] `pnpm typecheck` clean
- [ ] `pnpm test:coverage` passes configured coverage thresholds
- [ ] `pnpm build` succeeds from a fresh `node_modules`
- [ ] Feature covered by a unit test when practical
- [ ] UI changes smoke-tested against the seeded E2E account
- [ ] Schema changes are additive only (schema v1 is frozen) and ship with a migration in `supabase/migrations/`
