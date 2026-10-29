# Architecture

## Overview

Research-Swarm is a full-stack monorepo with a FastAPI/LangGraph backend and a Next.js 15 frontend. It uses Supabase for auth/storage, ChromaDB for vector search, and Ollama for local LLM inference. Docker Compose brings up the entire stack with one command.

## Module Map

### Backend (`backend/`)

```
backend/
  api/
    main.py          # FastAPI app factory, lifespan, middleware
    auth.py          # Auth router core (JWT, sessions, devices)
    auth_oauth.py    # Google OAuth endpoints
    auth_mfa.py      # Magic link, MFA, password reset endpoints
    stream.py        # SSE stream manager
    health.py        # /health, /ready, /debug/db endpoints
    metrics.py       # /metrics endpoint
    conversations.py # Conversation CRUD
    organizations.py # Organization CRUD
    workspaces.py    # Workspace CRUD
    documents.py     # Document upload/read/download
    common.py        # Shared utilities
    bootstrap.py     # App lifespan, plugin registration
  auth/
    jwt.py           # JWT token creation/validation
    password.py      # Password hashing/verification
    dependencies.py  # Auth dependency injection
    providers.py     # Auth providers (magic link, MFA, OAuth)
    tenant.py        # Multi-tenant context resolution
  core/
    logging.py       # Structured JSON logging (loguru)
    registry.py      # Plugin registry
    ratelimit.py     # Rate limiting utilities
    supabase.py      # Supabase bridge
    config.py        # Application configuration
  db/
    session.py       # Async SQLAlchemy session/engine
    models/          # SQLAlchemy models (package)
      base.py        # SoftDeleteMixin, TenantMixin
      auth.py        # User, UserSession, UserDevice
      org.py         # Organization, OrganizationMember, Workspace, WorkspaceMember, Project
      content.py     # Collection, Conversation, Message, Document, DocumentVersion, DocumentChunk
      activity.py    # ResearchTask, KnowledgeGraphNode, KnowledgeGraphEdge, Memory, Notification, AuditLog, APIKey, BillingRecord, Tag, TagAssignment, Bookmark, Provider
  agents/
    graph.py         # LangGraph research graph
    memory.py        # Conversation memory provider
    merge.py         # Research merge helper
    planner.py       # Research planner
    research_agent.py# Research agent
    debate_agent.py  # Debate agent
    document_agent.py# Document agent
    entity_extractor.py
  tools/
    registry.py      # Tool registry
    search.py        # Web search tools
    pdf_loader.py    # PDF text extraction
    browser.py       # Web page reader
    code_executor.py # Python/shell execution
    tracer.py        # Execution tracer
  providers/
    embedding.py     # Embedding providers (Ollama, OpenRouter)
    llm.py           # LLM providers
    memory.py        # Memory providers
    search.py        # Search providers (DuckDuckGo, Bing, Serper)
    storage.py       # Storage providers
    vector_db.py     # Vector DB providers (ChromaDB)
  tests/             # Unit and integration tests
```

### Frontend (`frontend/`)

```
frontend/
  app/               # Next.js App Router pages
  components/        # React components
  lib/               # Client libraries (api-client, auth-state-machine, errors)
  __tests__/         # Vitest unit and component tests
```

## Request Flow

1. Client sends HTTP request to FastAPI backend
2. `backend/api/main.py` creates the FastAPI app with lifespan (bootstrap)
3. Request passes through middleware (request ID, rate limiting, CORS)
4. Route handler in `backend/api/auth.py` (or other route module) processes the request
5. Business logic in agents/tools/providers executes
6. Database operations via SQLAlchemy async session
7. Response returned with consistent error schema and request ID headers

## Data Model

Core entities (in `backend/db/models/`):

- **User** - Accounts with email/password, OAuth, MFA
- **Organization** - Multi-tenant organizations with members
- **Workspace** - Workspaces within organizations
- **Project** - Projects within workspaces
- **Conversation** - Chat conversations with messages
- **Document** - Uploaded documents with versions and chunks
- **ResearchTask** - Async research task tracking
- **KnowledgeGraphNode/Edge** - Knowledge graph entities
- **Memory** - Multi-level memory store
- **Notification** - User notifications
- **AuditLog** - Audit trail
- **APIKey** - API access keys
- **BillingRecord** - Usage billing records

## Technology Stack

- **Backend**: FastAPI, SQLAlchemy (async), Alembic, LangGraph, ChromaDB, Ollama, OpenRouter, Supabase, Loguru
- **Frontend**: Next.js 15, React 19, Tailwind CSS, Vitest, Playwright
- **Infrastructure**: Docker Compose, PostgreSQL 16, Redis (optional)

## Observability

- `/health` - Health check with database and LLM provider connectivity
- `/ready` - Readiness probe (database only)
- `/metrics` - System metrics (uptime, plugins, configuration)
- Structured JSON logging via `backend/core/logging.py`
- Optional Sentry error tracking behind `SENTRY_DSN`
