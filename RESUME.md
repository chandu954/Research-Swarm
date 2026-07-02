# Resume Bullets — ResearchSwarm AI

## Strong Bullet (Lead with this)

> Designed and implemented a production-style multi-agent AI research platform using LangGraph, FastAPI, ChromaDB, PostgreSQL, and Ollama with dynamic model routing, RAG, JWT authentication, Docker, CI/CD, and comprehensive automated testing.

## Supporting Bullets (pick 2-3 for your resume)

> Built a LangGraph StateGraph orchestrating 4 AI agents (Planner, Web Research, Document QA, Answer Synthesis) with parallel fan-out execution and cross-encoder reranking, achieving sub-15s end-to-end research cycles.

> Implemented a Retrieval-Augmented Generation pipeline using ChromaDB for vector storage and nomic-embed-text for embeddings, with Gemma3-based cross-encoder relevance scoring replacing cosine similarity for higher retrieval quality.

> Developed a FastAPI backend with async SQLAlchemy, JWT access/refresh tokens, Google OAuth 2.0, SSE streaming for real-time agent logs, and a singleton Tool Registry with per-call execution tracing.

> Containerized the full stack with Docker Compose (PostgreSQL 16, Ollama with GPU, Python 3.12, Node 20) and configured CI/CD via GitHub Actions with 4 parallel jobs (lint, test, typecheck, build).

> Wrote 60+ automated tests across 6 test files covering planner JSON parsing, LangGraph error handling, tool execution, authentication flows, and API endpoints, achieving >30% coverage with mocked external dependencies.

## Resume Section Placement

Put the strong bullet under **Projects** or **Experience**:

```
Projects

ResearchSwarm AI | LangGraph, FastAPI, Next.js, PostgreSQL, ChromaDB, Ollama
- Designed and implemented a production-style multi-agent AI research platform using
  LangGraph, FastAPI, ChromaDB, PostgreSQL, and Ollama with dynamic model routing,
  RAG, JWT authentication, Docker, CI/CD, and comprehensive automated testing.
- Built a LangGraph StateGraph orchestrating 4 AI agents with parallel fan-out
  execution and cross-encoder reranking, achieving sub-15s research cycles.
- Containerized the full stack with Docker Compose and configured GitHub Actions CI
  with 4 parallel jobs (lint, test, typecheck, build).
```

## LinkedIn Headline

> AI Software Engineer | Multi-Agent Systems | LangGraph • FastAPI • RAG • LLMs

## Technical Skills Section

```
AI/ML: LangGraph, LangChain, RAG, ChromaDB, Ollama, LLM Prompt Engineering
Backend: Python, FastAPI, SQLAlchemy, PostgreSQL, Alembic, WebSockets, SSE
Auth: JWT, OAuth 2.0, bcrypt, python-jose, authlib
DevOps: Docker, Docker Compose, GitHub Actions, Vercel, Railway, Render
Frontend: TypeScript, Next.js 15, React 19, TailwindCSS, Framer Motion
Testing: pytest, Playwright, CI/CD pipelines
```
