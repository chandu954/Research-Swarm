"""Tool registry for agent dependency injection."""
from __future__ import annotations
import time
from typing import Dict, Any, Callable, Optional, List
from enum import Enum
from pydantic import BaseModel, Field
from loguru import logger


class ToolCategory(str, Enum):
    SEARCH = "search"
    DOCUMENT = "document"
    EMBEDDING = "embedding"
    VECTOR_STORE = "vector_store"
    BROWSER = "browser"
    CODE = "code"
    CALCULATOR = "calculator"


class ToolSpec(BaseModel):
    """Specification for a registered tool."""

    name: str = Field(..., description="Unique tool name")
    description: str = Field(..., description="What the tool does")
    category: ToolCategory = Field(..., description="Tool category")
    version: str = Field(default="1.0.0")
    requires_ollama: bool = Field(default=False)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """Record of a tool execution."""

    tool_name: str = Field(...)
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None


class ToolRegistry:
    """Central registry for all tools available to agents.

    Agents request tools by name instead of importing implementations
    directly. This enables swapping implementations, adding middleware,
    and collecting execution traces.
    """

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._specs: Dict[str, ToolSpec] = {}
        self._calls: List[ToolCall] = []

    def register(
        self,
        name: str,
        func: Callable,
        spec: ToolSpec,
    ) -> None:
        """Register a tool implementation."""
        self._tools[name] = func
        self._specs[name] = spec
        logger.info(f"Registered tool: {name} ({spec.category.value})")

    def get(self, name: str) -> Callable:
        """Get a tool by name."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not registered")
        return self._tools[name]

    def get_spec(self, name: str) -> ToolSpec:
        """Get tool specification."""
        if name not in self._specs:
            raise KeyError(f"Tool '{name}' not registered")
        return self._specs[name]

    def list_tools(self, category: Optional[ToolCategory] = None) -> List[ToolSpec]:
        """List registered tools, optionally filtered by category."""
        specs = list(self._specs.values())
        if category:
            specs = [s for s in specs if s.category == category]
        return specs

    def execute(
        self,
        name: str,
        **kwargs: Any,
    ) -> Any:
        """Execute a tool and record the call."""
        tool = self.get(name)
        spec = self.get_spec(name)

        call = ToolCall(tool_name=name, input=kwargs)
        logger.debug(f"Executing tool: {name}")

        try:
            result = tool(**kwargs)
            call.output = result
            call.end_time = time.time()
            call.duration_ms = round((call.end_time - call.start_time) * 1000, 2)
            logger.debug(f"Tool {name} completed in {call.duration_ms}ms")
            self._calls.append(call)
            return result
        except Exception as e:
            call.error = str(e)
            call.end_time = time.time()
            call.duration_ms = round((call.end_time - call.start_time) * 1000, 2)
            self._calls.append(call)
            logger.error(f"Tool {name} failed after {call.duration_ms}ms: {e}")
            raise

    def clear_calls(self) -> None:
        """Clear execution call history."""
        self._calls.clear()

    def get_call_history(self) -> List[ToolCall]:
        """Get all tool call records."""
        return self._calls.copy()


def _is_async(func: Callable) -> bool:
    """Check if a function is async."""
    import asyncio
    return asyncio.iscoroutinefunction(func)


# Global singleton
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get or create the global tool registry singleton."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (useful for testing)."""
    global _registry
    _registry = None
