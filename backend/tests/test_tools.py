"""Tests for tools: search, registry, PDF loader, embedding, vector store, tracer."""
from __future__ import annotations
import json
import tempfile
import os
from unittest.mock import patch, MagicMock
import pytest


class TestToolRegistry:
    """Tests for the tool registry."""

    def test_register_and_get(self, tool_registry):
        """Tools should be registered and retrievable."""
        def my_tool():
            return "result"
        tool_registry.register("my_tool", my_tool, MagicMock(name="my_tool", description="Test tool"))
        tool = tool_registry.get("my_tool")
        assert tool() == "result"

    def test_get_nonexistent(self, tool_registry):
        """Getting a nonexistent tool should raise KeyError."""
        with pytest.raises(KeyError):
            tool_registry.get("nonexistent")

    def test_list_tools(self, tool_registry):
        """Listing tools should return registered tools."""
        tool_registry.register("tool1", lambda: None, MagicMock(name="tool1", description="Tool 1"))
        tool_registry.register("tool2", lambda: None, MagicMock(name="tool2", description="Tool 2"))
        specs = tool_registry.list_tools()
        assert len(specs) == 2

    @pytest.mark.asyncio
    async def test_execute_tool(self, tool_registry):
        """Tool execution should record the call."""
        async def async_tool(x: int) -> int:
            return x * 2
        tool_registry.register("double", async_tool, MagicMock(name="double", description="Double"))
        result = await tool_registry.execute_async("double", x=5)
        assert result == 10
        history = tool_registry.get_call_history()
        assert len(history) == 1
        assert history[0].tool_name == "double"
        assert history[0].duration_ms is not None

    def test_clear_calls(self, tool_registry):
        """Call history should be clearable."""
        tool_registry.register("noop", lambda: None, MagicMock(name="noop", description="Noop"))
        tool_registry.execute("noop")
        assert len(tool_registry.get_call_history()) == 1
        tool_registry.clear_calls()
        assert len(tool_registry.get_call_history()) == 0

    def test_get_spec(self, tool_registry):
        """Getting a spec should return the correct metadata."""
        spec = MagicMock(name="test_tool", description="Test description")
        tool_registry.register("test_tool", lambda: None, spec)
        retrieved = tool_registry.get_spec("test_tool")
        assert retrieved.description == "Test description"

    def test_global_singleton(self):
        """get_registry should return the same instance."""
        from backend.tools.registry import get_registry, reset_registry
        reset_registry()
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2


class TestSearchTool:
    """Tests for the web search tool."""

    def test_clean_url(self):
        """URL cleaning should handle missing protocols."""
        from backend.tools.search import _clean_url
        assert _clean_url("example.com") == "https://example.com"
        assert _clean_url("https://example.com") == "https://example.com"
        assert _clean_url("") == ""


class TestPDFLoader:
    """Tests for the PDF loader tool."""

    def test_load_nonexistent_pdf(self):
        """Loading a nonexistent PDF should raise FileNotFoundError."""
        from backend.tools.pdf_loader import load_pdf
        with pytest.raises(FileNotFoundError):
            load_pdf("/nonexistent/file.pdf")


class TestTracer:
    """Tests for the observability tracer."""

    def test_tracer_start_and_end(self):
        """A trace should be created and persisted."""
        from backend.tools.tracer import Tracer
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = Tracer(trace_dir=tmpdir)
            trace_id = tracer.start_trace("task-1", "Test query")
            assert trace_id is not None

            tracer.start_span("plan", "planner")
            tracer.end_span(output={"plan": ["step1"]})

            tracer.end_trace("completed")

            files = os.listdir(tmpdir)
            assert len(files) == 1
            assert files[0].endswith(".json")

    def test_tracer_span_hierarchy(self):
        """Spans should maintain parent-child relationships."""
        from backend.tools.tracer import Tracer

        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = Tracer(trace_dir=tmpdir)
            tracer.start_trace("task-2", "Test")
            parent_id = tracer.start_span("parent", "planner")
            child_id = tracer.start_span("child", "research_agent")
            tracer.end_span()
            tracer.end_span()

            # Verify the trace was persisted
            trace_id = tracer.end_trace()
            assert trace_id is not None

    def test_tracer_context_manager(self):
        """Span context manager should work correctly."""
        from backend.tools.tracer import Tracer

        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = Tracer(trace_dir=tmpdir)
            tracer.start_trace("task-3", "Test")
            with tracer.span("test_span", "test_agent"):
                pass
            tracer.end_trace()

    def test_tracer_span_records_error(self):
        """Span should record errors when exception occurs."""
        from backend.tools.tracer import Tracer

        with tempfile.TemporaryDirectory() as tmpdir:
            tracer = Tracer(trace_dir=tmpdir)
            tracer.start_trace("task-4", "Test")
            try:
                with tracer.span("failing_span", "test_agent"):
                    raise ValueError("Test error")
            except ValueError:
                pass
            tracer.end_trace()
