# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Split `backend/api/auth.py` into `auth.py` (core), `auth_oauth.py` (Google OAuth), `auth_mfa.py` (magic link/MFA/password reset)
- Split `backend/tests/test_realtime_stream_infra.py` (1317 LOC) into 12 focused test files
- Split `backend/tests/test_workspace_documents_units.py` (943 LOC) into 5 focused test files
- Split `backend/tests/test_coverage_critical_paths.py` (942 LOC) into 4 focused test files
- Split `backend/tests/test_memory_graph_plugins.py` (907 LOC) into 3 focused test files
- Split `backend/db/models.py` (666 LOC) into package with base/auth/org/content/activity sub-modules
- Added `backend/pyproject.toml` with ruff and black config (line-length 100)
- Added `frontend/eslint.config.mjs` (flat config for ESLint 9), removed legacy `.eslintrc.json`
- Added `.prettierrc`, `.editorconfig`, `.pre-commit-config.yaml`
- Added `.gitattributes` with linguist-generated for `database.types.ts`
- Added `.python-version` (3.12) and `.nvmrc` (24)
- Split `backend/requirements.txt` into runtime + `requirements-dev.txt`
- Added `.github/dependabot.yml` (pip, npm, github-actions, docker; weekly)
- Added `.github/workflows/release.yml` for tag-based releases
- Added pull request and issue templates
- Added `make test`, `make lint`, `make check`, `make bootstrap` targets
- Raised frontend vitest coverage thresholds to 60/50/50/60
- Renamed `confirmPassword` to `passwordConfirmation` in login form
- Added `scripts/check_env_example.py` for env var validation
- Added `.gitleaks.toml` with allowlist
- Added Sentry error tracking behind `SENTRY_DSN`
- Added `LICENSE`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`
- Added `.devcontainer/devcontainer.json`

### Fixed

- Backend ruff violations (unused imports, unsorted imports)
- Frontend ESLint config conflict (removed legacy `.eslintrc.json`)

## [0.8.2] - 2026-10-XX

### Added

- Initial public release
- Multi-tenant FastAPI/LangGraph backend
- Next.js 15 frontend with Tailwind CSS
- Supabase integration
- Docker Compose setup
- CI/CD pipeline with GitHub Actions

## [0.8.1] - 2026-10-XX

### Added

- Authentication with JWT, OAuth, MFA, magic links
- Real-time collaboration with WebSockets
- Document upload and management

## [0.8.0] - 2026-10-XX

### Added

- Initial project scaffold
- Research agent with LangGraph
- Vector search with ChromaDB
