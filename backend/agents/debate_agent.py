"""AI Debate Mode — multi-perspective research with balanced synthesis.

Spawns perspective agents (Optimist, Skeptic, Academic, Engineer, Security
Expert, Economist, Industry Expert) that each analyze the same research
findings from their viewpoint. A Judge agent produces a balanced conclusion.
"""
from __future__ import annotations
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger

from backend.llm.factory import get_llm_provider, resolve_model
from backend.api.stream import get_stream_manager, make_log

DEBATE_MODEL = resolve_model("answer_agent")

PERSPECTIVES = [
    {
        "id": "optimist",
        "label": "Optimist",
        "emoji": "🌟",
        "color": "#10b981",
        "role": "Forward-looking advocate",
        "instruction": "Focus on opportunities, benefits, positive outcomes, and growth potential. Highlight what could go right, the upside of each finding, and why the future looks promising. Be enthusiastic but grounded in evidence.",
    },
    {
        "id": "skeptic",
        "label": "Skeptic",
        "emoji": "🔍",
        "color": "#f59e0b",
        "role": "Critical examiner",
        "instruction": "Question assumptions, identify weaknesses, and highlight risks. Point out methodological flaws, missing evidence, overhyped claims, and potential downsides. Be constructively critical — your job is to stress-test every conclusion.",
    },
    {
        "id": "academic",
        "label": "Academic",
        "emoji": "🎓",
        "color": "#8b5cf6",
        "role": "Scholarly analyst",
        "instruction": "Evaluate through the lens of academic rigor. Assess theoretical foundations, empirical evidence quality, citation impact, methodological soundness, and alignment with established literature. Note where claims are well-supported vs speculative.",
    },
    {
        "id": "engineer",
        "label": "Engineer",
        "emoji": "⚙️",
        "color": "#3b82f6",
        "role": "Technical practitioner",
        "instruction": "Focus on practical implementation, technical feasibility, architecture decisions, performance implications, scalability, and engineering trade-offs. Assess what it takes to build, deploy, and maintain solutions based on these findings.",
    },
    {
        "id": "security",
        "label": "Security Expert",
        "emoji": "🛡️",
        "color": "#ef4444",
        "role": "Safety and security auditor",
        "instruction": "Analyze security implications, threat models, attack vectors, data privacy concerns, compliance requirements, and safety considerations. Identify vulnerabilities, risks, and necessary mitigations.",
    },
    {
        "id": "economist",
        "label": "Economist",
        "emoji": "📊",
        "color": "#06b6d4",
        "role": "Economic analyst",
        "instruction": "Assess economic impact, market dynamics, cost-benefit tradeoffs, ROI, pricing implications, resource allocation, and competitive landscape. Consider total cost of ownership, market size, and economic moats.",
    },
    {
        "id": "industry",
        "label": "Industry Expert",
        "emoji": "🏢",
        "color": "#f472b6",
        "role": "Market practitioner",
        "instruction": "Provide industry context, competitive landscape analysis, adoption trends, real-world case studies, regulatory environment, and go-to-market considerations. Ground analysis in current industry realities.",
    },
]

JUDGE_SYSTEM_PROMPT = """You are an impartial Judge synthesizing a multi-perspective research debate.

You have heard from several experts, each analyzing the same research findings from their unique viewpoint.

Your job is to produce a balanced, well-reasoned conclusion that:

1. **Summarize the key insights** from each perspective — what did each expert contribute?
2. **Identify points of agreement** — where do perspectives converge?
3. **Highlight disagreements** — where do experts diverge and why?
4. **Reconcile conflicting views** — which arguments are strongest and why? What context resolves the tension?
5. **Provide a synthesized verdict** — a clear, evidence-based conclusion that incorporates the best insights from all perspectives.

Be fair to all perspectives. Acknowledge uncertainty where it exists. The goal is a nuanced, comprehensive understanding — not oversimplification."""


@dataclass
class PerspectiveResponse:
    perspective_id: str
    label: str
    emoji: str
    color: str
    argument: str
    latency_ms: float
    status: str
    error: Optional[str] = None


@dataclass
class DebateResult:
    query: str
    perspectives: List[PerspectiveResponse] = field(default_factory=list)
    judge_verdict: Optional[str] = None
    judge_latency_ms: float = 0.0
    status: str = "completed"
    errors: List[str] = field(default_factory=list)


def _push_log(stream_id: Optional[str], agent: str, action: str, status: str, details: Optional[str] = None):
    log = make_log(agent, action, status, details)
    if stream_id:
        get_stream_manager().push_log(stream_id, log)
    logger.info(f"[{agent}] {action}: {status}")


def run_debate(
    query: str,
    web_results: List[Dict[str, Any]],
    document_chunks: List[Dict[str, Any]],
    stream_task_id: Optional[str] = None,
    perspective_ids: Optional[List[str]] = None,
) -> DebateResult:
    """Run a full AI debate — multiple perspective analyses + judge synthesis."""
    llm = get_llm_provider()
    result = DebateResult(query=query)

    selected = [p for p in PERSPECTIVES if p["id"] in (perspective_ids or [p["id"] for p in PERSPECTIVES])]
    evidence = _format_evidence(web_results, document_chunks)

    for perspective in selected:
        _push_log(stream_task_id, perspective["id"], "analyze", "running",
                  f"{perspective['emoji']} {perspective['label']} analyzing...")

        start = time.time()
        try:
            prompt = _build_perspective_prompt(query, evidence, perspective)
            raw = llm.generate(
                prompt=prompt,
                model=DEBATE_MODEL,
                system_prompt=f"You are {perspective['label']}, {perspective['role']}.",
                options={"temperature": 0.4, "num_predict": 2048},
            )
            argument = raw.strip() if raw.strip() else f"*{perspective['label']} perspective analysis unavailable.*"
            latency = round((time.time() - start) * 1000, 2)

            result.perspectives.append(PerspectiveResponse(
                perspective_id=perspective["id"],
                label=perspective["label"],
                emoji=perspective["emoji"],
                color=perspective["color"],
                argument=argument,
                latency_ms=latency,
                status="completed",
            ))
            _push_log(stream_task_id, perspective["id"], "analyze", "completed",
                      f"{perspective['emoji']} {perspective['label']} finished in {latency}ms")

        except Exception as e:
            latency = round((time.time() - start) * 1000, 2)
            logger.error(f"Debate perspective {perspective['id']} failed: {e}")
            result.perspectives.append(PerspectiveResponse(
                perspective_id=perspective["id"],
                label=perspective["label"],
                emoji=perspective["emoji"],
                color=perspective["color"],
                argument=f"*{perspective['label']} analysis encountered an error.*",
                latency_ms=latency,
                status="failed",
                error=str(e),
            ))
            result.errors.append(f"{perspective['label']}: {e}")
            _push_log(stream_task_id, perspective["id"], "analyze", "failed", str(e))

    # Judge synthesis
    _push_log(stream_task_id, "judge", "synthesize", "running", "Synthesizing balanced conclusion...")
    start = time.time()
    try:
        judge_prompt = _build_judge_prompt(query, result.perspectives)
        judge_raw = llm.generate(
            prompt=judge_prompt,
            model=DEBATE_MODEL,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            options={"temperature": 0.2, "num_predict": 3072},
        )
        result.judge_verdict = judge_raw.strip() if judge_raw.strip() else "*Judge synthesis unavailable.*"
        result.judge_latency_ms = round((time.time() - start) * 1000, 2)
        _push_log(stream_task_id, "judge", "synthesize", "completed",
                  f"Judge synthesis complete in {result.judge_latency_ms}ms")
    except Exception as e:
        result.judge_latency_ms = round((time.time() - start) * 1000, 2)
        logger.error(f"Judge synthesis failed: {e}")
        result.judge_verdict = f"*Judge synthesis encountered an error: {e}*"
        result.errors.append(f"Judge: {e}")
        _push_log(stream_task_id, "judge", "synthesize", "failed", str(e))

    return result


def _format_evidence(web_results: List[Dict[str, Any]], document_chunks: List[Dict[str, Any]]) -> str:
    parts = []
    if web_results:
        parts.append("## Web Research Sources")
        for i, r in enumerate(web_results, 1):
            title = r.get("title", f"Source {i}")
            snippet = r.get("snippet", "No content")
            url = r.get("url", "")
            parts.append(f"### [{i}] {title}")
            if url:
                parts.append(f"URL: {url}")
            parts.append(f"Content: {snippet}\n")

    if document_chunks:
        parts.append("## Document Evidence")
        for i, c in enumerate(document_chunks, len(web_results) + 1):
            content = c.get("content", c.get("text", ""))
            meta = c.get("metadata", {})
            page = meta.get("page_number", "N/A")
            source = meta.get("source_file", meta.get("doc_id", "Document"))
            parts.append(f"### [{i}] From: {source} (Page {page})")
            parts.append(f"{content[:1200]}\n")

    return "\n".join(parts) if parts else "*No research evidence provided.*"


def _build_perspective_prompt(query: str, evidence: str, perspective: dict) -> str:
    return f"""## Research Question
{query}

## Evidence Available
{evidence}

## Your Role
You are {perspective['label']}, {perspective['role']}.

{perspective['instruction']}

## Task
Analyze the evidence from your unique perspective. Provide a detailed, well-reasoned analysis that reflects your viewpoint. Be specific — reference the evidence directly. Your analysis will be combined with other perspectives and judged by a neutral synthesizer.

## Output Format
Provide your analysis in clear markdown. Include:
- Your key observations
- What stands out from your perspective
- Specific evidence that supports your view
- Any concerns or highlights

Analysis:"""


def _build_judge_prompt(query: str, perspectives: List[PerspectiveResponse]) -> str:
    parts = [f"## Research Question\n{query}\n"]

    for p in perspectives:
        parts.append(f"\n---\n## {p.emoji} {p.label} Analysis\n{p.argument}")

    parts.append("\n---\n## Your Task\nSynthesize a balanced, well-reasoned conclusion now.")
    return "\n".join(parts)
