<div align="center">
  <img src="assets/banner.png" alt="ResearchSwarm AI Banner" width="100%">
  <h1>ResearchSwarm AI</h1>
  <p><strong>Production-Grade Multi-Agent Research System powered by LangGraph + Ollama</strong></p>

  <p>
    <a href="#features">Features</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#quick-start">Quick Start</a> •
    <a href="#demo">Demo</a> •
    <a href="#api">API</a> •
    <a href="#deploy">Deploy</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python" alt="Python">
    <img src="https://img.shields.io/badge/Next.js-15-000000?logo=next.js" alt="Next.js">
    <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi" alt="FastAPI">
    <img src="https://img.shields.io/badge/LangGraph-FF6F00?logo=langgraph" alt="LangGraph">
    <img src="https://img.shields.io/badge/Ollama-000000?logo=ollama" alt="Ollama">
    <img src="https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql" alt="PostgreSQL">
    <img src="https://img.shields.io/badge/Docker-2496ED?logo=docker" alt="Docker">
    <img src="https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=githubactions" alt="CI">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
</div>

---

ResearchSwarm AI orchestrates multiple AI agents to perform web research, analyze PDF documents, and generate cited answers using Retrieval-Augmented Generation (RAG) — all powered by open-source LLMs through [Ollama](https://ollama.ai). Built with LangGraph for stateful multi-agent workflows, FastAPI for the API layer, and a polished Next.js frontend.

**Live Demo:** [https://researchswarm.vercel.app](https://researchswarm.vercel.app) (coming soon)

---

## Demo

**[`assets/demo.mp4`](assets/demo.mp4)** — 2:50 story-driven walkthrough with narration (problem → architecture → live LangGraph research → OpenRouter settings → codebase → engineering highlights → CTA).

Re-record: `cd scripts && npm run demo:story` (backend `:8000` + frontend `:3001` required).

---

## Features

### Core
- **Multi-Agent Orchestration** — Planner, Web Research, Document QA, and Answer agents coordinated via LangGraph `StateGraph` with parallel fan-out/fan-in
- **Web Research** — Real-time search via DuckDuckGo with result extraction and summarization
- **PDF Analysis** — Upload and process PDFs with PyMuPDF text extraction + ChromaDB vector search
- **RAG Pipeline** — Semantic search over document chunks with nomic-embed-text embeddings and cross-encoder reranking (Gemma3)
- **Source Citations** — Every answer includes numbered references to web sources and document pages
- **Cross-Encoder Reranking** — Gemma3-based relevance scoring replaces cosine similarity for higher-quality retrieval
- **Semantic Memory** — Conversation history stored as embeddings via ChromaDB for long-term recall

### Platform
- **JWT Authentication** — Access + refresh tokens (30min/7d) with bcrypt hashing
- **Google OAuth 2.0** — One-click login via authlib
- **PostgreSQL Persistence** — Async SQLAlchemy + asyncpg with Alembic migrations
- **SSE Streaming** — Real-time agent logs pushed to the frontend via Server-Sent Events
- **Agent Metrics** — Per-node latency, model name, result counts returned in API responses
- **Tool Registry** — Singleton registry with execution tracing and call history
- **Docker Compose** — One-command startup with PostgreSQL 16, Ollama (GPU), backend, and frontend

### Observability
- **Execution Timeline** — Agent cards with latency bars and live status updates
- **Span Tracing** — JSON-based trace persistence with `start_span` / `end_span`
- **Health Endpoint** — `GET /health` returns status, version, uptime, and registered tool count

---

## Architecture

```mermaid
flowchart TB
    subgraph Frontend["Next.js 15 Frontend"]
        UI[Chat UI]
        TL[Execution Timeline]
        PV[PDF Preview]
    end

    subgraph Backend["FastAPI Server"]
        API[REST + SSE Endpoints]
        AUTH[JWT + OAuth]
        LG[LangGraph StateGraph]
    end

    subgraph Agents["LangGraph Nodes"]
        direction LR
        P[Planner<br/>Qwen3 14B]
        R[Research Agent<br/>Llama3 8B]
        D[Document Agent<br/>Gemma3 12B]
        M[Merge]
        AN[Answer Agent<br/>Gemma3 12B]
    end

    subgraph Storage["Persistence"]
        PG[(PostgreSQL)]
        CB[(ChromaDB)]
        MEM[(Memory JSON)]
    end

    subgraph Models["Ollama"]
        QWEN[qwen3:14b]
        LLAMA[llama3:8b]
        GEMMA[gemma3:12b]
        NOMIC[nomic-embed-text]
    end

    UI -->|HTTP / SSE| API
    API --> AUTH
    API --> LG
    LG --> P
    P -->|parallel| R
    P -->|parallel| D
    R --> M
    D --> M
    M --> AN
    AN --> API
    API --> PG
    API --> CB
    API --> MEM
    R --> LLAMA
    D --> GEMMA
    D --> NOMIC
    P --> QWEN
    AN --> GEMMA
```

### LangGraph Workflow

```mermaid
stateDiagram-v2
    [*] --> Planner: User Query
    Planner --> ResearchAgent: needs web search
    Planner --> DocumentAgent: has PDFs
    Planner --> AnswerAgent: no research needed
    ResearchAgent --> Merge
    DocumentAgent --> Merge
    Merge --> AnswerAgent: has data
    Merge --> [*]: no data
    AnswerAgent --> [*]: cited answer
```

---

## Tech Stack

### Frontend
| Technology | Purpose |
|---|---|
| Next.js 15 (App Router) | React framework |
| TypeScript | Type safety |
| TailwindCSS | Utility-first styling |
| Framer Motion | Animations |
| react-markdown + remark-gfm | Markdown rendering |
| Lucide React | Icons |

### Backend
| Technology | Purpose |
|---|---|
| Python 3.12 | Runtime |
| FastAPI | REST + SSE API server |
| LangGraph | Agent orchestration (StateGraph) |
| LangChain | LLM integration |
| Pydantic v2 | Data validation |
| SQLAlchemy 2.0 (async) | ORM |
| Alembic | Database migrations |

### AI Models (Ollama)
| Model | Role |
|---|---|
| Qwen3 (14B) | Task planning & decomposition |
| Llama3 (8B) | Web research & content extraction |
| Gemma3 (12B) | Document Q&A, reranking, answer synthesis |
| nomic-embed-text (0.5B) | Text embeddings for vector search |

### Storage & Tools
| Technology | Purpose |
|---|---|
| PostgreSQL 16 | Relational data (users, conversations, tasks) |
| ChromaDB | Vector store for RAG |
| PyMuPDF | PDF text extraction |
| DuckDuckGo Search | Web search API |
| python-jose | JWT encoding/decoding |
| authlib | Google OAuth 2.0 |

---

## Project Structure

```
research-swarm/
├── backend/
│   ├── agents/
│   │   ├── planner.py           # Task planning agent (Qwen3)
│   │   ├── research_agent.py     # Web research agent (Llama3)
│   │   ├── document_agent.py     # PDF + RAG agent (Gemma3)
│   │   ├── answer_agent.py       # Answer synthesis agent
│   │   ├── memory.py             # Semantic memory (JSON + vectors)
│   │   └── graph.py              # LangGraph workflow orchestrator
│   ├── tools/
│   │   ├── registry.py           # Singleton tool registry
│   │   ├── search.py             # DuckDuckGo search
│   │   ├── pdf_loader.py         # PyMuPDF loader
│   │   ├── embedding.py          # Ollama embeddings
│   │   ├── vectorstore.py        # ChromaDB wrapper
│   │   └── tracer.py             # Span-based observability
│   ├── api/
│   │   ├── main.py               # FastAPI server (routes)
│   │   ├── auth.py               # Auth router (JWT + OAuth)
│   │   └── stream.py             # SSE stream manager
│   ├── auth/
│   │   └── dependencies.py       # FastAPI auth dependencies
│   ├── db/
│   │   ├── models.py             # SQLAlchemy models
│   │   ├── schemas.py            # Pydantic schemas
│   │   ├── session.py            # Async session management
│   │   └── alembic/              # Database migrations
│   ├── models/
│   │   └── ollama.py             # Ollama API client
│   ├── tests/
│   │   ├── test_planner.py       # 15 tests
│   │   ├── test_graph.py         # 8 tests
│   │   ├── test_tools.py         # 12 tests
│   │   ├── test_auth.py          # 12 tests
│   │   ├── test_api.py           # 10 tests
│   │   ├── test_memory.py        # 8 tests
│   │   └── conftest.py           # Fixtures & mocks
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── page.tsx              # Main dashboard
│   │   ├── layout.tsx            # Root layout
│   │   └── globals.css           # Global styles (dark/light)
│   ├── components/
│   │   ├── Chat.tsx              # Chat interface
│   │   ├── Sidebar.tsx           # Navigation sidebar
│   │   ├── ExecutionTimeline.tsx # Agent cards with latency bars
│   │   ├── AgentLogs.tsx         # Detailed execution logs
│   │   ├── StreamingText.tsx     # Typewriter streaming effect
│   │   ├── ThemeToggle.tsx       # Dark/light mode toggle
│   │   ├── PDFUploader.tsx       # Document upload panel
│   │   └── Sources.tsx           # Source citations panel
│   ├── lib/
│   │   ├── api.ts                # API client (REST + SSE)
│   │   ├── types.ts              # TypeScript interfaces
│   │   └── utils.ts              # Utility functions
│   ├── vercel.json               # Vercel deployment config
│   ├── Dockerfile
│   ├── package.json
│   └── next.config.js
├── .github/
│   └── workflows/
│       └── ci.yml                # 4-job CI pipeline
├── docker-compose.yml            # PostgreSQL + Ollama + Backend + Frontend
├── .env.example
└── README.md
```

---

## Quick Start

### Prerequisites

- [Ollama](https://ollama.ai) >= 0.3.0
- [Docker](https://docker.com) (optional)
- Python 3.12+
- Node.js 20+

### Docker (Recommended)

```bash
# Clone
git clone https://github.com/yourusername/research-swarm.git
cd research-swarm

# Pull Ollama models
ollama pull qwen3:14b llama3:8b gemma3:12b nomic-embed-text

# Start all services
docker-compose up -d

# Open the app
open http://localhost:3000
```

### Local Development

#### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your settings
uvicorn backend.api.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

---

## Usage

### Flow

```
1. Ask a question → Planner decomposes it into steps
2. Agents run in parallel (web search + PDF analysis)
3. Results merged → Answer agent synthesizes cited answer
4. View sources, agent metrics, and execution timeline
```

### Example Queries

- `What are the latest developments in quantum computing?`
- `Compare the uploaded PDF with current AI safety research`
- `Summarize the key findings from these research papers`
- `Explain the difference between RAG and fine-tuning with examples`

### Screenshots

<div align="center">
  <table>
    <tr>
      <td><img src="screenshots/dashboard.png" alt="Dashboard" width="400"/></td>
      <td><img src="screenshots/chat.png" alt="Chat" width="400"/></td>
    </tr>
    <tr>
      <td><em>Dashboard with execution timeline</em></td>
      <td><em>Chat with cited answer</em></td>
    </tr>
    <tr>
      <td><img src="screenshots/timeline.png" alt="Timeline" width="400"/></td>
      <td><img src="screenshots/light.png" alt="Light mode" width="400"/></td>
    </tr>
    <tr>
      <td><em>Agent timeline with latency bars</em></td>
      <td><em>Light mode</em></td>
    </tr>
  </table>
</div>

---

## API

### Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | — | Health check |
| `POST` | `/auth/register` | — | Register (email, password) |
| `POST` | `/auth/login` | — | Login → JWT tokens |
| `POST` | `/auth/refresh` | — | Refresh access token |
| `GET` | `/auth/me` | Required | Current user profile |
| `GET` | `/auth/google` | — | Google OAuth login |
| `GET` | `/auth/google/callback` | — | Google OAuth callback |
| `POST` | `/research` | Optional | Execute research task |
| `GET` | `/research/stream` | — | SSE stream of agent logs |
| `POST` | `/upload` | Optional | Upload PDF document |
| `GET` | `/documents` | — | List uploaded documents |
| `GET` | `/conversations` | — | List conversations |

### Research Request

```json
POST /research
{
  "query": "What are the latest advances in LLM alignment?",
  "document_ids": ["doc-uuid-1", "doc-uuid-2"],
  "conversation_id": "conv-uuid"
}
```

### Research Response

```json
{
  "task_id": "uuid",
  "conversation_id": "uuid",
  "answer": "## Key Findings\n\n1. **RLHF improvements**...\n\n## References\n[Source 1]...",
  "sources": [
    {"source_type": "web", "title": "Article Title", "url": "https://..."},
    {"source_type": "document", "title": "paper.pdf", "relevance": "Page 5"}
  ],
  "plan": [{"step_id": 1, "agent": "research_agent", "action": "search_web", "status": "completed"}],
  "logs": [{"timestamp": 1712345678, "agent": "planner", "action": "analyze_query", "status": "completed"}],
  "status": "completed",
  "execution_time": 12.34,
  "agent_metrics": {
    "planner": {"latency_ms": 3200, "model": "qwen3:14b", "status": "ok"},
    "research_agent": {"latency_ms": 5100, "model": "llama3:8b", "result_count": 5, "status": "ok"},
    "answer_agent": {"latency_ms": 4200, "model": "gemma3:12b", "source_count": 7, "status": "ok"},
    "total": {"latency_ms": 12340}
  }
}
```

### SSE Stream

```
GET /research/stream?query=What+is+RAG%3F

data: {"agent":"planner","action":"analyze_query","status":"running","details":"Analyzing: What is RAG?"}
data: {"agent":"research_agent","action":"search_web","status":"running","details":"Searching..."}
data: {"agent":"research_agent","action":"search_web","status":"completed","details":"Found 5 results"}
event: done
data: completed
```

---

## Testing

```bash
cd backend
pytest tests/ -v --cov=agents --cov=tools --cov=api --cov=db --cov=auth --cov-report=term-missing
```

**Coverage:** 60+ tests across 6 test files covering planner, graph, tools, auth, API, and memory.

### CI Pipeline (GitHub Actions)

| Job | What it does |
|---|---|
| `lint-backend` | ruff check, black check, AST syntax check |
| `test-backend` | pytest with minimum 30% coverage |
| `lint-frontend` | TypeScript type check (`tsc --noEmit`) |
| `docker-build` | Build all Docker images |

---

## Deploy

### Stack

| Service | Provider | Config |
|---|---|---|
| Frontend | Vercel | `frontend/vercel.json` |
| Backend | Railway / Render | `backend/railway.toml` / `backend/render.yaml` |
| Database | Neon (PostgreSQL) | Free tier, connection pooling |
| Ollama | GPU VM / self-hosted | `docker-compose.yml` with nvidia runtime |

### Environment Variables

```bash
# Backend
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
OLLAMA_BASE_URL=http://localhost:11434
JWT_SECRET_KEY=your-secret-key-here
CORS_ORIGINS=https://your-frontend.vercel.app
LOG_LEVEL=INFO

# Frontend
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
```

---

## Roadmap

- [x] Multi-agent orchestration with LangGraph
- [x] Web search via DuckDuckGo
- [x] PDF document processing with RAG
- [x] Source citations
- [x] Cross-encoder reranking
- [x] Semantic conversation memory
- [x] JWT authentication + Google OAuth
- [x] PostgreSQL persistence
- [x] SSE streaming
- [x] Agent metrics & observability
- [x] Execution timeline UI
- [x] Dark/light mode
- [x] Docker Compose deployment
- [x] CI/CD pipeline
- [ ] WebSocket streaming
- [ ] Multi-language support
- [ ] End-to-end Playwright tests
- [ ] PDF preview in browser
- [ ] Export answers as PDF
- [ ] Agent performance analytics dashboard

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE).

---

<div align="center">
  <p>Built with ❤️ for AI Software Engineers</p>
  <p>
    <a href="https://github.com/yourusername/research-swarm">GitHub</a> •
    <a href="https://researchswarm.vercel.app">Live Demo</a> •
    <a href="https://your-docs-site.vercel.app">Documentation</a>
  </p>
</div>
