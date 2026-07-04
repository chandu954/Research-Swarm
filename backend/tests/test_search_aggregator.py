"""Tests for the parallel search aggregator."""
from __future__ import annotations
import pytest
from backend.core.registry import get_plugin_registry, reset_plugin_registry
from backend.core.providers.search import SearchProvider
from backend.core.plugin import PluginSpec


class _FastSearchA(SearchProvider):
    spec = PluginSpec(name="fast_a", description="Fast search A", version="1.0.0")

    async def initialize(self): pass
    async def cleanup(self): pass

    async def search(self, query: str, max_results: int = 5, **kwargs):
        return [{"title": f"A: {query}", "url": "https://a.example.com", "snippet": "Result A"}]


class _FastSearchB(SearchProvider):
    spec = PluginSpec(name="fast_b", description="Fast search B", version="1.0.0")

    async def initialize(self): pass
    async def cleanup(self): pass

    async def search(self, query: str, max_results: int = 5, **kwargs):
        return [{"title": f"B: {query}", "url": "https://b.example.com", "snippet": "Result B"}]


class _DedupSearch(SearchProvider):
    spec = PluginSpec(name="dedup", description="Returns duplicate URL", version="1.0.0")

    async def initialize(self): pass
    async def cleanup(self): pass

    async def search(self, query: str, max_results: int = 5, **kwargs):
        return [{"title": "Dup", "url": "https://a.example.com", "snippet": "Same URL as A"}]


class _FailingSearch(SearchProvider):
    spec = PluginSpec(name="failing", description="Always fails", version="1.0.0")

    async def initialize(self): pass
    async def cleanup(self): pass

    async def search(self, query: str, max_results: int = 5, **kwargs):
        raise RuntimeError("Provider crashed")


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_plugin_registry()
    yield
    reset_plugin_registry()


class TestAggregateSearch:
    @pytest.mark.asyncio
    async def test_no_providers(self):
        from backend.search.aggregator import aggregate_search
        result = await aggregate_search("test")
        assert result == []

    @pytest.mark.asyncio
    async def test_single_provider(self):
        reg = get_plugin_registry()
        reg.register(_FastSearchA(), "search")
        from backend.search.aggregator import aggregate_search
        result = await aggregate_search("hello", hybrid=False)
        assert len(result) == 1
        assert result[0]["title"] == "A: hello"

    @pytest.mark.asyncio
    async def test_multi_provider(self):
        reg = get_plugin_registry()
        reg.register(_FastSearchA(), "search")
        reg.register(_FastSearchB(), "search")
        from backend.search.aggregator import aggregate_search
        result = await aggregate_search("hello", hybrid=False)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_deduplication(self):
        reg = get_plugin_registry()
        reg.register(_FastSearchA(), "search")
        reg.register(_DedupSearch(), "search")
        from backend.search.aggregator import aggregate_search
        result = await aggregate_search("hello", hybrid=False)
        assert len(result) == 1
        assert result[0]["_provider"] == "fast_a"

    @pytest.mark.asyncio
    async def test_provider_filter(self):
        reg = get_plugin_registry()
        reg.register(_FastSearchA(), "search")
        reg.register(_FastSearchB(), "search")
        from backend.search.aggregator import aggregate_search
        result = await aggregate_search("hello", provider_filter=["fast_a"], hybrid=False)
        assert len(result) == 1
        assert "_provider" in result[0]
        assert result[0]["_provider"] == "fast_a"

    @pytest.mark.asyncio
    async def test_failing_provider_ignored(self):
        reg = get_plugin_registry()
        reg.register(_FailingSearch(), "search")
        reg.register(_FastSearchB(), "search")
        from backend.search.aggregator import aggregate_search
        result = await aggregate_search("hello", hybrid=False)
        assert len(result) == 1
        assert result[0]["_provider"] == "fast_b"

    @pytest.mark.asyncio
    async def test_hybrid_mode_does_not_crash(self):
        reg = get_plugin_registry()
        reg.register(_FastSearchA(), "search")
        from backend.search.aggregator import aggregate_search
        result = await aggregate_search("hello", hybrid=True)
        assert len(result) >= 1
