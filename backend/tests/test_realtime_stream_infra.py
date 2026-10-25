"""Coverage for realtime collaboration, SSE streams, providers, and infrastructure.

These tests exercise branches that the higher-level API tests do not reach:
WebSocket room lifecycle, stream persistence mirroring, provider fallbacks,
embedding failures, ChromaDB wrappers, and lightweight DB helpers.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table
from sqlalchemy.dialects import sqlite as sqlite_dialect

from backend.agents.merge import merge_research
from backend.api import metrics as metrics_module
from backend.api.stream import (
    AsyncQueueAdapter,
    StreamManager,
    event_stream,
    get_stream_manager,
    make_log,
)
from backend.api.websocket import (
    Connection,
    WorkspaceManager,
    WorkspaceRoom,
    get_workspace_manager,
)
from backend.llm.openrouter_provider import OpenRouterProvider
from backend.providers.embedding import (
    OllamaEmbeddingProvider,
    OpenRouterEmbeddingProvider,
)
from backend.providers.search import (
    BingProvider,
    DuckDuckGoProvider,
    SerperProvider,
    _clean_url,
    _fallback_search,
    _format_results,
)
from backend.providers.vector_db import ChromaDBVectorStore
from backend.tools.registry import ToolCategory, ToolRegistry, ToolSpec, _is_async
from backend.tools.search import hybrid_search_web, search_web


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


# ── WebSocket rooms ─────────────────────────────────────────────


class FakeSocket:
    def __init__(self, fail=False):
        self.sent: list[str] = []
        self.fail = fail

    async def send_text(self, text: str):
        if self.fail:
            raise RuntimeError("socket closed")
        self.sent.append(text)


class TestWorkspaceRoomBranches:
    def test_typing_users_filters_stale_entries(self):
        room = WorkspaceRoom("ws-1")
        room.add(Connection(FakeSocket(), "user-1", "Alice"))
        room.add(Connection(FakeSocket(), "user-2", "Bob"))
        room._typing["user-1"] = time.time()
        room._typing["user-2"] = time.time() - 60
        room._typing["ghost"] = time.time() - 60

        active = room.typing_users

        assert active == [{"userId": "user-1", "name": "Alice"}]
        assert "user-2" not in room._typing
        assert "ghost" not in room._typing

    def test_handle_message_ignores_invalid_and_unknown_messages(self):
        room = WorkspaceRoom("ws-1")
        conn = Connection(FakeSocket(), "user-1", "Alice")
        room.add(conn)

        asyncio_run(room.handle_message("not-json", conn))
        asyncio_run(room.handle_message(json.dumps({"type": "unknown"}), conn))
        asyncio_run(room.handle_message(json.dumps({"type": "ping"}), conn))

        assert json.loads(conn.ws.sent[0]) == {"type": "pong"}

    def test_chat_send_ignores_empty_and_caps_history(self):
        room = WorkspaceRoom("ws-1")
        conn = Connection(FakeSocket(), "user-1", "Alice")
        room.add(conn)

        asyncio_run(room.handle_message(json.dumps({"type": "chat:send"}), conn))
        asyncio_run(
            room.handle_message(
                json.dumps({"type": "chat:send", "payload": {"content": "   "}}),
                conn,
            )
        )
        assert room.chat_messages == []

        for index in range(101):
            asyncio_run(
                room.handle_message(
                    json.dumps(
                        {
                            "type": "chat:send",
                            "payload": {"content": f"message-{index}"},
                        }
                    ),
                    conn,
                )
            )

        assert len(room.chat_messages) == 100
        assert room.chat_messages[0].content == "message-1"
        history = room.get_chat_history()
        assert len(history) == 50
        assert history[-1]["content"] == "message-100"

    def test_typing_broadcast_excludes_sender(self):
        room = WorkspaceRoom("ws-1")
        sender = Connection(FakeSocket(), "user-1", "Alice")
        other = Connection(FakeSocket(), "user-2", "Bob")
        room.add(sender)
        room.add(other)

        asyncio_run(
            room.handle_message(
                json.dumps({"type": "typing", "payload": {"isTyping": True}}), sender
            )
        )

        assert sender.ws.sent == []
        payload = json.loads(other.ws.sent[-1])
        assert payload["type"] == "typing"
        assert payload["payload"]["typingUsers"][0]["userId"] == "user-1"

        asyncio_run(
            room.handle_message(
                json.dumps({"type": "typing", "payload": {"isTyping": False}}), sender
            )
        )
        assert "user-1" not in room._typing

    def test_research_and_document_broadcasts(self):
        room = WorkspaceRoom("ws-1")
        socket = FakeSocket()
        room.add(Connection(socket, "user-1", "Alice"))

        asyncio_run(room.broadcast_research_start("u", "A", "task", "q" * 300))
        asyncio_run(room.broadcast_research_log("task", {"line": 1}))
        asyncio_run(room.broadcast_research_complete("task", "u"))
        asyncio_run(room.broadcast_document_added({"id": "doc"}))
        asyncio_run(room.broadcast_document_removed("doc"))

        types = [json.loads(item)["type"] for item in socket.sent]
        assert types == [
            "research:start",
            "research:log",
            "research:complete",
            "document:added",
            "document:removed",
        ]
        assert len(json.loads(socket.sent[0])["payload"]["query"]) == 200

    def test_broadcast_drops_stale_connections_and_swallows_send_errors(self):
        room = WorkspaceRoom("ws-1")
        good = Connection(FakeSocket(), "user-1", "Alice")
        bad = Connection(FakeSocket(fail=True), "user-2", "Bob")
        room.add(good)
        room.add(bad)

        asyncio_run(room.broadcast({"type": "test"}))
        assert "user-2" not in room.user_ids
        assert len(good.ws.sent) == 1

        asyncio_run(room._send(Connection(FakeSocket(fail=True), "x"), {"type": "x"}))

    def test_manager_presence_disconnect_and_singleton(self):
        manager = WorkspaceManager()
        asyncio_run(manager.broadcast_presence("missing"))
        manager.disconnect("missing", "user")

        room = manager.get_or_create("ws-1")
        room.add(Connection(FakeSocket(), "user-1", "Alice"))
        asyncio_run(manager.broadcast_presence("ws-1"))
        assert json.loads(room.connections["user-1"].ws.sent[-1])["type"] == "presence"

        manager.disconnect("ws-1", "user-1")
        assert "ws-1" not in manager._rooms

        with patch("backend.api.websocket._manager", None):
            assert get_workspace_manager() is get_workspace_manager()


# ── SSE streams ─────────────────────────────────────────────────


class TestAsyncQueueAdapter:
    def test_put_closed_and_full_queue_are_ignored(self):
        adapter = AsyncQueueAdapter(maxsize=1)
        adapter.put("one")
        adapter.put("two")  # queue full — swallowed
        assert adapter._queue.qsize() == 1
        adapter.close()
        adapter.put("three")
        assert adapter._queue.qsize() == 1

    def test_get_async_returns_queued_item(self):
        adapter = AsyncQueueAdapter()
        adapter.put({"log": 1})
        assert asyncio_run(adapter.get_async()) == {"log": 1}


class TestEventStream:
    def _collect(self, task_id, adapter):
        async def collect():
            return [event async for event in event_stream(task_id, adapter)]

        return asyncio_run(collect())

    def test_yields_logs_then_done_on_close(self):
        adapter = AsyncQueueAdapter()
        adapter.put({"agent": "planner"})
        adapter.close()

        events = self._collect("task-1", adapter)

        assert "event: log" in events[0]
        assert json.loads(events[0].split("data: ", 1)[1])["agent"] == "planner"
        assert "event: done" in events[1]
        assert '"task_id": "task-1"' in events[1]

    def test_none_sentinel_terminates_without_log_event(self):
        adapter = AsyncQueueAdapter()
        adapter.put(None)
        adapter.close()

        events = self._collect("task-2", adapter)
        assert len(events) == 1
        assert "event: done" in events[0]

    def test_heartbeat_when_queue_is_idle(self):
        adapter = AsyncQueueAdapter()

        async def scenario():
            with patch(
                "backend.api.stream.asyncio.wait_for",
                AsyncMock(side_effect=asyncio.TimeoutError),
            ):
                generator = event_stream("task-3", adapter)
                first = await generator.__anext__()
                adapter.close()
                rest = [event async for event in generator]
            return first, rest

        first, rest = asyncio_run(scenario())
        assert "event: heartbeat" in first
        assert "event: done" in rest[-1]

    def test_cancellation_is_reraised(self):
        adapter = AsyncQueueAdapter()

        async def scenario():
            with patch(
                "backend.api.stream.asyncio.wait_for",
                AsyncMock(side_effect=asyncio.CancelledError),
            ):
                generator = event_stream("task-4", adapter)
                await generator.__anext__()

        with pytest.raises(asyncio.CancelledError):
            asyncio_run(scenario())


class TestStreamManager:
    def test_stream_lifecycle_and_owner(self):
        manager = StreamManager()
        adapter = manager.create_stream("task-1", owner_user_id="user-1")

        assert manager.get_stream("task-1") is adapter
        assert manager.has_stream("task-1") is True
        assert manager.get_or_create_stream("task-1") is adapter
        assert manager.get_owner("task-1") == "user-1"
        assert manager.get_owner("missing") is None

        other = manager.get_or_create_stream("task-2")
        assert manager.has_stream("task-2") is True
        assert other is manager.get_stream("task-2")

        manager.close_stream("task-1")
        assert manager.has_stream("task-1") is False
        assert manager.get_owner("task-1") is None
        manager.close_stream("missing")

    def test_task_registration_and_cancellation(self):
        async def scenario():
            manager = StreamManager()

            async def sleeper():
                await asyncio.sleep(30)

            first = asyncio.create_task(sleeper())
            second = asyncio.create_task(sleeper())
            done = asyncio.create_task(asyncio.sleep(0))
            await done

            manager.register_task("first", first)
            manager.register_task("second", second)
            manager.register_task("done", done)
            assert manager.get_task("first") is first

            manager.unregister_task("first", second)  # wrong task — ignored
            assert manager.get_task("first") is first
            manager.unregister_task("first", first)
            assert manager.get_task("first") is None
            manager.register_task("first", first)

            await manager.cancel_all_tasks()
            return first, second, done

        first, second, done = asyncio_run(scenario())
        assert first.cancelled()
        assert second.cancelled()
        assert done.done()

    def test_persistence_and_push_log(self):
        manager = StreamManager()
        manager.attach_persistence("task", supabase_user_id="sb", session_id="sess")
        assert manager.get_persistence("task") == {
            "user_id": "sb",
            "session_id": "sess",
        }

        manager.push_log("missing", {"agent": "x"})  # no adapter

        manager.create_stream("task")
        with patch.object(manager, "_mirror_to_supabase") as mirror:
            manager.push_log("task", {"agent": "x"})
        assert manager.get_stream("task")._queue.qsize() == 1
        mirror.assert_called_once_with("task", {"agent": "x"})

    def test_mirror_to_supabase_updates_statuses_and_messages(self):
        fake = MagicMock()
        manager = StreamManager()
        manager.attach_persistence("task", supabase_user_id="sb", session_id="sess")

        with patch.dict(sys.modules, {"backend.core.supabase": fake}):
            manager._mirror_to_supabase(
                "task",
                {"agent": "planner", "action": "plan", "status": "running"},
            )
            fake.update_session.assert_called_with("sess", status="planning")
            assert fake.upsert_agent_run.call_args.kwargs["started_at"] is not None

            fake.reset_mock()
            manager._mirror_to_supabase(
                "task",
                {"agent": "merge", "action": "complete", "status": "completed"},
            )
            fake.update_session.assert_called_with("sess", status="completed")
            assert fake.upsert_agent_run.call_args.kwargs["finished_at"] is not None

            fake.reset_mock()
            manager._mirror_to_supabase(
                "task",
                {
                    "agent": "answer_agent",
                    "action": "error",
                    "status": "failed",
                    "details": "x" * 700,
                },
            )
            assert fake.update_session.call_args.kwargs["error"] == "x" * 500

            fake.reset_mock()
            manager._mirror_to_supabase(
                "task",
                {
                    "agent": "system",
                    "action": "message",
                    "status": "completed",
                    "details": "hello",
                },
            )
            fake.insert_message.assert_called_once_with(
                session_id="sess", role="assistant", content="hello"
            )

            fake.update_session.side_effect = RuntimeError("db down")
            manager._mirror_to_supabase(
                "task", {"agent": "planner", "action": "x", "status": "running"}
            )

        manager._mirror_to_supabase("unknown", {"agent": "x"})

    def test_singleton_and_log_factory(self):
        with patch("backend.api.stream._stream_manager", None):
            assert get_stream_manager() is get_stream_manager()
        log = make_log("agent", "action", "completed", "details")
        assert log["agent"] == "agent"
        assert log["details"] == "details"
        assert isinstance(log["timestamp"], float)


# ── ChromaDB vector store ───────────────────────────────────────


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


# ── Search providers ────────────────────────────────────────────


class FakeHttpResponse:
    def __init__(self, payload=None, text="", error=None):
        self.payload = payload or {}
        self.text = text
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


class FakeDDGS:
    results = []
    error = None
    calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def text(self, *args, **kwargs):
        FakeDDGS.calls.append((args, kwargs))
        if FakeDDGS.error:
            raise FakeDDGS.error
        return FakeDDGS.results


class TestSearchProviders:
    def test_clean_url_and_format_results(self):
        assert _clean_url("") == ""
        assert _clean_url("https://a.test/x") == "https://a.test/x"
        assert _clean_url("a.test/x") == "https://a.test/x"
        assert (
            _clean_url("https://a.test/x?utm_source=y&ref=z&q=1")
            == "https://a.test/x?q=1"
        )

        formatted = _format_results(
            [
                {"href": "a.test", "title": "A", "body": "Snippet"},
                {"href": "", "title": "skip"},
                {"href": "b.test", "title": "B"},
            ],
            "duckduckgo",
        )
        assert [item["url"] for item in formatted] == [
            "https://a.test",
            "https://b.test",
        ]
        assert formatted[0]["position"] == 1
        assert formatted[1]["position"] == 3
        assert formatted[1]["snippet"] == ""

    def test_duckduckgo_uses_first_successful_backend(self, monkeypatch):
        FakeDDGS.results = [
            {"href": "example.com/page", "title": "Example", "body": "Body"}
        ]
        FakeDDGS.error = None
        FakeDDGS.calls = []
        monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=FakeDDGS))

        provider = DuckDuckGoProvider()
        results = asyncio_run(provider.search("query", max_results=2, region="us-en"))

        assert results[0]["source"] == "duckduckgo"
        assert results[0]["url"] == "https://example.com/page"
        assert FakeDDGS.calls[0][1]["backend"] == "html"

    def test_duckduckgo_falls_back_when_packages_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "ddgs", None)
        monkeypatch.setitem(sys.modules, "duckduckgo_search", None)
        with patch(
            "backend.providers.search._fallback_search",
            AsyncMock(return_value=[{"title": "fallback"}]),
        ) as fallback:
            results = asyncio_run(DuckDuckGoProvider().search("query"))
        assert results == [{"title": "fallback"}]
        fallback.assert_awaited_once()

    def test_duckduckgo_retries_then_falls_back(self, monkeypatch):
        FakeDDGS.error = RuntimeError("backend down")
        FakeDDGS.results = []
        monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=FakeDDGS))
        with patch(
            "backend.providers.search.asyncio.sleep", AsyncMock()
        ) as sleep, patch(
            "backend.providers.search._fallback_search",
            AsyncMock(return_value=[]),
        ) as fallback:
            assert asyncio_run(DuckDuckGoProvider().search("query")) == []
        sleep.assert_awaited_once()
        fallback.assert_awaited_once()

    def test_bing_without_key_falls_back(self, monkeypatch):
        monkeypatch.delenv("BING_API_KEY", raising=False)
        with patch.object(
            DuckDuckGoProvider, "search", AsyncMock(return_value=[{"title": "ddg"}])
        ) as ddg:
            results = asyncio_run(BingProvider().search("query", max_results=3))
        assert results == [{"title": "ddg"}]
        ddg.assert_awaited_once()

    def test_bing_success_and_failure(self, monkeypatch):
        monkeypatch.setenv("BING_API_KEY", "key")
        response = FakeHttpResponse(
            {
                "webPages": {
                    "value": [
                        {"name": "One", "url": "https://one.test", "snippet": "S1"},
                        {"url": "https://two.test"},
                    ]
                }
            }
        )
        client = AsyncMock()
        client.get.return_value = response
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        with patch("backend.providers.search.httpx.AsyncClient", return_value=client):
            results = asyncio_run(BingProvider().search("query", max_results=5))
        assert results[0]["title"] == "One"
        assert results[1]["title"] == "Result 2"
        assert (
            client.get.call_args.kwargs["headers"]["Ocp-Apim-Subscription-Key"] == "key"
        )

        response.error = RuntimeError("api down")
        with patch("backend.providers.search.httpx.AsyncClient", return_value=client):
            assert asyncio_run(BingProvider().search("query")) == []

    def test_serper_without_key_falls_back(self, monkeypatch):
        monkeypatch.delenv("SERPER_API_KEY", raising=False)
        with patch.object(
            DuckDuckGoProvider, "search", AsyncMock(return_value=[{"title": "ddg"}])
        ) as ddg:
            results = asyncio_run(SerperProvider().search("query"))
        assert results == [{"title": "ddg"}]
        ddg.assert_awaited_once()

    def test_serper_success_and_failure(self, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "key")
        response = FakeHttpResponse(
            {
                "organic": [
                    {"title": "One", "link": "https://one.test", "snippet": "S"},
                    {"link": "https://two.test"},
                ]
            }
        )
        client = AsyncMock()
        client.post.return_value = response
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        with patch("backend.providers.search.httpx.AsyncClient", return_value=client):
            results = asyncio_run(SerperProvider().search("query"))
        assert results[0]["source"] == "serper"
        assert results[1]["title"] == "Result 2"

        response.error = RuntimeError("api down")
        with patch("backend.providers.search.httpx.AsyncClient", return_value=client):
            assert asyncio_run(SerperProvider().search("query")) == []

    def test_fallback_html_parsing_and_errors(self):
        response = FakeHttpResponse(
            text=(
                '<a href="https://one.test" class="result-link">One <b>Title</b></a>'
                '<a href="https://two.test" class="result-link">Two</a>'
            )
        )
        client = MagicMock()
        client.get.return_value = response
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        with patch("backend.providers.search.httpx.Client", return_value=client):
            results = _fallback_search("query", max_results=1)
        assert len(results) == 1
        assert results[0]["title"] == "One Title"

        response.text = "<html>nothing</html>"
        with patch("backend.providers.search.httpx.Client", return_value=client):
            assert _fallback_search("query") == []

        response.error = RuntimeError("network down")
        with patch("backend.providers.search.httpx.Client", return_value=client):
            assert _fallback_search("query") == []


# ── Embedding providers ────────────────────────────────────────


class TestEmbeddingProviders:
    def test_ollama_lifecycle_and_embedding_paths(self, monkeypatch):
        provider = OllamaEmbeddingProvider()
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
        with patch("backend.providers.embedding.httpx.Client") as client_cls:
            asyncio_run(provider.initialize())
        assert provider.base_url == "http://ollama.test"
        client_cls.assert_called_once()

        asyncio_run(provider.cleanup())
        assert provider._client is None

        assert provider.embed([]) is None
        with pytest.raises(RuntimeError):
            provider.embed(["text"])

        response = FakeHttpResponse({"embedding": [0.1, 0.2]})
        client = MagicMock()
        client.post.return_value = response
        provider._client = client
        assert provider.embed(["one", "two"], model="m") == [
            [0.1, 0.2],
            [0.1, 0.2],
        ]
        assert client.post.call_args.kwargs["json"]["truncate"] is True
        assert provider.embed_query("one", model="m") == [0.1, 0.2]

        response.payload = {}
        assert provider.embed(["one"]) is None

        response.error = RuntimeError("embedding failed")
        result = provider.embed(["one"])
        assert result == [[0.0] * 768]

        provider._client = None
        with pytest.raises(RuntimeError):
            provider.embed_query("one")

    def test_openrouter_lifecycle_and_embedding_paths(self, monkeypatch):
        provider = OpenRouterEmbeddingProvider()
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        with patch("backend.providers.embedding.httpx.Client") as client_cls:
            asyncio_run(provider.initialize())
        assert provider.api_key == "key"
        client_cls.assert_called_once()

        asyncio_run(provider.cleanup())
        assert provider._client is None

        assert provider.embed([]) is None
        with pytest.raises(RuntimeError):
            provider.embed(["text"])

        response = FakeHttpResponse({"data": [{"embedding": [0.3]}]})
        client = MagicMock()
        client.post.return_value = response
        provider._client = client
        assert provider.embed(["one"]) == [[0.3]]
        assert provider.embed_query("one") == [0.3]
        assert client.post.call_args.kwargs["headers"]["Authorization"] == "Bearer key"

        response.error = RuntimeError("embedding failed")
        assert provider.embed(["one"]) == [[0.0] * 768]


# ── DB session helpers ─────────────────────────────────────────


class FakeSessionContext:
    def __init__(self):
        self.session = MagicMock()
        self.session.commit = AsyncMock()
        self.session.rollback = AsyncMock()
        self.session.close = AsyncMock()

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return False


class TestDatabaseSessionHelpers:
    def test_get_session_commits_and_closes(self):
        from backend.db.session import get_session

        context = FakeSessionContext()

        async def consume():
            generator = get_session()
            session = await generator.__anext__()
            assert session is context.session
            with pytest.raises(StopAsyncIteration):
                await generator.__anext__()

        with patch("backend.db.session._async_session_factory", return_value=context):
            asyncio_run(consume())

        context.session.commit.assert_awaited_once()
        context.session.close.assert_awaited_once()
        context.session.rollback.assert_not_awaited()

    def test_get_session_rolls_back_on_error(self):
        from backend.db.session import get_session

        context = FakeSessionContext()

        async def consume():
            generator = get_session()
            await generator.__anext__()
            with pytest.raises(RuntimeError, match="boom"):
                await generator.athrow(RuntimeError("boom"))

        with patch("backend.db.session._async_session_factory", return_value=context):
            asyncio_run(consume())

        context.session.rollback.assert_awaited_once()
        context.session.close.assert_awaited_once()
        context.session.commit.assert_not_awaited()

    def test_migrate_columns_adds_missing_columns(self):
        from backend.db import session as session_module

        metadata = MetaData()
        table = Table(
            "t",
            metadata,
            Column("existing", String),
            Column("flag", Boolean, nullable=False),
            Column("count", Integer, nullable=False),
            Column("label", String, nullable=True, default="x"),
            Column("bad", String),
        )
        broken = Table("broken", metadata, Column("x", String))

        alters: list[str] = []

        class Rows:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        class Connection:
            dialect = sqlite_dialect.dialect()

            async def execute(self, statement, params=None):
                sql = str(statement)
                if "information_schema" in sql:
                    if params["t"] == "broken":
                        raise RuntimeError("information schema unavailable")
                    return Rows([("existing",)])
                if "ADD COLUMN bad" in sql:
                    raise RuntimeError("alter failed")
                alters.append(sql)
                return MagicMock()

        class Begin:
            async def __aenter__(self):
                return Connection()

            async def __aexit__(self, *_args):
                return False

        class Engine:
            def begin(self):
                return Begin()

        fake_base = SimpleNamespace(
            metadata=SimpleNamespace(tables={"broken": broken, "t": table})
        )
        with patch.object(session_module, "Base", fake_base), patch.object(
            session_module, "_engine", Engine()
        ):
            asyncio_run(session_module._migrate_columns())

        joined = "\n".join(alters)
        assert "ADD COLUMN flag BOOLEAN NOT NULL DEFAULT false" in joined
        assert "ADD COLUMN count INTEGER NOT NULL DEFAULT 0" in joined
        assert "ADD COLUMN label VARCHAR NULL DEFAULT x" in joined
        assert "existing" not in joined
        assert "ADD COLUMN bad" not in joined

    def test_init_db_and_close_db(self):
        from backend.db import session as session_module

        connection = MagicMock()
        connection.run_sync = AsyncMock()

        class Begin:
            async def __aenter__(self):
                return connection

            async def __aexit__(self, *_args):
                return False

        engine = MagicMock()
        engine.begin.return_value = Begin()
        engine.dispose = AsyncMock()

        with patch.object(session_module, "_engine", engine), patch.object(
            session_module, "_migrate_columns", AsyncMock()
        ) as migrate:
            asyncio_run(session_module.init_db())
            asyncio_run(session_module.close_db())

        connection.run_sync.assert_awaited_once()
        migrate.assert_awaited_once()
        engine.dispose.assert_awaited_once()


# ── Web search tools ───────────────────────────────────────────


class TestWebSearchTools:
    def _registry(self, provider):
        registry = MagicMock()
        registry.get_search.return_value = provider
        registry.get_llm.return_value = None
        return registry

    def test_search_web_without_provider_and_with_error(self):
        with patch(
            "backend.tools.search.get_plugin_registry",
            return_value=self._registry(None),
        ):
            assert search_web("query") == []

        provider = MagicMock()
        provider.search = AsyncMock(side_effect=RuntimeError("search down"))
        with patch(
            "backend.tools.search.get_plugin_registry",
            return_value=self._registry(provider),
        ):
            assert search_web("query") == []

    def test_search_web_returns_provider_results(self):
        provider = MagicMock()
        provider.search = AsyncMock(return_value=[{"title": "T"}])
        with patch(
            "backend.tools.search.get_plugin_registry",
            return_value=self._registry(provider),
        ):
            assert search_web("query", max_results=2) == [{"title": "T"}]

    def test_hybrid_search_returns_aggregated_results(self):
        with patch(
            "backend.search.aggregator.aggregate_search",
            AsyncMock(return_value=[{"title": "aggregated"}]),
        ):
            assert hybrid_search_web("query") == [{"title": "aggregated"}]

    def test_hybrid_search_falls_back_to_provider_and_reranks(self):
        provider = MagicMock()
        provider.search = AsyncMock(return_value=[{"title": "raw"}])
        registry = self._registry(provider)
        with patch(
            "backend.search.aggregator.aggregate_search",
            AsyncMock(side_effect=RuntimeError("aggregate down")),
        ), patch(
            "backend.search.hybrid.hybrid_rerank",
            return_value=[{"title": "reranked"}],
        ) as rerank, patch(
            "backend.tools.search.get_plugin_registry", return_value=registry
        ):
            results = hybrid_search_web("query", max_results=3)

        assert results == [{"title": "reranked"}]
        embed_fn = rerank.call_args.kwargs["embed_fn"]
        assert embed_fn("text") is None

    def test_hybrid_search_uses_llm_embeddings_and_handles_empty(self):
        provider = MagicMock()
        provider.search = AsyncMock(return_value=[{"title": "raw"}])
        llm = MagicMock()
        llm.create_embedding.return_value = [0.1]
        registry = self._registry(provider)
        registry.get_llm.return_value = llm

        captured = {}

        def fake_rerank(query, raw, **kwargs):
            captured.update(kwargs)
            return [{"title": "reranked"}]

        with patch(
            "backend.search.aggregator.aggregate_search",
            AsyncMock(return_value=[]),
        ), patch("backend.search.hybrid.hybrid_rerank", side_effect=fake_rerank), patch(
            "backend.tools.search.get_plugin_registry", return_value=registry
        ):
            assert hybrid_search_web("query") == [{"title": "reranked"}]
        assert captured["embed_fn"]("text") == [0.1]

        provider.search = AsyncMock(return_value=[])
        with patch(
            "backend.search.aggregator.aggregate_search",
            AsyncMock(return_value=[]),
        ), patch("backend.tools.search.get_plugin_registry", return_value=registry):
            assert hybrid_search_web("query") == []

        provider.search = AsyncMock(side_effect=RuntimeError("provider down"))
        with patch(
            "backend.search.aggregator.aggregate_search",
            AsyncMock(side_effect=RuntimeError("aggregate down")),
        ), patch("backend.tools.search.get_plugin_registry", return_value=registry):
            assert hybrid_search_web("query") == []


# ── Weather plugin ─────────────────────────────────────────────


class TestWeatherPlugin:
    def _plugin(self, units="metric"):
        from backend.plugins.weather import WeatherPlugin

        plugin = WeatherPlugin()
        plugin._units = units
        plugin._base_url = "https://weather.test/v1"
        plugin._client = AsyncMock()
        return plugin

    def test_initialize_and_cleanup(self):
        from backend.plugins.weather import WeatherPlugin

        plugin = WeatherPlugin()
        plugin._config = {"units": "imperial"}
        with patch("backend.plugins.weather.httpx.AsyncClient") as client_cls:
            asyncio_run(plugin.initialize())
        assert plugin._units == "imperial"
        client_cls.assert_called_once()
        plugin._client = AsyncMock()
        asyncio_run(plugin.cleanup())
        plugin._client.aclose.assert_awaited_once()

    def test_forecast_metric_and_imperial(self):
        response = MagicMock()
        response.json.return_value = {"current": {}}
        plugin = self._plugin()
        plugin._client.get.return_value = response

        assert asyncio_run(
            plugin.execute("forecast", {"latitude": 1.0, "longitude": 2.0})
        ) == {"current": {}}
        assert (
            plugin._client.get.call_args.kwargs["params"]["temperature_unit"]
            == "celsius"
        )

        imperial = self._plugin(units="imperial")
        imperial._client.get.return_value = response
        asyncio_run(imperial.execute("forecast", {"latitude": 1.0, "longitude": 2.0}))
        assert (
            imperial._client.get.call_args.kwargs["params"]["temperature_unit"]
            == "fahrenheit"
        )

    def test_geocode_and_unknown_action(self):
        response = MagicMock()
        response.json.return_value = {"results": [{"name": "Paris"}]}
        plugin = self._plugin()
        plugin._client.get.return_value = response

        assert asyncio_run(plugin.execute("geocode", {"city": "Paris"})) == {
            "results": [{"name": "Paris"}]
        }
        assert plugin._client.get.call_args.args[0].startswith("https://geocoding")

        with pytest.raises(ValueError, match="Unknown action"):
            asyncio_run(plugin.execute("storm", {}))


# ── Metrics endpoint ───────────────────────────────────────────


class TestMetricsEndpoint:
    def test_metrics_reports_plugins_and_uptime(self):
        class CallablePlugin:
            def name(self):
                return "callable"

            def version(self):
                return "2.0"

        plain = SimpleNamespace(name="plain", version="1.0")
        anonymous = object()
        registry = MagicMock()
        registry.list_types.return_value = ["llm", "search"]
        registry.list_plugins.side_effect = [
            [CallablePlugin(), plain],
            [anonymous],
        ]
        registry.is_configured.return_value = True

        with patch(
            "backend.api.metrics.get_plugin_registry", return_value=registry
        ), patch.object(metrics_module, "_start_time", 100.0), patch(
            "backend.api.metrics.time.time", return_value=105.4
        ):
            result = asyncio_run(metrics_module.metrics())

        assert result["status"] == "ok"
        assert result["uptime_seconds"] == 5
        assert result["plugins"]["llm"][0] == {
            "name": "callable",
            "version": "2.0",
            "configured": True,
        }
        assert result["plugins"]["llm"][1]["name"] == "plain"
        assert result["plugins"]["search"][0]["name"] == str(anonymous)
        assert result["plugins"]["search"][0]["version"] == "?"


# ── Merge helper ───────────────────────────────────────────────


class TestMergeResearch:
    def test_merges_and_deduplicates_web_and_documents(self):
        result = merge_research(
            [
                {"content": "same", "title": "A", "url": "https://a", "source": "bing"},
                {"snippet": "same", "title": "dup"},
                {"title": "title only"},
                {"content": "   ", "title": "blank"},
            ],
            [
                {"content": "doc", "filename": "paper.pdf", "page": 2},
                {"text": "same"},
                {"text": "second", "title": "Doc title"},
            ],
        )

        assert result["source_count"] == 4
        assert result["document_count"] == 3
        assert result["has_evidence"] is True
        assert [item["content"] for item in result["merged_evidence"]] == [
            "same",
            "title only",
            "doc",
            "second",
        ]
        assert result["merged_evidence"][0]["source"] == "bing"
        assert result["merged_evidence"][2]["title"] == "paper.pdf"
        assert result["merged_evidence"][3]["title"] == "Doc title"

    def test_empty_inputs(self):
        result = merge_research([], [])
        assert result == {
            "merged_evidence": [],
            "has_evidence": False,
            "source_count": 0,
            "document_count": 0,
        }


# ── OpenRouter LLM provider ────────────────────────────────────


class TestOpenRouterProvider:
    def test_initialize_requires_key_and_cleanup(self, monkeypatch):
        provider = OpenRouterProvider()
        with patch(
            "backend.llm.openrouter_provider.get_openrouter_key", return_value=""
        ):
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                asyncio_run(provider.initialize())

        with patch(
            "backend.llm.openrouter_provider.get_openrouter_key", return_value="key"
        ), patch("backend.llm.openrouter_provider.httpx.Client") as client_cls:
            asyncio_run(provider.initialize())
        assert provider.api_key == "key"
        client_cls.assert_called_once_with(timeout=60.0)

        client = provider._client
        asyncio_run(provider.cleanup())
        client.close.assert_called_once()
        assert provider._client is None

        with pytest.raises(RuntimeError, match="not initialized"):
            _ = provider.client

    def test_generate_once_builds_payload(self):
        provider = OpenRouterProvider()
        provider.api_key = "key"
        response = MagicMock()
        response.json.return_value = {
            "choices": [{"message": {"content": "  answer  "}}]
        }
        provider._client = MagicMock()
        provider._client.post.return_value = response

        result = provider._generate_once(
            "prompt",
            "model",
            system_prompt="system",
            options={"temperature": 0.7, "num_predict": 100},
        )
        assert result == "answer"
        payload = provider._client.post.call_args.kwargs["json"]
        assert payload["messages"][0] == {"role": "system", "content": "system"}
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 100

        provider._generate_once("prompt", "model")
        payload = provider._client.post.call_args.kwargs["json"]
        assert payload["messages"] == [{"role": "user", "content": "prompt"}]
        assert payload["temperature"] == 0.2
        assert payload["max_tokens"] == 4096

    def test_create_embedding_success_and_failure(self, monkeypatch):
        provider = OpenRouterProvider()
        provider.api_key = "key"
        provider._client = MagicMock()
        response = MagicMock()
        response.json.return_value = {"data": [{"embedding": [0.5]}]}
        provider._client.post.return_value = response

        assert provider.create_embedding("model", "text") == [0.5]
        monkeypatch.setenv("EMBEDDING_MODEL", "default-model")
        provider.create_embedding("", "text")
        assert (
            provider._client.post.call_args.kwargs["json"]["model"] == "default-model"
        )

        response.raise_for_status.side_effect = RuntimeError("embedding down")
        assert provider.create_embedding("model", "text") == []


# ── Tool registry ──────────────────────────────────────────────


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
