# ResearchSwarm v0.8.2

This release completes the production-readiness milestone for ResearchSwarm.

## 🔒 Security

- Fixed cross-tenant organization authorization (C1)
- Fixed cross-tenant document access in research streaming (C2)
- Hardened Supabase bridge token generation (C3)
- Implemented refresh token rotation, reuse detection, and session revocation (C4)
- Added request and WebSocket rate limiting
- Added production secret validation with fail-fast startup
- Improved SSE ownership and cancellation handling

## 🗄 Database & Infrastructure

- Repaired Alembic migration chain
- Deterministic fresh-database migrations
- Improved deployment safety
- Strengthened tenant isolation

## 🧪 Testing

- Backend security regression suite
- Migration chain verification
- Planner/graph test infrastructure stabilization
- **190/190 tests passing**
- Ruff clean

## 📄 Report Experience

- Rich Markdown report viewer
- Citation hover cards
- Evidence scoring
- Sticky source panel
- Markdown export
- Print-optimized PDF export

## 📚 Developer Experience

- Fresh-machine verification
- Deterministic pnpm installs
- CONTRIBUTING.md
- E2E seed and cleanup tooling
- Improved local development workflow

## Thanks

This release marks the completion of the production-readiness milestone.

The next milestone will focus on expanding the user experience based on real-world feedback.
