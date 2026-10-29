"""Tests for tool registry branches.

Split from backend/tests/test_realtime_stream_infra.py.
"""

from __future__ import annotations

import asyncio

import pytest
from backend.tools.registry import ToolCategory, ToolRegistry, ToolSpec, _is_async


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


class TestToolRegistryBranches:
    def _spec(self, name="tool", category=ToolCategory.SEARCH):
        return ToolSpec(name=name, description="desc", category=category)

    def test_register_get_and_list(self):
        registry = ToolRegistry()
        registry.register("tool", lambda: "ok", self._spec())
        registry.register(
            "calc", lambda: 1, self._spec("calc", ToolCategory.CALCULATOR)
        )

        assert registry.get("tool")() == "ok"
        assert registry.get_spec("tool").description == "desc"
        assert len(registry.list_tools()) == 2
        assert [spec.name for spec in registry.list_tools(ToolCategory.CALCULATOR)] == [
            "calc"
        ]
        with pytest.raises(KeyError):
            registry.get("missing")
        with pytest.raises(KeyError):
            registry.get_spec("missing")

    def test_execute_sync_success_and_failure(self):
        registry = ToolRegistry()
        registry.register("ok", lambda value: value * 2, self._spec("ok"))
        registry.register(
            "fail",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            self._spec("fail"),
        )

        assert registry.execute("ok", value=2) == 4
        with pytest.raises(RuntimeError, match="boom"):
            registry.execute("fail")

        history = registry.get_call_history()
        assert len(history) == 2
        assert history[0].duration_ms is not None
        assert history[1].error == "boom"
        registry.clear_calls()
        assert registry.get_call_history() == []

    def test_execute_async_tool_from_sync_context(self):
        registry = ToolRegistry()

        async def async_tool(value):
            return value + 1

        registry.register("async", async_tool, self._spec("async"))
        assert registry.execute("async", value=1) == 2
        assert _is_async(async_tool) is True
        assert _is_async(lambda: None) is False

    def test_execute_async_success_and_failure_for_both_tool_types(self):
        registry = ToolRegistry()

        async def async_tool(value):
            return value

        async def async_fail():
            raise RuntimeError("async boom")

        registry.register("async", async_tool, self._spec("async"))
        registry.register("async_fail", async_fail, self._spec("async_fail"))
        registry.register("sync", lambda value: value, self._spec("sync"))
        registry.register(
            "sync_fail",
            lambda: (_ for _ in ()).throw(RuntimeError("sync boom")),
            self._spec("sync_fail"),
        )

        async def scenario():
            assert await registry.execute_async("async", value=3) == 3
            assert await registry.execute_async("sync", value=4) == 4
            with pytest.raises(RuntimeError, match="async boom"):
                await registry.execute_async("async_fail")
            with pytest.raises(RuntimeError, match="sync boom"):
                await registry.execute_async("sync_fail")

        asyncio_run(scenario())
        assert len(registry.get_call_history()) == 4

    def test_global_registry_singleton_and_reset(self):
        from backend.tools.registry import get_registry, reset_registry

        reset_registry()
        first = get_registry()
        assert first is get_registry()
        reset_registry()
        assert get_registry() is not first
        reset_registry()
