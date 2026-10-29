"""Tests for ChromaDB vector store provider.

Split from backend/tests/test_realtime_stream_infra.py.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from backend.providers.vector_db import ChromaDBVectorStore


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


class TestChromaDBVectorStore:
    def test_initialize_without_chromadb(self):
        store = ChromaDBVectorStore()
        with patch("backend.providers.vector_db.chromadb", None):
            asyncio_run(store.initialize())
        assert store._client is None

    def test_initialize_success_and_failure(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
        fake_client = MagicMock()
        collection = MagicMock()
        fake_client.get_or_create_collection.return_value = collection
        fake_chromadb = MagicMock()
        fake_chromadb.PersistentClient.return_value = fake_client

        store = ChromaDBVectorStore()
        with patch("backend.providers.vector_db.chromadb", fake_chromadb), patch(
            "backend.providers.vector_db.Settings"
        ) as settings:
            asyncio_run(store.initialize())

        assert store._collection is collection
        assert store._persist_directory == str(tmp_path / "chroma")
        settings.assert_called_once_with(anonymized_telemetry=False)

        broken = ChromaDBVectorStore()
        fake_chromadb.PersistentClient.side_effect = RuntimeError("cannot open")
        with patch("backend.providers.vector_db.chromadb", fake_chromadb), patch(
            "backend.providers.vector_db.Settings"
        ):
            asyncio_run(broken.initialize())
        assert broken._client is None

    def test_store_query_delete_paths(self):
        store = ChromaDBVectorStore()

        asyncio_run(store.store(["1"], ["doc"]))
        asyncio_run(store.delete(["1"]))
        assert asyncio_run(store.query([0.1])) == []

        collection = MagicMock()
        store._collection = collection
        asyncio_run(store.store(["1", "2"], ["a", "b"]))
        collection.add.assert_called_once()
        assert collection.add.call_args.kwargs["metadatas"] == [{}, {}]

        collection.add.side_effect = RuntimeError("write failed")
        asyncio_run(store.store(["3"], ["c"]))

        collection.query.return_value = {
            "documents": [["first", "second"]],
            "metadatas": [[{"page": 1}, {"page": 2}]],
            "distances": [[0.25, 0.75]],
        }
        results = asyncio_run(store.query([0.1], top_k=2, filter={"page": 1}))
        assert results[0]["score"] == 0.75
        assert results[1]["distance"] == 0.75
        assert collection.query.call_args.kwargs["where"] == {"page": 1}

        collection.query.return_value = {
            "documents": [["only"]],
            "metadatas": [[{}]],
        }
        assert asyncio_run(store.query([0.1]))[0]["distance"] == 0.0

        collection.query.side_effect = RuntimeError("query failed")
        assert asyncio_run(store.query([0.1])) == []

        asyncio_run(store.delete(["1"]))
        collection.delete.side_effect = RuntimeError("delete failed")
        asyncio_run(store.delete(["1"]))

        asyncio_run(store.cleanup())
        assert store._collection is None
