"""LLM-powered planner agent for multi-agent research system.

Uses Qwen3 via Ollama to dynamically generate execution plans
instead of brittle regex matching.
"""
from __future__ import annotations
import json
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger

from pydantic import BaseModel, Field
from backend.llm.factory import get_llm_provider_instance, resolve_model
from backend.tools.registry import ToolRegistry, get_registry

PLANNER_SYSTEM_PROMPT = """You are a senior research planner. Your job is to analyze a user's research query and create an optimal execution plan.

Available agents:
- research_agent: Searches the web using DuckDuckGo. Use when the query requires current information, comparisons, or external knowledge.
- document_agent: Processes uploaded PDF documents and retrieves relevant chunks using RAG. Use when PDFs are uploaded or the query mentions documents.
- answer_agent: Synthesizes all collected information into a final answer. Always include this as the last step.

Rules:
1. NEVER answer the question yourself. Only plan the execution steps.
2. Output a JSON array of step objects with: agent, action, description.
3. Always end with an answer_agent step.
4. Be concise. Each description should be 1 sentence.
5. If the query mentions PDFs, documents, or files, include document_agent steps.
6. For general research questions, include research_agent steps.
7. For simple questions without research or documents, you can go straight to answer_agent.

Output format (JSON only, no markdown):
[
  {"agent": "research_agent", "action": "search_web", "description": "Search for latest information about..."},
  {"agent": "answer_agent", "action": "generate_answer", "description": "Synthesize findings into answer"}
]"""


class PlanStep(BaseModel):
    """A single step in the execution plan, validated from LLM output."""

    agent: str = Field(..., pattern=r"^(research_agent|document_agent|answer_agent)$")
    action: str = Field(..., min_length=1)
    description: str = Field(default="")


class PlanResult(BaseModel):
    """Result from the planner agent."""

    steps: List[Dict[str, Any]] = Field(default_factory=list)
    reasoning: str = Field(default="")


class Planner:
    """Agent that uses an LLM to dynamically plan research execution."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.llm = get_llm_provider_instance()
        self.registry = registry or get_registry()

    def create_plan(self, query: str, max_retries: int = 2) -> PlanResult:
        """Generate an execution plan using Qwen3 via Ollama, with retry logic."""
        logger.info(f"Planning for query: {query[:100]}...")

        user_prompt = f"Create an execution plan for this research query:\n\n{query}"
        last_error = None

        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.info(f"Planner retry {attempt}/{max_retries}")

            raw_output = ""
            try:
                model = resolve_model("planner")
                raw_output = self.llm.generate(
                    prompt=user_prompt,
                    model=model,
                    system_prompt=PLANNER_SYSTEM_PROMPT,
                    options={"temperature": 0.1 + (attempt * 0.1), "num_predict": 2048},
                )
            except Exception as e:
                logger.error(f"LLM call failed (attempt {attempt + 1}): {e}")
                last_error = e
                continue

            steps, reasoning = self._parse_output(raw_output)

            if len(steps) > 0:
                logger.info(f"Planner produced {len(steps)} steps: {[s['agent'] for s in steps]}")
                return PlanResult(steps=steps, reasoning=reasoning)

            last_error = ValueError("Planner returned empty steps")

        logger.error(f"Planner failed after {max_retries + 1} attempts, using fallback")
        return self._fallback_plan(query)

    def _parse_output(self, text: str) -> Tuple[List[Dict[str, Any]], str]:
        """Parse LLM output into structured steps with Pydantic validation."""
        text = text.strip()

        json_str = self._extract_json(text)
        if json_str is None:
            logger.warning("Could not extract JSON from planner output")
            return self._validate_steps([]), text[:500]

        try:
            parsed = json.loads(json_str)
            if not isinstance(parsed, list):
                logger.warning("Parsed JSON is not a list")
                return [], text[:500]

            validated = self._validate_steps_by_pydantic(parsed)
            if validated:
                return validated, text[:500]
        except json.JSONDecodeError:
            pass

        return [], text[:500]

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        """Extract a JSON array from text, repairing common issues."""
        text = text.strip()

        if text.startswith("["):
            return text

        try:
            start = text.index("[")
            end = text.rindex("]") + 1
            candidate = text[start:end]

            # Repair trailing commas before closing brackets
            candidate = re.sub(r",\s*]", "]", candidate)
            candidate = re.sub(r",\s*}", "}", candidate)

            # Remove markdown code fences if present
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
            candidate = re.sub(r"\s*```$", "", candidate)

            # Validate it parses
            json.loads(candidate)
            return candidate
        except (ValueError, json.JSONDecodeError):
            return None

    def _validate_steps(self, steps: List[dict]) -> List[Dict[str, Any]]:
        """Validate steps using Pydantic and provide fallback if needed."""
        validated = self._validate_steps_by_pydantic(steps)
        if validated:
            return validated
        return self._fallback_plan("").steps

    def _validate_steps_by_pydantic(self, steps: List[dict]) -> List[Dict[str, Any]]:
        """Validate steps using Pydantic model, discarding invalid entries."""
        validated = []
        for i, step in enumerate(steps):
            try:
                valid = PlanStep(**step)
                validated.append({
                    "step_id": i + 1,
                    "agent": valid.agent,
                    "action": valid.action,
                    "description": valid.description,
                    "status": "pending",
                })
            except Exception as e:
                logger.debug(f"Invalid step skipped: {step.get('agent')}: {e}")

        if not validated:
            return []

        if validated[-1]["agent"] != "answer_agent":
            validated.append({
                "step_id": len(validated) + 1,
                "agent": "answer_agent",
                "action": "generate_answer",
                "description": "Synthesize all findings into final answer",
                "status": "pending",
            })

        return validated

    def _fallback_plan(self, query: str) -> PlanResult:
        """Fallback plan when LLM is unavailable."""
        has_doc_keywords = any(w in query.lower() for w in ["pdf", "document", "file", "upload"])
        has_research_keywords = any(w in query.lower() for w in ["research", "compare", "analyze", "what", "how", "why", "latest"])

        steps = []

        if has_doc_keywords:
            steps.append({
                "step_id": 1, "agent": "document_agent",
                "action": "load_pdf", "description": "Process uploaded PDF documents",
                "status": "pending",
            })
            steps.append({
                "step_id": 2, "agent": "document_agent",
                "action": "retrieve_chunks", "description": "Retrieve relevant document chunks",
                "status": "pending",
            })

        if has_research_keywords:
            agent_prefix = max([s.get("step_id", 0) for s in steps], default=0)
            steps.append({
                "step_id": agent_prefix + 1, "agent": "research_agent",
                "action": "search_web", "description": "Search the web for relevant information",
                "status": "pending",
            })

        last_id = max([s.get("step_id", 0) for s in steps], default=0)
        steps.append({
            "step_id": last_id + 1, "agent": "answer_agent",
            "action": "generate_answer", "description": "Generate final answer from all sources",
            "status": "pending",
        })

        return PlanResult(steps=steps, reasoning="Fallback plan (LLM unavailable)")
