"""Coverage for debate mode, entity extraction, realtime WS, and persistence."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from backend.agents.debate_agent import (
    DEBATE_MODEL,
    PERSPECTIVES,
    DebateResult,
    PerspectiveResponse,
    _build_judge_prompt,
    _build_perspective_prompt,
    _format_evidence,
    _push_log,
    run_debate,
)
from backend.agents.entity_extractor import (
    ExtractedEntity,
    ExtractionResult,
    _fallback_extract,
    extract_entities,
)
from fastapi import WebSocketDisconnect


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


# ── Debate mode ─────────────────────────────────────────────────


class FakeLLM:
    def __init__(self, responses=None, errors=None):
        self.responses = list(responses or [])
        self.errors = list(errors or [])
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.errors:
            raise self.errors.pop(0)
        if self.responses:
            return self.responses.pop(0)
        return "A considered argument."


class TestDebateMode:
    def test_run_debate_completes_all_perspectives_and_judge(self):
        llm = FakeLLM(responses=["Optimist view"] + ["View"] * 6 + ["Verdict"])
        with patch(
            "backend.agents.debate_agent.get_llm_provider_instance",
            return_value=llm,
        ):
            result = run_debate(
                "Does RAG help?",
                [{"title": "Paper", "snippet": "Evidence", "url": "https://x.test"}],
                [{"content": "Chunk text", "metadata": {"page_number": 3}}],
            )

        assert result.status == "completed"
        assert len(result.perspectives) == len(PERSPECTIVES)
        assert all(p.status == "completed" for p in result.perspectives)
        assert result.judge_verdict == "Verdict"
        assert result.errors == []
        assert llm.calls[-1]["system_prompt"].startswith("You are an impartial Judge")

    def test_run_debate_filters_perspectives(self):
        llm = FakeLLM(responses=["One", "Two", "Verdict"])
        with patch(
            "backend.agents.debate_agent.get_llm_provider_instance",
            return_value=llm,
        ):
            result = run_debate(
                "Question", [], [], perspective_ids=["optimist", "skeptic"]
            )
        assert [p.perspective_id for p in result.perspectives] == [
            "optimist",
            "skeptic",
        ]

    def test_run_debate_handles_empty_llm_output(self):
        llm = FakeLLM(responses=["   ", "  ", "  "])
        with patch(
            "backend.agents.debate_agent.get_llm_provider_instance",
            return_value=llm,
        ):
            result = run_debate("Question", [], [], perspective_ids=["optimist"])
        assert result.perspectives[0].argument == (
            "*Optimist perspective analysis unavailable.*"
        )
        assert result.judge_verdict == "*Judge synthesis unavailable.*"

    def test_run_debate_records_perspective_and_judge_failures(self):
        llm = FakeLLM(
            responses=[],
            errors=[RuntimeError("provider down"), RuntimeError("judge down")],
        )
        with patch(
            "backend.agents.debate_agent.get_llm_provider_instance",
            return_value=llm,
        ):
            result = run_debate("Question", [], [], perspective_ids=["optimist"])

        assert result.perspectives[0].status == "failed"
        assert "provider down" in result.perspectives[0].error
        assert any("Optimist" in error for error in result.errors)
        assert result.judge_verdict.startswith("*Judge synthesis encountered an error")
        assert any(error.startswith("Judge:") for error in result.errors)

    def test_push_log_with_and_without_stream(self):
        manager = MagicMock()
        with patch(
            "backend.agents.debate_agent.get_stream_manager",
            return_value=manager,
        ), patch("backend.agents.debate_agent.make_log", return_value={"log": 1}):
            _push_log("stream-1", "judge", "synthesize", "running", "details")
            manager.push_log.assert_called_once_with("stream-1", {"log": 1})

            manager.reset_mock()
            _push_log(None, "judge", "synthesize", "running")
            manager.push_log.assert_not_called()

    def test_format_evidence_variants(self):
        assert _format_evidence([], []) == "*No research evidence provided.*"

        web = _format_evidence(
            [
                {"title": "T", "snippet": "S", "url": "https://x.test"},
                {"title": "No URL", "snippet": "S2"},
            ],
            [],
        )
        assert "## Web Research Sources" in web
        assert "URL: https://x.test" in web
        assert "No URL" in web

        docs = _format_evidence(
            [],
            [
                {
                    "text": "fallback text",
                    "metadata": {"source_file": "paper.pdf", "page_number": 2},
                },
                {"content": "content", "metadata": {}},
            ],
        )
        assert "From: paper.pdf (Page 2)" in docs
        assert "fallback text" in docs
        assert "From: Document (Page N/A)" in docs

    def test_prompt_builders_include_context(self):
        perspective = PERSPECTIVES[0]
        prompt = _build_perspective_prompt("Q?", "Evidence", perspective)
        assert "Q?" in prompt
        assert perspective["instruction"] in prompt

        judge = _build_judge_prompt(
            "Q?",
            [
                PerspectiveResponse(
                    perspective_id="optimist",
                    label="Optimist",
                    emoji="🌟",
                    color="#fff",
                    argument="Argument",
                    latency_ms=1.0,
                    status="completed",
                )
            ],
        )
        assert "Optimist Analysis" in judge
        assert "Argument" in judge

    def test_debate_dataclass_defaults(self):
        result = DebateResult(query="q")
        assert result.perspectives == []
        assert result.status == "completed"
        assert DEBATE_MODEL


# ── Entity extraction ───────────────────────────────────────────


class TestEntityExtraction:
    def test_short_text_returns_empty(self):
        assert asyncio_run(extract_entities("short")).entities == []
        assert asyncio_run(extract_entities("   ")).entities == []

    def test_llm_json_extraction(self):
        payload = json.dumps(
            {
                "entities": [
                    {
                        "id": "rag",
                        "label": "RAG",
                        "type": "technology",
                        "description": "Retrieval",
                    }
                ],
                "relationships": [
                    {
                        "source": "rag",
                        "target": "llm",
                        "label": "uses",
                    }
                ],
            }
        )
        llm = MagicMock()
        llm.generate.return_value = f"Here you go:\n{payload}\nDone."
        with patch(
            "backend.agents.entity_extractor.get_llm_provider_instance",
            return_value=llm,
        ), patch(
            "backend.agents.entity_extractor.resolve_model",
            return_value="test-model",
        ):
            result = asyncio_run(
                extract_entities("A long enough research text about RAG and LLMs.")
            )

        assert result.entities[0].id == "rag"
        assert result.relationships[0].label == "uses"
        assert llm.generate.call_args.kwargs["model"] == "test-model"

    def test_llm_without_json_falls_back(self):
        llm = MagicMock()
        llm.generate.return_value = "No structured data here"
        with patch(
            "backend.agents.entity_extractor.get_llm_provider_instance",
            return_value=llm,
        ), patch(
            "backend.agents.entity_extractor.resolve_model",
            return_value="m",
        ):
            result = asyncio_run(
                extract_entities(
                    "LangGraph and OpenAI build retrieval augmented generation systems."
                )
            )
        assert any(e.label == "LangGraph" for e in result.entities)

    def test_llm_exception_falls_back(self):
        with patch(
            "backend.agents.entity_extractor.get_llm_provider_instance",
            side_effect=RuntimeError("no provider"),
        ):
            result = asyncio_run(
                extract_entities("LangGraph and OpenAI build retrieval systems.")
            )
        assert result.entities

    def test_fallback_extracts_entities_and_relationships(self):
        result = _fallback_extract(
            "OpenAI builds GPT models. Google uses Transformers and embeddings. "
            "Anthropic studies Attention and RAG."
        )
        labels = {entity.label for entity in result.entities}
        assert {"OpenAI", "Google", "Anthropic"} & labels
        assert result.relationships
        assert len(result.relationships) <= 8
        assert all(
            relationship.label == "related-to" for relationship in result.relationships
        )

    def test_fallback_deduplicates_entities(self):
        result = _fallback_extract("RAG rag RAG and more RAG with LLM LLM.")
        ids = [entity.id for entity in result.entities]
        assert len(ids) == len(set(ids))

    def test_extraction_models_validate(self):
        entity = ExtractedEntity(id="x", label="X", type="concept")
        assert entity.description is None
        assert ExtractionResult().entities == []


# ── Research persistence ────────────────────────────────────────


class TestResearchPersistence:
    @pytest.fixture
    def supabase(self):
        module = MagicMock()
        module.save_report.return_value = {"id": "report-1"}
        module.upload_report_file.return_value = "reports/report-1.md"
        with patch.dict("sys.modules", {"backend.core.supabase": module}):
            yield module

    def test_completed_run_persists_report_and_metrics(self, supabase):
        from backend.api.research_persistence import finalize_supabase_run

        finalize_supabase_run(
            session_id="session-1",
            user_id="user-1",
            query="A research query",
            execution_time=1.25,
            result={
                "status": "completed",
                "answer": "The answer",
                "sources": [{"url": "https://x.test"}],
                "token_count": 42,
                "metrics": {
                    "relevant_sources": 1,
                    "chunks": 3,
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "cost_estimate": 0.01,
                },
                "agent_metrics": {
                    "planner": {"status": "ok", "latency_ms": 10},
                    "search": {"status": "skipped"},
                    "answer": {"status": "failed", "latency": 0.5},
                    "ignored": {"tokens": 1},
                },
            },
        )

        supabase.update_session.assert_called_once()
        assert supabase.update_session.call_args.kwargs["sources_total"] == 1
        supabase.insert_message.assert_called_once_with(
            session_id="session-1", role="assistant", content="The answer"
        )
        supabase.save_run_metrics.assert_called_once()
        assert supabase.save_run_metrics.call_args.kwargs["execution_time_ms"] == 1250
        supabase.save_report.assert_called_once()
        supabase.upload_report_file.assert_called_once()
        supabase.set_report_storage_path.assert_called_once_with(
            "report-1", "reports/report-1.md"
        )
        supabase.log_activity.assert_called_once()
        assert supabase.upsert_agent_run.call_count == 3

    def test_failed_run_records_error_without_report(self, supabase):
        from backend.api.research_persistence import finalize_supabase_run

        finalize_supabase_run(
            session_id="session-2",
            user_id=None,
            query="Failure",
            execution_time=0.5,
            result={
                "status": "failed",
                "answer": "partial",
                "errors": ["boom", "again"],
                "sources": [],
            },
        )

        assert supabase.update_session.call_args.kwargs["error"] == "boom; again"
        supabase.save_report.assert_not_called()
        supabase.insert_message.assert_called_once()

    def test_empty_answer_skips_message(self, supabase):
        from backend.api.research_persistence import finalize_supabase_run

        finalize_supabase_run(
            session_id="s",
            user_id=None,
            query="q",
            execution_time=0.0,
            result={"status": "completed"},
        )
        supabase.insert_message.assert_not_called()
        supabase.save_report.assert_not_called()

    def test_upload_failure_marks_report_failed(self, supabase):
        from backend.api.research_persistence import finalize_supabase_run

        supabase.upload_report_file.side_effect = RuntimeError("storage down")
        finalize_supabase_run(
            session_id="s",
            user_id="u",
            query="q",
            execution_time=0.0,
            result={"status": "completed", "answer": "answer"},
        )
        supabase.set_report_status.assert_called_once_with("report-1", "failed")

    def test_upload_and_status_failure_are_suppressed(self, supabase):
        from backend.api.research_persistence import finalize_supabase_run

        supabase.upload_report_file.side_effect = RuntimeError("storage down")
        supabase.set_report_status.side_effect = RuntimeError("db down")
        finalize_supabase_run(
            session_id="s",
            user_id="u",
            query="q",
            execution_time=0.0,
            result={"status": "completed", "answer": "answer"},
        )

    def test_top_level_failure_is_suppressed(self, supabase):
        from backend.api.research_persistence import finalize_supabase_run

        supabase.update_session.side_effect = RuntimeError("supabase down")
        finalize_supabase_run(
            session_id="s",
            user_id=None,
            query="q",
            execution_time=0.0,
            result={"status": "completed"},
        )

    def test_storage_path_not_set_when_upload_returns_empty(self, supabase):
        from backend.api.research_persistence import finalize_supabase_run

        supabase.upload_report_file.return_value = ""
        finalize_supabase_run(
            session_id="s",
            user_id="u",
            query="q",
            execution_time=0.0,
            result={"status": "completed", "answer": "answer"},
        )
        supabase.set_report_storage_path.assert_not_called()


# ── Realtime WebSocket ──────────────────────────────────────────


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, *_args, **_kwargs):
        return _Result(self.results.pop(0))


class FakeWebSocket:
    def __init__(
        self,
        headers=None,
        query=None,
        messages=None,
        client_host="127.0.0.1",
    ):
        self.headers = headers or {}
        self.query_params = query or {}
        self.messages = list(messages or [])
        self.client = SimpleNamespace(host=client_host)
        self.accepted = False
        self.accept_subprotocol = None
        self.closed = []
        self.sent = []

    async def close(self, code=1000, reason=""):
        self.closed.append((code, reason))

    async def accept(self, subprotocol=None):
        self.accepted = True
        self.accept_subprotocol = subprotocol

    async def receive_text(self):
        if self.messages:
            item = self.messages.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        raise WebSocketDisconnect()

    async def send_text(self, text):
        self.sent.append(text)


class FakeRoom:
    def __init__(self, history=None):
        self.history = history or []
        self.connections = []
        self.messages = []

    def get_chat_history(self):
        return self.history

    def add(self, connection):
        self.connections.append(connection)

    async def handle_message(self, data, connection):
        self.messages.append((data, connection))


class FakeManager:
    def __init__(self, room):
        self.room = room
        self.broadcasts = []
        self.disconnects = []

    def get_or_create(self, workspace_id):
        self.workspace_id = workspace_id
        return self.room

    async def broadcast_presence(self, workspace_id):
        self.broadcasts.append(workspace_id)

    def disconnect(self, workspace_id, user_id):
        self.disconnects.append((workspace_id, user_id))


def _session_generator(session):
    async def generator():
        yield session

    return generator


class TestRealtimeWebSocket:
    def _run(self, ws, session, manager, limiter=None, token=None):
        from backend.api import realtime

        if token is None:
            from backend.auth.jwt import create_access_token

            token = create_access_token("user-1", {"name": "Alice"})

        if limiter is None:
            limiter = MagicMock()
            limiter.allow.return_value = True

        if "sec-websocket-protocol" not in ws.headers:
            ws.query_params = {**ws.query_params, "token": token}

        with patch.object(
            realtime, "get_session", _session_generator(session)
        ), patch.object(
            realtime, "get_workspace_manager", return_value=manager
        ), patch.object(
            realtime, "ws_limiter", limiter
        ):
            asyncio_run(realtime.workspace_ws("ws-1", ws))

    def test_rejects_disallowed_origin(self):
        ws = FakeWebSocket(headers={"origin": "https://evil.test"})
        self._run(ws, FakeSession([]), FakeManager(FakeRoom()))
        assert ws.closed == [(1008, "Origin not allowed")]

    def test_rejects_rate_limited_connection(self):
        limiter = MagicMock()
        limiter.allow.return_value = False
        ws = FakeWebSocket()
        self._run(ws, FakeSession([]), FakeManager(FakeRoom()), limiter=limiter)
        assert ws.closed == [(1008, "Rate limit exceeded")]

    def test_rejects_missing_token(self):
        ws = FakeWebSocket(query={"user_id": "user-1"})
        self._run(ws, FakeSession([]), FakeManager(FakeRoom()), token="")
        assert ws.closed == [(4001, "Authentication required")]

    def test_rejects_access_token_of_wrong_type(self):
        from backend.auth.jwt import create_refresh_token

        ws = FakeWebSocket()
        self._run(
            ws,
            FakeSession([]),
            FakeManager(FakeRoom()),
            token=create_refresh_token("user-1"),
        )
        assert ws.closed == [(4001, "Authentication required")]

    def test_rejects_user_id_mismatch(self):
        from backend.auth.jwt import create_access_token

        ws = FakeWebSocket(query={"user_id": "someone-else"})
        self._run(
            ws,
            FakeSession([]),
            FakeManager(FakeRoom()),
            token=create_access_token("user-1"),
        )
        assert ws.closed == [(4001, "User ID mismatch")]

    def test_rejects_missing_workspace(self):
        ws = FakeWebSocket()
        self._run(ws, FakeSession([None]), FakeManager(FakeRoom()))
        assert ws.closed == [(4004, "Workspace not found")]

    def test_rejects_missing_user(self):
        workspace = SimpleNamespace(id="ws-1", is_active=True)
        ws = FakeWebSocket()
        self._run(ws, FakeSession([workspace, None]), FakeManager(FakeRoom()))
        assert ws.closed == [(4001, "User not found")]

    def test_rejects_non_member(self):
        workspace = SimpleNamespace(id="ws-1", is_active=True)
        user = SimpleNamespace(id="user-1", is_active=True, is_superuser=False)
        ws = FakeWebSocket()
        self._run(ws, FakeSession([workspace, user, None]), FakeManager(FakeRoom()))
        assert ws.closed == [(4003, "Not a member of this workspace")]

    def test_superuser_joins_without_membership(self):
        workspace = SimpleNamespace(id="ws-1", is_active=True)
        user = SimpleNamespace(id="user-1", is_active=True, is_superuser=True)
        room = FakeRoom()
        manager = FakeManager(room)
        ws = FakeWebSocket(messages=[WebSocketDisconnect()])
        self._run(ws, FakeSession([workspace, user]), manager)

        assert ws.accepted is True
        assert ws.accept_subprotocol == "research-swarm"
        assert len(room.connections) == 1
        assert manager.disconnects == [("ws-1", "user-1")]

    def test_member_receives_history_and_messages(self):
        workspace = SimpleNamespace(id="ws-1", is_active=True)
        user = SimpleNamespace(id="user-1", is_active=True, is_superuser=False)
        member = SimpleNamespace(id="member-1")
        room = FakeRoom(history=[{"role": "user", "content": "hello"}])
        manager = FakeManager(room)
        ws = FakeWebSocket(messages=['{"type":"ping"}', WebSocketDisconnect()])

        self._run(ws, FakeSession([workspace, user, member]), manager)

        assert json.loads(ws.sent[0])["type"] == "chat:history"
        assert room.messages[0][0] == '{"type":"ping"}'
        assert manager.broadcasts == ["ws-1", "ws-1"]

    def test_token_from_websocket_subprotocol(self):
        from backend.auth.jwt import create_access_token

        workspace = SimpleNamespace(id="ws-1", is_active=True)
        user = SimpleNamespace(id="user-1", is_active=True, is_superuser=True)
        token = create_access_token("user-1")
        ws = FakeWebSocket(
            headers={"sec-websocket-protocol": f"research-swarm, {token}"},
            messages=[WebSocketDisconnect()],
        )
        self._run(
            ws,
            FakeSession([workspace, user]),
            FakeManager(FakeRoom()),
            token="unused",
        )
        assert ws.accepted is True
