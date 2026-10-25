"""Coverage for conversation memory, graph nodes, and plugin/provider routes."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.agents import graph as graph_module
from backend.agents import memory as memory_module
from backend.agents.memory import (
    Conversation,
    ConversationMemory,
    get_memory,
)
from backend.api import plugins as plugins_api
from backend.api.plugins import (
    configure_plugin,
    create_provider,
    delete_provider,
    execute_plugin,
    get_provider,
    list_plugins,
    list_provider_types,
    list_providers,
    update_provider,
)
from backend.auth.tenant import TenantContext, _resolve_permissions
from backend.db.models import Provider, User
from backend.db.schemas import (
    PluginConfigRequest,
    ProviderCreate,
    ProviderUpdate,
)


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


NOW = datetime.now(timezone.utc)


def _user():
    return User(
        id="user-1",
        email="user@example.com",
        name="User",
        is_active=True,
        mfa_enabled=False,
        created_at=NOW,
        updated_at=NOW,
    )


def _ctx():
    return TenantContext(
        organization_id="org-1",
        organization_slug="org",
        user_id="user-1",
        user_role="owner",
        permissions=_resolve_permissions("owner"),
    )


# ── Conversation memory ────────────────────────────────────────


@pytest.fixture
def memory(tmp_path):
    ConversationMemory._semantic_client = None
    ConversationMemory._semantic_collection = None
    return ConversationMemory(str(tmp_path))


class TestConversationMemoryFiles:
    def test_create_add_and_get_history(self, memory):
        conversation_id = memory.create_conversation({"topic": "RAG"})
        assert memory.get_history(conversation_id) == []
        assert memory.get_history("missing") == []

        memory.add_turn(conversation_id, "user", "hello")
        memory.add_turn(conversation_id, "assistant", "world")
        memory.add_turn(conversation_id, "user", "third")

        assert memory.get_history(conversation_id, max_turns=2) == [
            {"role": "assistant", "content": "world"},
            {"role": "user", "content": "third"},
        ]

        conversation = memory.get_conversation(conversation_id)
        assert conversation.metadata == {"topic": "RAG"}
        assert len(conversation.turns) == 3
        assert memory.get_conversation("missing") is None

    def test_add_turn_creates_unknown_conversation(self, memory):
        memory.add_turn("brand-new", "user", "short")
        assert memory.get_conversation("brand-new").turns[0].content == "short"

    def test_list_and_delete_conversations(self, memory):
        first = memory.create_conversation()
        memory.add_turn(first, "user", "first query")
        second = memory.create_conversation()

        empty_path = memory.memory_dir / "empty.json"
        empty_path.write_text(json.dumps({"conversation_id": "empty", "turns": []}))
        (memory.memory_dir / "broken.json").write_text("{not-json")

        conversations = memory.list_conversations()
        assert len(conversations) == 3
        by_id = {item["conversation_id"]: item for item in conversations}
        assert by_id[first]["first_query"] == "first query"
        assert by_id["empty"]["first_query"] == ""
        assert by_id[second]["turn_count"] == 0

        assert memory.delete_conversation(first) is True
        assert memory.delete_conversation("never-existed") is True
        assert memory.get_conversation(first) is None

    def test_persist_and_load_failures_are_suppressed(self, memory, tmp_path):
        conversation = Conversation(conversation_id="broken-write")
        broken_dir = tmp_path / "gone"
        broken_memory = ConversationMemory(str(broken_dir))
        broken_dir.rmdir()
        broken_memory._persist(conversation)
        assert broken_memory.get_conversation("broken-write") is None

        (memory.memory_dir / "bad.json").write_text("{not-json")
        assert memory._load("bad") is None

    def test_semantic_retrieval_disabled_without_dependencies(
        self, memory, monkeypatch
    ):
        monkeypatch.setattr(memory_module, "has_chromadb", False)
        monkeypatch.setattr(memory_module, "has_httpx", True)
        assert memory.retrieve_semantic("query") == []

        monkeypatch.setattr(memory_module, "has_chromadb", True)
        monkeypatch.setattr(memory_module, "has_httpx", False)
        assert memory.retrieve_semantic("query") == []

    def test_semantic_retrieval_branches(self, memory, monkeypatch):
        monkeypatch.setattr(memory_module, "has_chromadb", True)
        monkeypatch.setattr(memory_module, "has_httpx", True)
        with patch.object(memory, "_ensure_semantic_collection", return_value=None):
            assert memory.retrieve_semantic("query") == []

        collection = MagicMock()
        with patch.object(
            memory, "_ensure_semantic_collection", return_value=collection
        ), patch.object(memory, "_create_embedding", return_value=None):
            assert memory.retrieve_semantic("query") == []

        collection.query.return_value = {
            "documents": [["memory one", "memory two"]],
            "metadatas": [
                [
                    {
                        "role": "user",
                        "conversation_id": "conv",
                        "timestamp": 123,
                    },
                    {},
                ]
            ],
            "distances": [[0.2, 0.6]],
        }
        with patch.object(
            memory, "_ensure_semantic_collection", return_value=collection
        ), patch.object(memory, "_create_embedding", return_value=[0.1]):
            results = memory.retrieve_semantic("query", top_k=2)

        assert results[0] == {
            "content": "memory one",
            "role": "user",
            "conversation_id": "conv",
            "similarity": 0.8,
            "timestamp": 123,
        }
        assert results[1]["role"] == "unknown"
        assert results[1]["similarity"] == 0.4

        collection.query.return_value = {
            "documents": [["memory one"]],
            "metadatas": [[{}]],
        }
        with patch.object(
            memory, "_ensure_semantic_collection", return_value=collection
        ), patch.object(memory, "_create_embedding", return_value=[0.1]):
            assert memory.retrieve_semantic("query")[0]["similarity"] == 1.0

        collection.query.return_value = {}
        with patch.object(
            memory, "_ensure_semantic_collection", return_value=collection
        ), patch.object(memory, "_create_embedding", return_value=[0.1]):
            assert memory.retrieve_semantic("query") == []

        collection.query.side_effect = RuntimeError("chroma down")
        with patch.object(
            memory, "_ensure_semantic_collection", return_value=collection
        ), patch.object(memory, "_create_embedding", return_value=[0.1]):
            assert memory.retrieve_semantic("query") == []

    def test_ensure_semantic_collection_cache_and_errors(self, memory, monkeypatch):
        monkeypatch.setattr(memory_module, "has_chromadb", False)
        assert memory._ensure_semantic_collection() is None

        monkeypatch.setattr(memory_module, "has_chromadb", True)
        sentinel = object()
        ConversationMemory._semantic_collection = sentinel
        assert memory._ensure_semantic_collection() is sentinel

        ConversationMemory._semantic_collection = None
        ConversationMemory._semantic_client = None
        collection = object()
        fake_chromadb = MagicMock()
        fake_chromadb.PersistentClient.return_value.get_or_create_collection.return_value = (
            collection
        )
        with patch.object(memory_module, "chromadb", fake_chromadb), patch.object(
            memory_module, "Settings", create=True
        ):
            assert memory._ensure_semantic_collection() is collection
            assert memory._ensure_semantic_collection() is collection
        fake_chromadb.PersistentClient.assert_called_once()

        ConversationMemory._semantic_collection = None
        ConversationMemory._semantic_client = None
        fake_chromadb.PersistentClient.side_effect = RuntimeError("cannot open")
        with patch.object(memory_module, "chromadb", fake_chromadb), patch.object(
            memory_module, "Settings", create=True
        ):
            assert memory._ensure_semantic_collection() is None

    def test_create_embedding_paths(self, memory, monkeypatch):
        monkeypatch.setattr(memory_module, "has_httpx", False)
        assert ConversationMemory._create_embedding("text") is None

        monkeypatch.setattr(memory_module, "has_httpx", True)
        response = MagicMock()
        response.json.return_value = {"embedding": [0.1]}
        client = MagicMock()
        client.post.return_value = response
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        with patch.object(
            memory_module.httpx, "Client", return_value=client
        ) as client_cls:
            assert ConversationMemory._create_embedding("text" * 2000) == [0.1]
        client_cls.assert_called_once()
        assert client.post.call_args.kwargs["json"]["truncate"] is True

        response.error = RuntimeError("ollama down")
        response.raise_for_status = MagicMock(side_effect=RuntimeError("down"))
        with patch.object(memory_module.httpx, "Client", return_value=client):
            assert ConversationMemory._create_embedding("text") is None

    def test_store_semantic_memory_branches(self, memory):
        memory._store_semantic_memory("conv", "user", "short")
        memory._store_semantic_memory("conv", "user", "")

        with patch.object(memory, "_create_embedding", return_value=None):
            memory._store_semantic_memory("conv", "user", "long enough content here")

        with patch.object(
            memory, "_create_embedding", return_value=[0.1]
        ), patch.object(memory, "_ensure_semantic_collection", return_value=None):
            memory._store_semantic_memory("conv", "user", "long enough content here")

        collection = MagicMock()
        with patch.object(
            memory, "_create_embedding", return_value=[0.1]
        ), patch.object(memory, "_ensure_semantic_collection", return_value=collection):
            memory._store_semantic_memory("conv", "user", "long enough content here")
            assert collection.add.call_args.kwargs["metadatas"][0]["source"] == "chat"

            memory._store_semantic_memory(
                "conv",
                "user",
                "another long enough content",
                {"source": "document"},
            )
            assert (
                collection.add.call_args.kwargs["metadatas"][0]["source"] == "document"
            )

        collection.add.side_effect = RuntimeError("write failed")
        with patch.object(
            memory, "_create_embedding", return_value=[0.1]
        ), patch.object(memory, "_ensure_semantic_collection", return_value=collection):
            memory._store_semantic_memory("conv", "user", "long enough content here")

    def test_memory_singleton(self):
        with patch.object(memory_module, "_memory", None):
            first = get_memory()
            assert first is get_memory()


# ── Graph nodes and routing ────────────────────────────────────


def _state(**overrides):
    state = {
        "query": "What is RAG?",
        "conversation_id": None,
        "plan": [],
        "plan_reasoning": None,
        "web_results": [],
        "document_chunks": [],
        "answer": None,
        "sources": [],
        "errors": [],
        "status": "running",
        "logs": [],
        "pdf_paths": [],
        "execution_start": time.time(),
        "agent_metrics": {},
        "stream_task_id": None,
    }
    state.update(overrides)
    return state


class TestGraphHelpers:
    def test_add_log_pushes_to_stream(self):
        manager = MagicMock()
        state = _state(stream_task_id="task-1")
        with patch.object(graph_module, "get_stream_manager", return_value=manager):
            graph_module._add_log(state, "agent", "action", "completed", "details")
        assert state["logs"][0]["details"] == "details"
        manager.push_log.assert_called_once()

        without_stream = _state()
        graph_module._add_log(without_stream, "agent", "action", "completed")

    def test_apply_state_overrides(self):
        state = _state(
            llm_provider="openrouter",
            planner_model="p",
            research_model="r",
            document_model="d",
            answer_model="a",
        )
        with patch.object(
            graph_module, "apply_provider_overrides", return_value="backup"
        ) as apply:
            assert graph_module._apply_state_overrides(state) == "backup"
        apply.assert_called_once_with(
            llm_provider="openrouter",
            planner_model="p",
            research_model="r",
            document_model="d",
            answer_model="a",
        )

    def test_routing_after_planning_and_research(self):
        assert (
            graph_module._route_after_planning(
                _state(plan=[{"agent": "research_agent"}, {"agent": "document_agent"}])
            )
            == "research_agent"
        )
        assert (
            graph_module._route_after_planning(
                _state(plan=[{"agent": "document_agent"}])
            )
            == "document_agent"
        )
        assert (
            graph_module._route_after_planning(_state(pdf_paths=["a.pdf"]))
            == "document_agent"
        )
        assert graph_module._route_after_planning(_state()) == "answer_agent"

        assert (
            graph_module._route_after_research(
                _state(plan=[{"agent": "document_agent"}])
            )
            == "document_agent"
        )
        assert (
            graph_module._route_after_research(_state(pdf_paths=["a.pdf"]))
            == "document_agent"
        )
        assert graph_module._route_after_research(_state()) == "merge"

    def test_route_after_merge(self):
        assert (
            graph_module._route_after_merge(_state(web_results=[{"x": 1}]))
            == "answer_agent"
        )
        assert (
            graph_module._route_after_merge(_state(plan=[{"agent": "x"}]))
            == "answer_agent"
        )
        assert graph_module._route_after_merge(_state()) == graph_module.END


class TestGraphNodes:
    def test_research_node_failure(self):
        with patch.object(
            graph_module.WebResearchAgent,
            "run",
            side_effect=RuntimeError("search down"),
        ), patch.object(graph_module, "restore_provider_overrides"):
            result = graph_module._run_research_node(_state())
        assert result["web_results"] == []
        assert result["agent_metrics"]["research_agent"]["status"] == "error"
        assert "search down" in result["errors"][0]

    def test_document_node_without_pdfs(self):
        with patch.object(graph_module, "resolve_model", return_value="m"):
            result = graph_module._run_document_node(_state())
        assert result["document_chunks"] == []
        assert result["agent_metrics"]["document_agent"]["status"] == "skipped"

    def test_document_node_success(self):
        agent = MagicMock()
        agent.retrieve.return_value = [{"content": "chunk"}]
        with patch.object(
            graph_module, "DocumentAgent", return_value=agent
        ), patch.object(graph_module, "resolve_model", return_value="m"), patch.object(
            graph_module, "restore_provider_overrides"
        ):
            result = graph_module._run_document_node(
                _state(pdf_paths=["one.pdf", "two.pdf"])
            )

        assert agent.ingest_pdf.call_count == 2
        assert result["document_chunks"] == [{"content": "chunk"}]
        assert result["agent_metrics"]["document_agent"]["pdfs_processed"] == 2

    def test_document_node_failure(self):
        agent = MagicMock()
        agent.ingest_pdf.side_effect = RuntimeError("parse failed")
        with patch.object(
            graph_module, "DocumentAgent", return_value=agent
        ), patch.object(graph_module, "resolve_model", return_value="m"), patch.object(
            graph_module, "restore_provider_overrides"
        ):
            result = graph_module._run_document_node(_state(pdf_paths=["one.pdf"]))

        assert result["document_chunks"] == []
        assert result["agent_metrics"]["document_agent"]["status"] == "error"
        assert "parse failed" in result["errors"][0]

    def test_answer_node_success(self):
        source = SimpleNamespace(model_dump=lambda: {"title": "Source"})
        response = SimpleNamespace(
            answer="Answer",
            sources=[source],
            mode="normal",
            evidence_summary={"source_count": 1},
        )
        agent = MagicMock()
        agent.generate.return_value = response
        with patch.object(
            graph_module, "AnswerAgent", return_value=agent
        ), patch.object(graph_module, "resolve_model", return_value="m"), patch.object(
            graph_module, "restore_provider_overrides"
        ):
            result = graph_module._run_answer_node(_state())

        assert result["answer"] == "Answer"
        assert result["sources"] == [{"title": "Source"}]
        assert result["status"] == "completed"
        assert result["has_evidence"] is True
        assert result["agent_metrics"]["answer_agent"]["source_count"] == 1

    def test_answer_node_debate_success(self):
        response = SimpleNamespace(
            answer="Answer", sources=[], mode="normal", evidence_summary=None
        )
        agent = MagicMock()
        agent.generate.return_value = response
        perspective = SimpleNamespace(
            perspective_id="optimist",
            label="Optimist",
            emoji="*",
            color="#fff",
            argument="Argument",
            latency_ms=1.0,
            status="completed",
        )
        debate = SimpleNamespace(
            query="Q",
            perspectives=[perspective],
            judge_verdict="Verdict",
            judge_latency_ms=2.0,
            status="completed",
            errors=[],
        )
        with patch.object(
            graph_module, "AnswerAgent", return_value=agent
        ), patch.object(graph_module, "resolve_model", return_value="m"), patch.object(
            graph_module, "restore_provider_overrides"
        ), patch(
            "backend.agents.debate_agent.run_debate", return_value=debate
        ):
            result = graph_module._run_answer_node(_state(debate_mode=True))

        assert result["debate_result"]["judge_verdict"] == "Verdict"
        assert (
            result["debate_result"]["perspectives"][0]["perspective_id"] == "optimist"
        )

    def test_answer_node_debate_failure(self):
        response = SimpleNamespace(
            answer="Answer", sources=[], mode="normal", evidence_summary=None
        )
        agent = MagicMock()
        agent.generate.return_value = response
        with patch.object(
            graph_module, "AnswerAgent", return_value=agent
        ), patch.object(graph_module, "resolve_model", return_value="m"), patch.object(
            graph_module, "restore_provider_overrides"
        ), patch(
            "backend.agents.debate_agent.run_debate",
            side_effect=RuntimeError("debate down"),
        ):
            result = graph_module._run_answer_node(_state(debate_mode=True))

        assert result["debate_result"] == {
            "status": "failed",
            "errors": ["debate down"],
            "perspectives": [],
            "judge_verdict": None,
        }

    def test_answer_node_failure(self):
        agent = MagicMock()
        agent.generate.side_effect = RuntimeError("llm down")
        with patch.object(
            graph_module, "AnswerAgent", return_value=agent
        ), patch.object(graph_module, "resolve_model", return_value="m"), patch.object(
            graph_module, "restore_provider_overrides"
        ):
            result = graph_module._run_answer_node(_state())

        assert result["status"] == "failed"
        assert result["answer"] == "**Error generating answer:** llm down"
        assert "llm down" in result["errors"][0]

    def test_graph_singleton(self):
        graph_module.reset_graph()
        sentinel = object()
        with patch.object(
            graph_module, "create_research_graph", return_value=sentinel
        ) as create:
            assert graph_module.get_graph() is sentinel
            assert graph_module.get_graph() is sentinel
        create.assert_called_once()
        graph_module.reset_graph()


# ── Plugin and provider API routes ────────────────────────────


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class Session:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []
        self.deleted = []
        self.commits = 0

    async def execute(self, *_args, **_kwargs):
        return Result(self.results.pop(0) if self.results else None)

    def add(self, item):
        self.added.append(item)

    async def delete(self, item):
        self.deleted.append(item)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _item):
        return None


def _provider(**overrides):
    values = {
        "id": "provider-1",
        "name": "Provider",
        "provider_type": "llm",
        "provider_key": "openrouter",
        "config": {"api_key": "x"},
        "is_active": True,
        "organization_id": "org-1",
        "created_by": "user-1",
    }
    values.update(overrides)
    return Provider(**values)


class TestPluginRoutes:
    def _registry(self, plugin=None):
        registry = MagicMock()
        registry.get.return_value = plugin
        return registry

    def test_list_plugins(self):
        registry = MagicMock()
        registry.list_plugins.return_value = [
            SimpleNamespace(name="weather", tags=["forecast"]),
            SimpleNamespace(name="search", tags=[]),
        ]
        registry.is_configured.side_effect = [True, False]
        with patch.object(plugins_api, "_registry", return_value=registry):
            result = asyncio_run(list_plugins())

        assert [item.name for item in result] == ["weather", "search"]
        assert result[0].configured is True
        assert result[0].actions == ["forecast"]

    def test_configure_plugin_rejects_unknown_plugin_and_keys(self):
        with patch.object(plugins_api, "_registry", return_value=self._registry()):
            with pytest.raises(HTTPException) as missing:
                asyncio_run(
                    configure_plugin(
                        "missing",
                        PluginConfigRequest(name="missing", config={}),
                        current_user=_user(),
                        ctx=_ctx(),
                    )
                )
        assert missing.value.status_code == 404

        plugin = SimpleNamespace(
            spec=SimpleNamespace(config_schema={"api_key": {"type": "string"}}),
            _config={},
        )
        with patch.object(
            plugins_api, "_registry", return_value=self._registry(plugin)
        ):
            with pytest.raises(HTTPException) as invalid:
                asyncio_run(
                    configure_plugin(
                        "weather",
                        PluginConfigRequest(
                            name="weather", config={"api_key": "x", "extra": 1}
                        ),
                        current_user=_user(),
                        ctx=_ctx(),
                    )
                )
        assert invalid.value.status_code == 422
        assert "extra" in invalid.value.detail

    def test_configure_plugin_success_and_plugin_without_config(self):
        plugin = SimpleNamespace(
            spec=SimpleNamespace(config_schema={"api_key": {"type": "string"}}),
            _config={},
        )
        with patch.object(
            plugins_api, "_registry", return_value=self._registry(plugin)
        ):
            result = asyncio_run(
                configure_plugin(
                    "weather",
                    PluginConfigRequest(name="weather", config={"api_key": "x"}),
                    current_user=_user(),
                    ctx=_ctx(),
                )
            )
        assert result == {"status": "configured", "name": "weather"}
        assert plugin._config == {"api_key": "x"}

        no_config = SimpleNamespace(
            spec=SimpleNamespace(config_schema={}), is_configured=lambda: True
        )
        with patch.object(
            plugins_api, "_registry", return_value=self._registry(no_config)
        ):
            assert asyncio_run(
                configure_plugin(
                    "plain",
                    PluginConfigRequest(name="plain", config={"anything": 1}),
                    current_user=_user(),
                    ctx=_ctx(),
                )
            ) == {"status": "configured", "name": "plain"}

    def test_execute_plugin_validation(self):
        with patch.object(plugins_api, "_registry", return_value=self._registry()):
            with pytest.raises(HTTPException) as missing:
                asyncio_run(
                    execute_plugin(
                        "missing",
                        action="run",
                        current_user=_user(),
                        ctx=_ctx(),
                    )
                )
        assert missing.value.status_code == 404

        plugin = SimpleNamespace(
            spec=SimpleNamespace(tags=["forecast"]), is_configured=lambda: True
        )
        with patch.object(
            plugins_api, "_registry", return_value=self._registry(plugin)
        ):
            with pytest.raises(HTTPException) as invalid:
                asyncio_run(
                    execute_plugin(
                        "weather",
                        action="storm",
                        current_user=_user(),
                        ctx=_ctx(),
                    )
                )
        assert invalid.value.status_code == 400

        unconfigured = SimpleNamespace(
            spec=SimpleNamespace(tags=[]), is_configured=lambda: False
        )
        with patch.object(
            plugins_api, "_registry", return_value=self._registry(unconfigured)
        ):
            with pytest.raises(HTTPException) as not_configured:
                asyncio_run(
                    execute_plugin(
                        "weather",
                        action="forecast",
                        current_user=_user(),
                        ctx=_ctx(),
                    )
                )
        assert not_configured.value.status_code == 400

    def test_execute_plugin_success_without_and_with_json_body(self):
        plugin = SimpleNamespace(
            spec=SimpleNamespace(tags=["forecast"]), is_configured=lambda: True
        )
        registry = self._registry(plugin)
        registry.execute = AsyncMock(return_value={"temp": 20})

        with patch.object(plugins_api, "_registry", return_value=registry):
            result = asyncio_run(
                execute_plugin(
                    "weather",
                    action="forecast",
                    current_user=_user(),
                    ctx=_ctx(),
                    request=None,
                )
            )
        assert result == {
            "status": "ok",
            "name": "weather",
            "action": "forecast",
            "result": {"temp": 20},
        }
        registry.execute.assert_awaited_with("weather", "forecast")

        request = SimpleNamespace(
            headers={"content-type": "application/json"},
            json=AsyncMock(return_value={"city": "Paris"}),
        )
        with patch.object(plugins_api, "_registry", return_value=registry):
            asyncio_run(
                execute_plugin(
                    "weather",
                    action="forecast",
                    current_user=_user(),
                    ctx=_ctx(),
                    request=request,
                )
            )
        registry.execute.assert_awaited_with("weather", "forecast", city="Paris")

    def test_execute_plugin_error_mapping(self):
        plugin = SimpleNamespace(
            spec=SimpleNamespace(tags=[]), is_configured=lambda: True
        )
        registry = self._registry(plugin)
        registry.execute = AsyncMock(side_effect=KeyError("missing"))

        with patch.object(plugins_api, "_registry", return_value=registry):
            with pytest.raises(HTTPException) as missing:
                asyncio_run(
                    execute_plugin(
                        "weather",
                        action="forecast",
                        current_user=_user(),
                        ctx=_ctx(),
                    )
                )
        assert missing.value.status_code == 404

        registry.execute = AsyncMock(side_effect=RuntimeError("execution failed"))
        with patch.object(plugins_api, "_registry", return_value=registry):
            with pytest.raises(HTTPException) as failed:
                asyncio_run(
                    execute_plugin(
                        "weather",
                        action="forecast",
                        current_user=_user(),
                        ctx=_ctx(),
                    )
                )
        assert failed.value.status_code == 400
        assert failed.value.detail == "execution failed"

    def test_provider_listing(self):
        registry = MagicMock()
        registry.list_all.return_value = {"llm": {"openrouter": {"configured": True}}}
        with patch.object(plugins_api, "_registry", return_value=registry):
            listed = asyncio_run(list_providers())
            types = asyncio_run(list_provider_types())

        assert listed.builtin == {"llm": {"openrouter": {"configured": True}}}
        assert listed.custom == []
        assert types == {"llm": {"openrouter": {"configured": True}}}


class TestProviderRoutes:
    def test_create_provider_conflict_and_success(self):
        body = ProviderCreate(
            name="Provider",
            provider_type="llm",
            provider_key="openrouter",
            config={"api_key": "x"},
        )
        with pytest.raises(HTTPException) as conflict:
            asyncio_run(
                create_provider(
                    body,
                    current_user=_user(),
                    session=Session(_provider()),
                    ctx=_ctx(),
                )
            )
        assert conflict.value.status_code == 409

        session = Session(None)
        provider = asyncio_run(
            create_provider(body, current_user=_user(), session=session, ctx=_ctx())
        )
        assert provider.name == "Provider"
        assert session.added[0].organization_id == "org-1"
        assert session.commits == 1

    def test_get_provider_found_and_missing(self):
        assert (
            asyncio_run(
                get_provider("provider-1", session=Session(_provider()), ctx=_ctx())
            ).id
            == "provider-1"
        )
        with pytest.raises(HTTPException) as missing:
            asyncio_run(get_provider("missing", session=Session(None), ctx=_ctx()))
        assert missing.value.status_code == 404

    def test_update_provider_fields_and_missing(self):
        provider = _provider()
        updated = asyncio_run(
            update_provider(
                "provider-1",
                ProviderUpdate(
                    name="Renamed", config={"api_key": "y"}, is_active=False
                ),
                session=Session(provider),
                ctx=_ctx(),
            )
        )
        assert updated.name == "Renamed"
        assert updated.config == {"api_key": "y"}
        assert updated.is_active is False

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                update_provider(
                    "missing",
                    ProviderUpdate(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )
        assert missing.value.status_code == 404

    def test_delete_provider_success_and_missing(self):
        provider = _provider()
        session = Session(provider)
        assert asyncio_run(
            delete_provider("provider-1", session=session, ctx=_ctx())
        ) == {"status": "deleted"}
        assert session.deleted == [provider]

        with pytest.raises(HTTPException) as missing:
            asyncio_run(delete_provider("missing", session=Session(None), ctx=_ctx()))
        assert missing.value.status_code == 404
