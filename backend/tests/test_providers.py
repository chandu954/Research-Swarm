"""Tests for concrete provider implementations."""
from __future__ import annotations


class TestVectorDBProvider:
    def test_chromadb_spec(self):
        from backend.providers.vector_db import ChromaDBVectorStore
        p = ChromaDBVectorStore()
        assert p.spec.name == "chromadb"
        assert p.spec.version == "1.0.0"

    def test_chromadb_initialize_cleanup(self):
        from backend.providers.vector_db import ChromaDBVectorStore
        import asyncio
        p = ChromaDBVectorStore()
        asyncio.run(p.initialize())
        asyncio.run(p.cleanup())

    def test_chromadb_before_init_does_not_raise(self):
        from backend.providers.vector_db import ChromaDBVectorStore
        import asyncio
        p = ChromaDBVectorStore()
        # store() logs a warning and returns without raising before init
        asyncio.run(p.store(["1"], ["test"], [[0.1] * 4]))


class TestStorageProvider:
    def test_local_storage_spec(self):
        from backend.providers.storage import LocalStorageProvider
        p = LocalStorageProvider()
        assert p.spec.name == "local"

    def test_local_storage_save_load_delete(self):
        from backend.providers.storage import LocalStorageProvider
        import asyncio
        p = LocalStorageProvider()
        asyncio.run(p.initialize())
        try:
            path = "test_storage/test_file.txt"
            content = b"hello world"
            saved = asyncio.run(p.save(path, content))
            assert saved.endswith(path)
            loaded = asyncio.run(p.load(path))
            assert loaded == content
            exists = asyncio.run(p.exists(path))
            assert exists is True
            deleted = asyncio.run(p.delete(path))
            assert deleted is True
            gone = asyncio.run(p.exists(path))
            assert gone is False
        finally:
            import shutil
            shutil.rmtree(p._base_path, ignore_errors=True)

    def test_local_storage_load_missing(self):
        from backend.providers.storage import LocalStorageProvider
        import asyncio
        p = LocalStorageProvider()
        asyncio.run(p.initialize())
        try:
            loaded = asyncio.run(p.load("nonexistent.txt"))
            assert loaded is None
        finally:
            import shutil
            shutil.rmtree(p._base_path, ignore_errors=True)


class TestMemoryProvider:
    def test_conversation_memory_spec(self):
        from backend.providers.memory import ConversationMemoryProvider
        p = ConversationMemoryProvider()
        assert p.spec.name == "conversation"

    def test_conversation_memory_store_retrieve(self):
        from backend.providers.memory import ConversationMemoryProvider
        import asyncio
        p = ConversationMemoryProvider()
        asyncio.run(p.initialize())
        try:
            asyncio.run(p.store("test_conv", "Hello", tags=["user"]))
            result = asyncio.run(p.retrieve("test_conv"))
            assert result is not None
            assert len(result) == 1
            assert result[0]["role"] == "user"
            assert result[0]["content"] == "Hello"
        finally:
            import shutil
            shutil.rmtree("./data/memory", ignore_errors=True)

    def test_conversation_memory_delete(self):
        from backend.providers.memory import ConversationMemoryProvider
        import asyncio
        p = ConversationMemoryProvider()
        asyncio.run(p.initialize())
        try:
            asyncio.run(p.store("del_conv", "data"))
            deleted = asyncio.run(p.delete("del_conv"))
            assert deleted is True
            result = asyncio.run(p.retrieve("del_conv"))
            assert result is None
        finally:
            import shutil
            shutil.rmtree("./data/memory", ignore_errors=True)

    def test_conversation_memory_missing_key(self):
        from backend.providers.memory import ConversationMemoryProvider
        import asyncio
        p = ConversationMemoryProvider()
        asyncio.run(p.initialize())
        try:
            result = asyncio.run(p.retrieve("nope"))
            assert result is None
        finally:
            import shutil
            shutil.rmtree("./data/memory", ignore_errors=True)


class TestEmbeddingProviders:
    def test_ollama_embedding_spec(self):
        from backend.providers.embedding import OllamaEmbeddingProvider
        p = OllamaEmbeddingProvider()
        assert p.spec.name == "ollama"
        assert p.spec.version == "1.0.0"

    def test_openrouter_embedding_spec(self):
        from backend.providers.embedding import OpenRouterEmbeddingProvider
        p = OpenRouterEmbeddingProvider()
        assert p.spec.name == "openrouter"


class TestSearchProviders:
    def test_duckduckgo_spec(self):
        from backend.providers.search import DuckDuckGoProvider
        p = DuckDuckGoProvider()
        assert p.spec.name == "duckduckgo"
        assert p.spec.version == "1.0.0"

    def test_bing_spec(self):
        from backend.providers.search import BingProvider
        p = BingProvider()
        assert p.spec.name == "bing"

    def test_serper_spec(self):
        from backend.providers.search import SerperProvider
        p = SerperProvider()
        assert p.spec.name == "serper"
