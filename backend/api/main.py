"""FastAPI server for ResearchSwarm AI multi-agent system."""
from __future__ import annotations
import os, time, uuid, asyncio
from typing import Optional
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import Depends, FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from backend.agents.graph import create_research_graph
from backend.agents.entity_extractor import extract_entities
from backend.agents.memory import get_memory
from backend.api.stream import get_stream_manager, make_log, event_stream
from backend.api.auth import router as auth_router
from backend.tools.registry import get_registry
from backend.db.session import init_db, close_db
from backend.auth.dependencies import get_current_user, get_optional_user
from backend.db.models import User
from backend.db.schemas import ResearchRequest, ResearchResponse

UPLOAD_DIR = "./data/uploads"
for d in [UPLOAD_DIR, "./data/chroma_db", "./data/memory", "./data/logs"]:
    os.makedirs(d, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ResearchSwarm AI starting up")
    app.state.start_time = time.time()
    await init_db()
    app.state.graph = create_research_graph()
    app.state.memory = get_memory()
    app.state.registry = get_registry()
    app.state.stream_manager = get_stream_manager()
    try:
        tools = app.state.registry.list_tools()
        logger.info(f"Tools registered: {[t.name for t in tools]}")
    except Exception as e:
        logger.warning(f"Tool listing failed: {e}")
    yield
    await close_db()
    logger.info("ResearchSwarm AI shutting down")


def _ensure_app_state() -> None:
    """Lazy initialize app state for environments without lifespan startup."""
    if not hasattr(app.state, "start_time"):
        app.state.start_time = time.time()
    if not hasattr(app.state, "graph"):
        app.state.graph = create_research_graph()
    if not hasattr(app.state, "memory"):
        app.state.memory = get_memory()
    if not hasattr(app.state, "registry"):
        app.state.registry = get_registry()
    if not hasattr(app.state, "stream_manager"):
        app.state.stream_manager = get_stream_manager()


app = FastAPI(
    title="ResearchSwarm AI",
    description="Multi-Agent Research System powered by LangGraph + Ollama",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health")
async def health_check():
    _ensure_app_state()
    registry = app.state.registry
    return {
        "status": "healthy",
        "version": "2.0.0",
        "uptime": time.time() - app.state.start_time,
        "tools_available": len(registry.list_tools()),
    }


@app.post("/research", response_model=ResearchResponse)
async def run_research(
    request: ResearchRequest,
    current_user: User = Depends(get_optional_user),
):
    """Execute a multi-agent research task."""
    _ensure_app_state()
    task_id = request.stream_task_id or str(uuid.uuid4())
    conversation_id = request.conversation_id or app.state.memory.create_conversation(
        metadata={"query": request.query[:200], "user_id": current_user.id if current_user else "anonymous"}
    )
    start_time = time.time()
    logger.info(f"[{task_id}] Research by {current_user.id if current_user else 'anon'}: {request.query[:100]}...")

    app.state.memory.add_turn(conversation_id, "user", request.query)
    pdf_paths = _resolve_pdf_paths(request.document_ids)
    graph = app.state.graph
    app.state.stream_manager.get_or_create_stream(task_id)

    try:
        initial_state = {
            "query": request.query,
            "conversation_id": conversation_id,
            "plan": [],
            "plan_reasoning": None,
            "web_results": [],
            "document_chunks": [],
            "answer": None,
            "sources": [],
            "errors": [],
            "status": "running",
            "logs": [],
            "pdf_paths": pdf_paths,
            "execution_start": start_time,
            "agent_metrics": {},
            "stream_task_id": task_id,
            "llm_provider": request.llm_provider,
            "planner_model": request.planner_model,
            "research_model": request.research_model,
            "document_model": request.document_model,
            "answer_model": request.answer_model,
            "openrouter_key": request.openrouter_key,
        }
        result = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": task_id}})
        execution_time = time.time() - start_time
        app.state.memory.add_turn(conversation_id, "assistant", result.get("answer", "")[:500], metadata={"task_id": task_id})
        app.state.stream_manager.close_stream(task_id)

        return ResearchResponse(
            task_id=task_id,
            conversation_id=conversation_id,
            query=request.query,
            answer=result.get("answer"),
            sources=result.get("sources", []),
            plan=result.get("plan", []),
            logs=result.get("logs", []),
            status=result.get("status", "completed"),
            errors=result.get("errors", []),
            execution_time=execution_time,
            plan_reasoning=result.get("plan_reasoning"),
            agent_metrics=result.get("agent_metrics", {}),
        )
    except Exception as e:
        logger.error(f"[{task_id}] Research failed: {e}")
        app.state.stream_manager.close_stream(task_id)
        return ResearchResponse(
            task_id=task_id,
            conversation_id=conversation_id,
            query=request.query,
            status="failed",
            errors=[str(e)],
            execution_time=time.time() - start_time,
        )


@app.get("/research/stream/{task_id}")
async def subscribe_research_stream(task_id: str):
    """Subscribe to live agent logs for an in-progress research task."""
    _ensure_app_state()
    stream_mgr = app.state.stream_manager
    log_queue = stream_mgr.get_or_create_stream(task_id)
    return StreamingResponse(
        event_stream(task_id, log_queue),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.get("/research/stream")
async def research_stream(
    query: str = Query(..., min_length=1),
    conversation_id: Optional[str] = Query(None),
    document_ids: str = Query(default=""),
):
    """Stream research execution logs via SSE."""
    _ensure_app_state()
    task_id = str(uuid.uuid4())
    conv_id = conversation_id or app.state.memory.create_conversation(
        metadata={"query": query[:200], "user_id": "anonymous"}
    )
    doc_ids = [d.strip() for d in document_ids.split(",") if d.strip()]
    pdf_paths = _resolve_pdf_paths(doc_ids)
    stream_mgr = app.state.stream_manager
    log_queue = stream_mgr.create_stream(task_id)

    stream_mgr.push_log(task_id, make_log("planner", "analyze_query", "running", query[:100]))

    async def run_and_stream():
        try:
            initial_state = {
                "query": query,
                "conversation_id": conv_id,
                "plan": [],
                "plan_reasoning": None,
                "web_results": [],
                "document_chunks": [],
                "answer": None,
                "sources": [],
                "errors": [],
                "status": "running",
                "logs": [],
                "pdf_paths": pdf_paths,
                "execution_start": time.time(),
                "agent_metrics": {},
                "llm_provider": None,
                "planner_model": None,
                "research_model": None,
                "document_model": None,
                "answer_model": None,
                "openrouter_key": None,
            }
            graph = app.state.graph
            await graph.ainvoke(initial_state, config={"configurable": {"thread_id": task_id}})
            stream_mgr.push_log(task_id, make_log("system", "complete", "completed", "Execution finished"))
        except Exception as e:
            stream_mgr.push_log(task_id, make_log("system", "error", "failed", str(e)))
        finally:
            stream_mgr.close_stream(task_id)

    asyncio.ensure_future(run_and_stream())
    return StreamingResponse(
        event_stream(task_id, log_queue),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


class ExtractEntitiesRequest(BaseModel):
    text: str = Field(..., min_length=20, description="Research text to extract entities from")
    llm_provider: Optional[str] = Field(None, description="Provider override (ollama, openrouter)")
    model: Optional[str] = Field(None, description="Model override for extraction")


@app.post("/research/extract-entities")
async def research_extract_entities(request: ExtractEntitiesRequest):
    """Extract entities and relationships from research text for knowledge graph enrichment."""
    _ensure_app_state()
    result = await extract_entities(
        text=request.text,
        llm_provider=request.llm_provider,
        model=request.model,
    )
    return result


@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_optional_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files supported")
    file_id = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, file_id)
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(f"Uploaded: {file.filename} ({len(content)} bytes)")
        return {"document_id": file_id, "filename": file.filename, "size": len(content), "status": "uploaded"}
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents():
    if not os.path.exists(UPLOAD_DIR):
        return {"documents": []}
    docs = []
    for fname in os.listdir(UPLOAD_DIR):
        if not fname.lower().endswith(".pdf"):
            continue
        stat = os.stat(os.path.join(UPLOAD_DIR, fname))
        docs.append({"document_id": fname, "filename": "_".join(fname.split("_")[1:]), "size": stat.st_size, "upload_date": stat.st_mtime})
    return {"documents": docs}


@app.get("/conversations")
async def list_conversations():
    _ensure_app_state()
    return {"conversations": app.state.memory.list_conversations()}


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    _ensure_app_state()
    conv = app.state.memory.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation_id": conv.conversation_id, "turn_count": len(conv.turns), "created_at": conv.created_at, "updated_at": conv.updated_at}


@app.get("/models")
async def list_models():
    """List available models from the active provider."""
    import json, urllib.request

    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return {"provider": "openrouter", "models": [], "error": "No API key configured"}
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            models = sorted(set(m["id"] for m in data.get("data", [])))
            return {"provider": "openrouter", "models": models, "count": len(models)}
        except Exception as e:
            logger.error(f"Failed to fetch OpenRouter models: {e}")
            return {"provider": "openrouter", "models": [], "error": str(e)}
    else:
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            models = sorted(set(m["name"] for m in data.get("models", [])))
            return {"provider": "ollama", "models": models, "count": len(models)}
        except Exception as e:
            logger.error(f"Failed to fetch Ollama models: {e}")
            return {"provider": "ollama", "models": [], "error": str(e)}


def _resolve_pdf_paths(document_ids: list[str]) -> list[str]:
    paths = []
    for doc_id in document_ids:
        path = os.path.join(UPLOAD_DIR, doc_id)
        if os.path.exists(path):
            paths.append(path)
        else:
            logger.warning(f"Document not found: {doc_id}")
    return paths


@app.exception_handler(Exception)
async def global_handler(request, exc):
    logger.error(f"Unhandled: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
