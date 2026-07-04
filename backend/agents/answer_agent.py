from __future__ import annotations
from typing import List, Dict, Any, Optional
from loguru import logger

from pydantic import BaseModel, Field

from backend.llm.factory import get_llm_provider_instance, resolve_model
from backend.tools.registry import ToolRegistry, get_registry

ANSWER_SYSTEM_PROMPT = """You are a senior research analyst. Synthesize information from web research and document chunks to answer the user's question.

Rules:
1. Produce a well-structured answer in markdown.
2. Use bullet points, comparison tables, and headings where appropriate.
3. Cite all factual claims using [Source N] notation.
4. Include a "## References" section at the end.
5. Be factual and confident when sources provide evidence. Lead with findings; only note gaps for specific claims that lack support.
6. Never fabricate citations or sources.
7. Highlight areas of agreement and disagreement between sources.
8. If sources conflict, explain the different viewpoints."""


class AnswerRequest(BaseModel):
    """Input for answer generation."""

    question: str = Field(...)
    web_results: List[Dict[str, Any]] = Field(default_factory=list)
    document_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    plan: List[Dict[str, Any]] = Field(default_factory=list)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)


class SourceRef(BaseModel):
    """A cited source."""

    source_type: str = Field(...)
    title: str = Field(...)
    url: Optional[str] = None
    relevance: str = ""
    provider: Optional[str] = None
    hybrid_score: Optional[float] = None
    source_diversity_score: Optional[float] = None


class AnswerResponse(BaseModel):
    """Generated answer with citations."""

    answer: str = Field(...)
    sources: List[SourceRef] = Field(default_factory=list)
    mode: str = Field(default="normal", description="normal | fallback | no_evidence")
    evidence_summary: Optional[Dict[str, Any]] = Field(default=None, description="What evidence was available")


class AnswerAgent:
    """Agent that generates cited answers from research results."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or get_registry()
        self.llm = get_llm_provider_instance()
        logger.info("AnswerAgent ready")

    def generate(self, request: AnswerRequest) -> AnswerResponse:
        """Generate answer using the LLM."""
        logger.info(f"Generating answer for: {request.question[:100]}...")

        sources = self._extract_sources(request)
        has_web = bool(request.web_results)
        has_docs = bool(request.document_chunks)
        has_evidence = has_web or has_docs

        evidence_summary = {
            "has_web_sources": has_web,
            "has_documents": has_docs,
            "web_count": len(request.web_results),
            "document_chunks_count": len(request.document_chunks),
            "source_count": len(sources),
        }

        if not has_evidence:
            logger.warning("No evidence available — returning no-evidence response")
            return AnswerResponse(
                answer=self._no_evidence_answer(request),
                sources=sources,
                mode="no_evidence",
                evidence_summary=evidence_summary,
            )

        prompt = self._build_prompt(request)

        try:
            raw = self.llm.generate(
                prompt=prompt,
                model=resolve_model("answer_agent"),
                system_prompt=ANSWER_SYSTEM_PROMPT,
                options={"temperature": 0.2, "num_predict": 4096},
            )
            answer = raw.strip() if raw.strip() else self._fallback(request)
            mode = "fallback" if answer != raw.strip() else "normal"
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            answer = self._fallback(request)
            mode = "fallback"

        return AnswerResponse(answer=answer, sources=sources, mode=mode, evidence_summary=evidence_summary)

    def _build_prompt(self, request: AnswerRequest) -> str:
        """Construct the full prompt with context."""
        parts = [
            f"## Question\n{request.question}\n",
        ]

        if request.conversation_history:
            parts.append("## Conversation History")
            for msg in request.conversation_history[-4:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:200]
                parts.append(f"**{role.capitalize()}**: {content}")
            parts.append("")

        if request.web_results:
            parts.append(f"## Web Research ({len(request.web_results)} sources)")
            for i, r in enumerate(request.web_results, 1):
                title = r.get("title", "Untitled")
                url = r.get("url", "")
                snippet = r.get("snippet", "No content")
                parts.append(f"### [Source {i}] {title}")
                parts.append(f"URL: {url}")
                parts.append(f"Content: {snippet}\n")

        if request.document_chunks:
            parts.append(f"## Document Evidence ({len(request.document_chunks)} chunks)")
            for i, c in enumerate(request.document_chunks, len(request.web_results) + 1):
                content = c.get("content", c.get("text", ""))
                meta = c.get("metadata", {})
                page = meta.get("page_number", "N/A")
                score = c.get("relevance_score", c.get("score", "N/A"))
                parts.append(f"### [Source {i}] Page {page} (relevance: {score})")
                parts.append(f"{content[:1500]}\n")

        parts.append("## Instructions\nGenerate a comprehensive, cited answer now.")
        return "\n".join(parts)

    def _extract_sources(self, request: AnswerRequest) -> List[SourceRef]:
        """Build source references from results."""
        sources = []
        for r in request.web_results:
            sources.append(SourceRef(
                source_type="web",
                title=r.get("title", "Untitled"),
                url=r.get("url"),
                provider=r.get("_provider") or r.get("source"),
                hybrid_score=r.get("hybrid_score"),
                source_diversity_score=r.get("source_diversity_score"),
            ))
        for c in request.document_chunks:
            meta = c.get("metadata", {})
            sources.append(SourceRef(
                source_type="document",
                title=meta.get("source_file", meta.get("doc_id", "Document")),
                relevance=f"Page {meta.get('page_number', 'N/A')} (score: {c.get('relevance_score', 'N/A')})",
            ))
        return sources

    def _no_evidence_answer(self, request: AnswerRequest) -> str:
        """Structured response when no evidence was retrieved."""
        return """# Research could not be completed

## Why?

- **Web search**: No relevant web sources were retrieved (0 results).
- **Documents**: No documents were uploaded or available.

## What happened

The AI was unable to retrieve any external evidence to answer your question. No search results or document content was available to synthesize an evidence-based response.

## Suggestions

- **Try enabling web search** — check that search backends (DuckDuckGo, Bing, or Serper) are configured correctly.
- **Upload supporting documents** — PDF files can be uploaded and queried via the document agent.
- **Rephrase your question** — a more specific or differently worded query may yield better results.
- **Retry research** — temporary search service issues may resolve on retry.

---

*Research pipeline completed with no evidence retrieved.*"""

    def _fallback(self, request: AnswerRequest) -> str:
        """Fallback answer when LLM is unavailable."""
        lines = [f"# Research Summary: {request.question}", ""]
        if request.web_results:
            lines.append("## Web Findings")
            for r in request.web_results:
                lines.append(f"- **{r.get('title', 'Source')}**: {r.get('snippet', '')[:200]}")
        if request.document_chunks:
            lines.append("\n## Document Evidence")
            for c in request.document_chunks:
                content = c.get("content", "")[:300]
                lines.append(f"- {content}...")
        lines.append("\n---\n*Answers were generated in fallback mode.*")
        lines.append("\n> **⚠️ Fallback mode:** The AI answered using only its pretrained knowledge because the primary language model was unavailable. No external evidence was synthesized.")
        return "\n".join(lines)
