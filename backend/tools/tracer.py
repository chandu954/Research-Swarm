"""Observability: structured tracing for agent execution.

Provides a lightweight trace collector that records agent node entries/exits,
tool calls, and LLM invocations. Outputs structured JSON logs suitable for
OpenTelemetry or LangSmith-style analysis.
"""
from __future__ import annotations
import json
import time
import uuid
from typing import Dict, Any, Optional, List
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from loguru import logger


TRACE_DIR = "./data/logs/traces"


@dataclass
class Span:
    """A span representing a unit of work in the execution trace."""

    span_id: str
    parent_id: Optional[str]
    name: str
    agent: str
    span_type: str  # "node", "tool", "llm"
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "unknown"
    input: Optional[Dict[str, Any]] = None
    output: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trace:
    """A full execution trace for a research task."""

    trace_id: str
    task_id: str
    query: str
    spans: List[Span] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_duration_ms: Optional[float] = None
    status: str = "unknown"


class Tracer:
    """Collects execution traces for observability."""

    def __init__(self, trace_dir: str = TRACE_DIR):
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self._current_trace: Optional[Trace] = None
        self._span_stack: List[Span] = []

    def start_trace(self, task_id: str, query: str) -> str:
        """Start a new trace for a research task."""
        trace_id = str(uuid.uuid4())
        self._current_trace = Trace(
            trace_id=trace_id,
            task_id=task_id,
            query=query[:200],
        )
        logger.debug(f"Trace started: {trace_id}")
        return trace_id

    def start_span(
        self,
        name: str,
        agent: str,
        span_type: str = "node",
        input_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a new span in the current trace."""
        parent_id = self._span_stack[-1].span_id if self._span_stack else None
        span = Span(
            span_id=str(uuid.uuid4()),
            parent_id=parent_id,
            name=name,
            agent=agent,
            span_type=span_type,
            start_time=time.time(),
            input=input_data,
        )
        self._span_stack.append(span)
        return span.span_id

    def end_span(
        self,
        output: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        """End the current span."""
        if not self._span_stack:
            logger.warning("No span to end")
            return

        span = self._span_stack.pop()
        span.end_time = time.time()
        span.duration_ms = round((span.end_time - span.start_time) * 1000, 2)
        span.status = "error" if error else "ok"
        span.output = output
        span.error = error

        if self._current_trace is not None:
            self._current_trace.spans.append(span)

        logger.debug(f"Span ended: {span.name} ({span.duration_ms}ms)")

    def end_trace(self, status: str = "completed") -> Optional[str]:
        """End the current trace and persist it."""
        if self._current_trace is None:
            return None

        self._current_trace.end_time = time.time()
        self._current_trace.total_duration_ms = round(
            (self._current_trace.end_time - self._current_trace.start_time) * 1000, 2
        )
        self._current_trace.status = status

        path = self.trace_dir / f"{self._current_trace.trace_id}.json"
        try:
            path.write_text(json.dumps(asdict(self._current_trace), indent=2, default=str))
            trace_id = self._current_trace.trace_id
            self._current_trace = None
            logger.info(f"Trace persisted: {trace_id}")
            return trace_id
        except Exception as e:
            logger.error(f"Failed to persist trace: {e}")
            return None

    @contextmanager
    def span(self, name: str, agent: str, span_type: str = "node"):
        """Context manager for spans."""
        span_id = self.start_span(name, agent, span_type)
        try:
            yield span_id
        except Exception as e:
            self.end_span(error=str(e))
            raise
        else:
            self.end_span()


# Global singleton
_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """Get or create the global tracer singleton."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer
