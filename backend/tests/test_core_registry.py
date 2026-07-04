"""Tests for the unified PluginRegistry (core.registry)."""
from __future__ import annotations
import pytest
from backend.core.plugin import PluginInterface, PluginSpec
from backend.core.registry import get_plugin_registry, reset_plugin_registry
from backend.core.providers.llm import LLMProvider
from backend.core.providers.search import SearchProvider
from backend.core.providers.embedding import EmbeddingProvider
from backend.core.providers.vector_db import VectorDBProvider
from backend.core.providers.storage import StorageProvider
from backend.core.providers.memory import MemoryProvider


def _make_llm(name: str) -> LLMProvider:
    class _MockLLM(LLMProvider):
        spec = PluginSpec(name=name, description=f"Mock {name}", version="1.0.0")

        async def initialize(self): pass
        async def cleanup(self): pass
        def generate(self, prompt, model, **kw): return f"mock: {prompt[:50]}"
        def generate_stream(self, prompt, model, **kw): yield "mock"
        def create_embedding(self, model, text): return [0.1] * 4
    return _MockLLM()


def _make_search(name: str) -> SearchProvider:
    class _MockSearch(SearchProvider):
        spec = PluginSpec(name=name, description=f"Mock {name}", version="1.0.0")
        async def initialize(self): pass
        async def cleanup(self): pass
        async def search(self, query, max_results=5, **kw):
            return [{"title": f"Mock result for {query}", "url": "https://mock.com"}]
    return _MockSearch()


class MockEmbeddingProvider(EmbeddingProvider):
    spec = PluginSpec(name="mock_embed", description="Mock Embedding", version="1.0.0")

    async def initialize(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    def embed(self, texts: list[str], model: str | None = None, **kwargs) -> list[list[float]] | None:
        return [[0.1] * 4 for _ in texts]

    def embed_query(self, text: str, model: str | None = None) -> list[float] | None:
        return [0.1] * 4


class MockVectorDBProvider(VectorDBProvider):
    spec = PluginSpec(name="mock_vdb", description="Mock Vector DB", version="1.0.0")

    async def initialize(self) -> None:
        self._data: dict[str, dict] = {}

    async def cleanup(self) -> None:
        self._data.clear()

    async def store(self, ids: list[str], documents: list[str], embeddings: list[list[float]] | None = None, metadatas: list[dict] | None = None) -> None:
        for i, doc_id in enumerate(ids):
            self._data[doc_id] = {"content": documents[i], "metadata": metadatas[i] if metadatas else {}}

    async def query(self, query_embedding: list[float], top_k: int = 10, filter: dict | None = None) -> list[dict]:
        return [{"content": v["content"], "metadata": v["metadata"], "score": 0.9} for v in list(self._data.values())[:top_k]]

    async def delete(self, ids: list[str]) -> None:
        for doc_id in ids:
            self._data.pop(doc_id, None)


class MockStorageProvider(StorageProvider):
    spec = PluginSpec(name="mock_storage", description="Mock Storage", version="1.0.0")

    async def initialize(self) -> None:
        self._data: dict[str, bytes] = {}

    async def cleanup(self) -> None:
        self._data.clear()

    async def save(self, path: str, content: bytes) -> str:
        self._data[path] = content
        return path

    async def load(self, path: str) -> bytes | None:
        return self._data.get(path)

    async def delete(self, path: str) -> bool:
        return self._data.pop(path, None) is not None

    async def exists(self, path: str) -> bool:
        return path in self._data


class MockMemoryProvider(MemoryProvider):
    spec = PluginSpec(name="mock_memory", description="Mock Memory", version="1.0.0")

    async def initialize(self) -> None:
        self._data: dict[str, list[dict]] = {}

    async def cleanup(self) -> None:
        self._data.clear()

    async def store(self, key: str, value: any, tags: list[str] | None = None) -> None:
        self._data.setdefault(key, []).append({"content": str(value), "tags": tags or []})

    async def retrieve(self, key: str) -> any:
        return self._data.get(key)

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        return self._data.get(query, [])[:limit]

    async def delete(self, key: str) -> bool:
        return self._data.pop(key, None) is not None


class TestPluginRegistryCore:
    def setup_method(self):
        reset_plugin_registry()

    def test_register_and_get_llm(self):
        reg = get_plugin_registry()
        p = _make_llm("mock_llm")
        reg.register(p, "llm")
        assert reg.get_llm() is p
        assert reg.get_llm("mock_llm") is p

    def test_register_default_fallback(self):
        reg = get_plugin_registry()
        p1 = _make_llm("mock_llm_1")
        p2 = _make_llm("mock_llm_2")
        reg.register(p1, "llm", default=True)
        reg.register(p2, "llm")
        assert reg.get_llm() is p1

    def test_register_default_overrides(self):
        reg = get_plugin_registry()
        p1 = _make_llm("mock_llm_1")
        p2 = _make_llm("mock_llm_2")
        reg.register(p1, "llm")
        reg.register(p2, "llm", default=True)
        assert reg.get_llm() is p2

    def test_get_nonexistent_type(self):
        reg = get_plugin_registry()
        assert reg.get_llm("nope") is None

    def test_get_empty_registry(self):
        reg = get_plugin_registry()
        assert reg.get_llm() is None

    def test_list_plugins(self):
        reg = get_plugin_registry()
        reg.register(_make_llm("mock_llm"), "llm")
        reg.register(_make_search("mock_search"), "search")
        specs = reg.list_plugins()
        assert len(specs) == 2

    def test_list_plugins_with_type_filter(self):
        reg = get_plugin_registry()
        reg.register(_make_llm("mock_llm"), "llm")
        reg.register(_make_search("mock_search"), "search")
        specs = reg.list_plugins("llm")
        assert len(specs) == 1
        assert specs[0].name == "mock_llm"

    def test_list_types(self):
        reg = get_plugin_registry()
        types = reg.list_types()
        assert "llm" in types
        assert "search" in types
        assert "embedding" in types

    def test_list_all(self):
        reg = get_plugin_registry()
        reg.register(_make_llm("mock_llm"), "llm")
        all_p = reg.list_all()
        assert "llm" in all_p
        assert "mock_llm" in all_p["llm"]

    def test_set_default(self):
        reg = get_plugin_registry()
        p1 = _make_llm("mock_llm_1")
        p2 = _make_llm("mock_llm_2")
        reg.register(p1, "llm")
        reg.register(p2, "llm")
        reg.set_default("llm", "mock_llm_2")
        assert reg.get_llm() is p2

    def test_is_configured(self):
        reg = get_plugin_registry()
        p = _make_search("mock_search")
        reg.register(p, "search")
        assert reg.is_configured("mock_search") is True

    def test_is_configured_not_found(self):
        reg = get_plugin_registry()
        assert reg.is_configured("nope") is False

    def test_execute_rejects_non_executable_plugins(self):
        reg = get_plugin_registry()
        p = _make_search("mock_search")
        reg.register(p, "search")
        with pytest.raises(ValueError, match="does not support execute"):
            import asyncio
            asyncio.run(reg.execute("mock_search", "search", query="test"))

    def test_execute_external_plugin(self):
        from backend.plugins.base import Plugin
        class _MockExt(Plugin):
            spec = PluginSpec(name="ext_test", description="Ext", version="1.0.0", tags=["ping"])
            async def initialize(self): pass
            async def execute(self, action, **kw):
                if action == "ping":
                    return "pong"
                raise ValueError(f"Unknown: {action}")
        reg = get_plugin_registry()
        p = _MockExt()
        import asyncio
        asyncio.run(p.initialize())
        reg.register(p, "external")
        result = asyncio.run(reg.execute("ext_test", "ping"))
        assert result == "pong"

    def test_execute_nonexistent(self):
        reg = get_plugin_registry()
        import asyncio
        with pytest.raises(KeyError):
            asyncio.run(reg.execute("nope", "search"))

    def test_get_typed_with_name(self):
        reg = get_plugin_registry()
        p = MockEmbeddingProvider()
        reg.register(p, "embedding")
        assert reg.get_typed("embedding", "mock_embed") is p

    def test_get_typed_fallback(self):
        reg = get_plugin_registry()
        assert reg.get_typed("nonexistent") is None

    def test_vdb_provider(self):
        reg = get_plugin_registry()
        p = MockVectorDBProvider()
        reg.register(p, "vector_db")
        assert reg.get_vector_db() is p

    def test_storage_provider(self):
        reg = get_plugin_registry()
        p = MockStorageProvider()
        reg.register(p, "storage")
        assert reg.get_storage() is p

    def test_memory_provider(self):
        reg = get_plugin_registry()
        p = MockMemoryProvider()
        reg.register(p, "memory")
        assert reg.get_memory() is p

    def test_reset_creates_new_instance(self):
        r1 = get_plugin_registry()
        reset_plugin_registry()
        r2 = get_plugin_registry()
        assert r1 is not r2

    def test_cache_singleton(self):
        reset_plugin_registry()
        r1 = get_plugin_registry()
        r2 = get_plugin_registry()
        assert r1 is r2
