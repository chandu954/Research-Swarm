"""LangGraph StateGraph for multi-agent research orchestration.

Flow: START -> planner -> parallel(research, document) -> merge -> answer -> END
"""
from __future__ import annotations
import time
from typing import Dict, List, Any, Optional, TypedDict
from loguru import logger

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from backend.agents.planner import Planner
from backend.agents.research_agent import WebResearchAgent
from backend.agents.document_agent import DocumentAgent
from backend.agents.answer_agent import AnswerAgent, AnswerRequest
from backend.agents.merge import merge_research
from backend.llm.factory import resolve_model, apply_provider_overrides, restore_provider_overrides
from backend.llm.context import ProviderOverrides
from backend.api.stream import get_stream_manager
from backend.tools.registry import get_registry


class AgentState(TypedDict, total=False):
    """Shared state flowing through the LangGraph workflow.

    Uses total=False so all fields are optional at construction time;
    required fields are enforced at the call site in run_research.
    """

    query: str
    conversation_id: Optional[str]
    plan: List[Dict[str, Any]]
    plan_reasoning: Optional[str]
    web_results: List[Dict[str, Any]]
    document_chunks: List[Dict[str, Any]]
    answer: Optional[str]
    sources: List[Dict[str, Any]]
    errors: List[str]
    status: str
    logs: List[Dict[str, Any]]
    pdf_paths: List[str]
    execution_start: Optional[float]
    agent_metrics: Dict[str, Dict[str, Any]]
    llm_provider: Optional[str]
    planner_model: Optional[str]
    research_model: Optional[str]
    document_model: Optional[str]
    answer_model: Optional[str]
    stream_task_id: Optional[str]
    debate_mode: bool
    debate_perspectives: Optional[List[str]]
    debate_result: Optional[Dict[str, Any]]
    has_evidence: bool
    evidence_summary: Optional[Dict[str, Any]]
    answer_mode: str
    fallback_reason: Optional[str]


def _apply_state_overrides(state: AgentState) -> ProviderOverrides:
    return apply_provider_overrides(
        llm_provider=state.get("llm_provider"),
        planner_model=state.get("planner_model"),
        research_model=state.get("research_model"),
        document_model=state.get("document_model"),
        answer_model=state.get("answer_model"),
    )


def create_research_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("planner", _run_planner_node)
    workflow.add_node("research_agent", _run_research_node)
    workflow.add_node("document_agent", _run_document_node)
    workflow.add_node("merge", _run_merge_node)
    workflow.add_node("answer_agent", _run_answer_node)

    workflow.add_edge(START, "planner")

    workflow.add_conditional_edges(
        "planner",
        _route_after_planning,
        {
            "research_agent": "research_agent",
            "document_agent": "document_agent",
            "answer_agent": "answer_agent",
        },
    )

    workflow.add_conditional_edges(
        "research_agent",
        _route_after_research,
        {
            "document_agent": "document_agent",
            "merge": "merge",
        },
    )

    workflow.add_edge("document_agent", "merge")

    workflow.add_conditional_edges(
        "merge",
        _route_after_merge,
        {"answer_agent": "answer_agent", END: END},
    )

    workflow.add_edge("answer_agent", END)

    memory = MemorySaver()

    graph = workflow.compile(checkpointer=memory)
    graph.name = "ResearchSwarm Graph"

    return graph


def _add_log(state: AgentState, agent: str, action: str, status: str, details: Optional[str] = None) -> None:
    log = {
        "timestamp": time.time(),
        "agent": agent,
        "action": action,
        "status": status,
        "details": details,
    }
    state.setdefault("logs", []).append(log)
    logger.info(f"[{agent}] {action}: {status}")
    stream_id = state.get("stream_task_id")
    if stream_id:
        get_stream_manager().push_log(stream_id, log)


def _run_planner_node(state: AgentState) -> Dict[str, Any]:
    """Node: Planner agent — analyzes query and produces an execution plan."""
    backup = _apply_state_overrides(state)
    start = time.time()
    _add_log(state, "planner", "analyze_query", "running", f"Analyzing: {state['query'][:100]}...")

    registry = get_registry()
    planner = Planner(registry=registry)

    try:
        plan_result = planner.create_plan(state["query"])
        plan_data = plan_result.steps
        plan_reasoning = plan_result.reasoning

        latency_ms = round((time.time() - start) * 1000, 2)
        _add_log(state, "planner", "create_plan", "completed",
                 f"Created {len(plan_data)} steps in {latency_ms}ms. Reasoning: {plan_reasoning[:200]}...")

        restore_provider_overrides(backup)
        return {
            "plan": plan_data,
            "plan_reasoning": plan_reasoning,
            "execution_start": time.time(),
            "agent_metrics": {"planner": {"latency_ms": latency_ms, "model": resolve_model("planner"), "status": "ok"}},
        }
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000, 2)
        logger.error(f"Planner failed: {e}")
        _add_log(state, "planner", "create_plan", "failed", str(e))
        restore_provider_overrides(backup)
        return {
            "plan": [],
            "plan_reasoning": f"Error: {e}",
            "errors": state.get("errors", []) + [f"Planner error: {e}"],
            "agent_metrics": {"planner": {"latency_ms": latency_ms, "model": resolve_model("planner"), "status": "error", "error": str(e)}},
        }


def _route_after_planning(state: AgentState) -> str:
    """Route to the primary next node after planning.

    Returns a single destination key matching the edges dict.
    Because LangGraph conditional edges return a single string (not a
    list), only one destination can be returned.  To ensure both
    research_agent and document_agent run when needed, we chain them:
    if both are needed we route to research_agent first, and its
    conditional edge (see _route_after_research) fans out to
    document_agent afterwards.  This is sequential but guarantees
    both execute instead of one being skipped.
    """
    plan = state.get("plan", [])
    has_research = any(s.get("agent") == "research_agent" for s in plan)
    has_document = any(s.get("agent") == "document_agent" for s in plan) or bool(state.get("pdf_paths"))

    if has_research:
        return "research_agent"
    if has_document:
        return "document_agent"
    return "answer_agent"


def _route_after_research(state: AgentState) -> str:
    """After research_agent completes, route to document_agent if needed or merge."""
    plan = state.get("plan", [])
    has_document = any(s.get("agent") == "document_agent" for s in plan) or bool(state.get("pdf_paths"))
    return "document_agent" if has_document else "merge"


def _run_research_node(state: AgentState) -> Dict[str, Any]:
    """Node: Web research agent — searches the web and extracts content."""
    backup = _apply_state_overrides(state)
    start = time.time()
    _add_log(state, "research_agent", "search_web", "running", f"Searching for: {state['query'][:100]}...")

    registry = get_registry()
    agent = WebResearchAgent(registry=registry)

    try:
        results = agent.run(state["query"])
        latency_ms = round((time.time() - start) * 1000, 2)
        _add_log(state, "research_agent", "search_web", "completed", f"Found {len(results)} results in {latency_ms}ms")

        restore_provider_overrides(backup)
        return {
            "web_results": results,
            "agent_metrics": {
                "research_agent": {
                    "latency_ms": latency_ms,
                    "model": resolve_model("research_agent"),
                    "result_count": len(results),
                    "status": "ok",
                }
            },
        }
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000, 2)
        logger.error(f"Web research failed: {e}")
        _add_log(state, "research_agent", "search_web", "failed", str(e))
        restore_provider_overrides(backup)
        return {
            "web_results": [],
            "errors": state.get("errors", []) + [f"Research error: {e}"],
            "agent_metrics": {"research_agent": {"latency_ms": latency_ms, "model": resolve_model("research_agent"), "status": "error", "error": str(e)}},
        }


def _run_document_node(state: AgentState) -> Dict[str, Any]:
    """Node: Document agent — processes PDFs and retrieves relevant chunks."""
    backup = _apply_state_overrides(state)
    start = time.time()
    pdf_paths = state.get("pdf_paths", [])

    if not pdf_paths:
        _add_log(state, "document_agent", "process_documents", "completed", "No PDFs to process")
        return {"document_chunks": [], "agent_metrics": {"document_agent": {"latency_ms": 0, "model": resolve_model("document_agent"), "chunks_retrieved": 0, "status": "skipped"}}}

    _add_log(state, "document_agent", "process_documents", "running", f"Processing {len(pdf_paths)} PDF(s)")

    registry = get_registry()
    agent = DocumentAgent(registry=registry)

    try:
        for pdf_path in pdf_paths:
            _add_log(state, "document_agent", "parse_pdf", "running", f"Parsing {pdf_path}")
            agent.ingest_pdf(pdf_path)
            _add_log(state, "document_agent", "parse_pdf", "completed", f"Processed {pdf_path}")

        _add_log(state, "document_agent", "retrieve_chunks", "running", "Querying vector store")
        chunks = agent.retrieve(state["query"])
        latency_ms = round((time.time() - start) * 1000, 2)
        _add_log(state, "document_agent", "retrieve_chunks", "completed", f"Retrieved {len(chunks)} chunks in {latency_ms}ms")

        restore_provider_overrides(backup)
        return {
            "document_chunks": chunks,
            "agent_metrics": {
                "document_agent": {
                    "latency_ms": latency_ms,
                    "model": resolve_model("document_agent"),
                    "chunks_retrieved": len(chunks),
                    "pdfs_processed": len(pdf_paths),
                    "status": "ok",
                }
            },
        }
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000, 2)
        logger.error(f"Document processing failed: {e}")
        _add_log(state, "document_agent", "process_documents", "failed", str(e))
        restore_provider_overrides(backup)
        return {
            "document_chunks": [],
            "errors": state.get("errors", []) + [f"Document error: {e}"],
            "agent_metrics": {"document_agent": {"latency_ms": latency_ms, "model": resolve_model("document_agent"), "status": "error", "error": str(e)}},
        }


def _run_merge_node(state: AgentState) -> Dict[str, Any]:
    """Node: Merge — combines web and document evidence, deduplicates."""
    merged = merge_research(
        web_results=state.get("web_results", []),
        document_chunks=state.get("document_chunks", []),
    )
    _add_log(state, "merge", "synchronize", "completed",
             f"Web: {merged['source_count']} results, Docs: {merged['document_count']} chunks, "
             f"merged: {len(merged['merged_evidence'])} items, has_evidence={merged['has_evidence']}")
    return {
        "has_evidence": merged["has_evidence"],
        "evidence_summary": {
            "web_count": merged["source_count"],
            "document_chunks_count": merged["document_count"],
            "merged_count": len(merged["merged_evidence"]),
            "has_web_sources": merged["source_count"] > 0,
            "has_documents": merged["document_count"] > 0,
        },
    }


def _route_after_merge(state: AgentState) -> str:
    """Route to answer agent or end if no data."""
    has_any_data = bool(state.get("web_results")) or bool(state.get("document_chunks")) or bool(state.get("plan"))
    return "answer_agent" if has_any_data else END


def _run_answer_node(state: AgentState) -> Dict[str, Any]:
    """Node: Answer agent — synthesizes final answer from all sources.

    If debate_mode is enabled, also runs multi-perspective debate after the
    standard answer is generated.
    """
    backup = _apply_state_overrides(state)
    start = time.time()
    _add_log(state, "answer_agent", "generate_answer", "running", "Synthesizing answer")

    registry = get_registry()
    agent = AnswerAgent(registry=registry)
    extra_updates: Dict[str, Any] = {}

    try:
        request = AnswerRequest(
            question=state["query"],
            web_results=state.get("web_results", []),
            document_chunks=state.get("document_chunks", []),
            plan=state.get("plan", []),
        )

        response = agent.generate(request)
        latency_ms = round((time.time() - start) * 1000, 2)
        total_time = time.time() - state.get("execution_start", time.time())

        _add_log(state, "answer_agent", "generate_answer", "completed",
                 f"Generated answer in {latency_ms}ms with {len(response.sources)} sources")

        # Debate mode: run multi-perspective analysis after answer generation
        if state.get("debate_mode"):
            _add_log(state, "answer_agent", "start_debate", "running",
                     "Launching multi-perspective debate...")
            try:
                from backend.agents.debate_agent import run_debate
                debate_result = run_debate(
                    query=state["query"],
                    web_results=state.get("web_results", []),
                    document_chunks=state.get("document_chunks", []),
                    stream_task_id=state.get("stream_task_id"),
                    perspective_ids=state.get("debate_perspectives"),
                )
                extra_updates["debate_result"] = {
                    "query": debate_result.query,
                    "perspectives": [
                        {
                            "perspective_id": p.perspective_id,
                            "label": p.label,
                            "emoji": p.emoji,
                            "color": p.color,
                            "argument": p.argument,
                            "latency_ms": p.latency_ms,
                            "status": p.status,
                        }
                        for p in debate_result.perspectives
                    ],
                    "judge_verdict": debate_result.judge_verdict,
                    "judge_latency_ms": debate_result.judge_latency_ms,
                    "status": debate_result.status,
                    "errors": debate_result.errors,
                }
                _add_log(state, "answer_agent", "debate_complete", "completed",
                         f"Debate concluded with {len(debate_result.perspectives)} perspectives")
            except Exception as e:
                logger.error(f"Debate mode failed: {e}")
                _add_log(state, "answer_agent", "debate_error", "failed", str(e))
                extra_updates["debate_result"] = {
                    "status": "failed",
                    "errors": [str(e)],
                    "perspectives": [],
                    "judge_verdict": None,
                }

        restore_provider_overrides(backup)
        return {
            "answer": response.answer,
            "sources": [s.model_dump() for s in response.sources],
            "status": "completed",
            "answer_mode": response.mode,
            "evidence_summary": response.evidence_summary or state.get("evidence_summary"),
            "has_evidence": bool(response.sources),
            "agent_metrics": {
                "answer_agent": {
                    "latency_ms": latency_ms,
                    "model": resolve_model("answer_agent"),
                    "source_count": len(response.sources),
                    "mode": response.mode,
                    "status": "ok",
                },
                "total": {"latency_ms": round(total_time * 1000, 2)},
            },
            **extra_updates,
        }
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000, 2)
        logger.error(f"Answer generation failed: {e}")
        _add_log(state, "answer_agent", "generate_answer", "failed", str(e))
        restore_provider_overrides(backup)
        return {
            "answer": f"**Error generating answer:** {e}",
            "status": "failed",
            "errors": state.get("errors", []) + [f"Answer error: {e}"],
            "agent_metrics": {"answer_agent": {"latency_ms": latency_ms, "model": resolve_model("answer_agent"), "status": "error", "error": str(e)}},
            **extra_updates,
        }


# Graph singleton
_graph: Optional[StateGraph] = None


def get_graph() -> StateGraph:
    global _graph
    if _graph is None:
        _graph = create_research_graph()
    return _graph

def reset_graph() -> None:
    global _graph
    _graph = None
