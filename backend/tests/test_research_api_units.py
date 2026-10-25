"""Direct-route coverage for research execution, streaming, and cancellation."""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from backend.api import research as research_api
from backend.api.stream import StreamManager
from backend.auth.tenant import TenantContext, _resolve_permissions
from backend.core.ratelimit import limiter
from backend.db.models import User
from backend.db.schemas import ExtractEntitiesRequest, ResearchRequest


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


def _user(user_id="user-1"):
    return User(
        id=user_id,
        email=f"{user_id}@example.com",
        name="User",
        is_active=True,
        mfa_enabled=False,
    )


def _ctx():
    return TenantContext(
        organization_id="org-1",
        organization_slug="org",
        user_id="user-1",
        user_role="owner",
        permissions=_resolve_permissions("owner"),
    )


class FakeTask:
    def __init__(self, done=False):
        self._done = done
        self.cancelled = False

    def done(self):
        return self._done

    def cancel(self):
        self.cancelled = True


class FakeStreamManager:
    def __init__(self):
        self.owners = {}
        self.tasks = {}
        self.logs = []
        self.closed = []
        self.registered = []
        self.unregistered = []
        self.persisted = []

    def get_owner(self, task_id):
        return self.owners.get(task_id)

    def get_task(self, task_id):
        return self.tasks.get(task_id)

    def has_stream(self, task_id):
        return task_id in self.owners or task_id in self.tasks

    def get_stream(self, task_id):
        return "adapter"

    def get_or_create_stream(self, task_id, owner_user_id=None):
        self.owners[task_id] = owner_user_id
        return "adapter"

    def attach_persistence(self, task_id, **kwargs):
        self.persisted.append((task_id, kwargs))

    def push_log(self, task_id, log):
        self.logs.append((task_id, log))

    def register_task(self, task_id, task):
        self.tasks[task_id] = task
        self.registered.append(task_id)

    def unregister_task(self, task_id, task):
        self.unregistered.append(task_id)

    def close_stream(self, task_id):
        self.closed.append(task_id)


def _request(stream_manager=None, graph=None):
    app = SimpleNamespace(
        state=SimpleNamespace(
            graph=graph or MagicMock(),
            stream_manager=stream_manager or FakeStreamManager(),
        )
    )
    return SimpleNamespace(app=app)


def _tracer():
    tracer = MagicMock()
    tracer.start_trace.return_value = "trace"
    span = MagicMock()
    span.__enter__ = MagicMock(return_value="span")
    span.__exit__ = MagicMock(return_value=False)
    tracer.span.return_value = span
    return tracer


class TestNormalizeRunStatus:
    def test_terminal_statuses_pass_through(self):
        assert (
            research_api._normalize_run_status({"status": "completed"}) == "completed"
        )
        assert research_api._normalize_run_status({"status": "failed"}) == "failed"
        assert (
            research_api._normalize_run_status({"status": "cancelled"}) == "cancelled"
        )

    def test_missing_status_is_marked_failed(self):
        result = {}
        assert research_api._normalize_run_status(result) == "failed"
        assert result["status"] == "failed"
        assert "terminal status" in result["errors"][0]

        again = {"status": "running", "errors": [result["errors"][0]]}
        assert research_api._normalize_run_status(again) == "failed"
        assert len(again["errors"]) == 1

        assert research_api._normalize_run_status(None) == "failed"
        assert research_api._normalize_run_status("not-a-dict") == "failed"


class TestCancelAndSubscribe:
    def test_cancel_rejects_non_owner(self):
        manager = FakeStreamManager()
        manager.owners["task-1"] = "someone-else"
        with patch.object(research_api, "ensure_app_state"):
            with pytest.raises(HTTPException) as denied:
                asyncio_run(
                    research_api.cancel_research_task(
                        "task-1", _request(manager), current_user=_user()
                    )
                )
        assert denied.value.status_code == 403

    def test_cancel_handles_missing_and_finished_tasks(self):
        manager = FakeStreamManager()
        manager.owners["task-1"] = "user-1"
        with patch.object(research_api, "ensure_app_state"):
            missing = asyncio_run(
                research_api.cancel_research_task(
                    "task-1", _request(manager), current_user=_user()
                )
            )
            assert missing == {
                "status": "cancelled",
                "task_id": "task-1",
                "already_done": True,
            }

            manager.tasks["task-1"] = FakeTask(done=True)
            finished = asyncio_run(
                research_api.cancel_research_task(
                    "task-1", _request(manager), current_user=_user()
                )
            )
            assert finished["already_done"] is True

    def test_cancel_active_task(self):
        manager = FakeStreamManager()
        manager.owners["task-1"] = "user-1"
        task = FakeTask()
        manager.tasks["task-1"] = task
        with patch.object(research_api, "ensure_app_state"):
            result = asyncio_run(
                research_api.cancel_research_task(
                    "task-1", _request(manager), current_user=_user()
                )
            )
        assert result == {"status": "cancelled", "task_id": "task-1"}
        assert task.cancelled is True

    def test_subscribe_validates_stream_and_owner(self):
        manager = FakeStreamManager()
        with patch.object(research_api, "ensure_app_state"):
            with pytest.raises(HTTPException) as missing:
                asyncio_run(
                    research_api.subscribe_research_stream(
                        "unknown", _request(manager), current_user=_user()
                    )
                )
        assert missing.value.status_code == 404

        manager.owners["task-1"] = "someone-else"
        with patch.object(research_api, "ensure_app_state"):
            with pytest.raises(HTTPException) as denied:
                asyncio_run(
                    research_api.subscribe_research_stream(
                        "task-1", _request(manager), current_user=_user()
                    )
                )
        assert denied.value.status_code == 403

        manager.owners["task-1"] = "user-1"
        with patch.object(research_api, "ensure_app_state"):
            response = asyncio_run(
                research_api.subscribe_research_stream(
                    "task-1", _request(manager), current_user=_user()
                )
            )
        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache"

    def test_extract_entities_route(self):
        body = ExtractEntitiesRequest(text="Research text", model="m")
        with patch.object(research_api, "ensure_app_state"), patch.object(
            research_api,
            "extract_entities",
            AsyncMock(return_value={"entities": [], "relationships": []}),
        ) as extract, patch.object(limiter, "enabled", False):
            result = asyncio_run(
                research_api.research_extract_entities(
                    _request(), body, current_user=_user()
                )
            )
        assert result == {"entities": [], "relationships": []}
        extract.assert_awaited_once_with(
            text="Research text", llm_provider=None, model="m"
        )


class TestRunResearch:
    def _run(self, graph, manager=None, request_body=None, supabase=None):
        manager = manager or FakeStreamManager()
        request = _request(manager, graph)
        body = request_body or ResearchRequest(query="What is RAG?")
        modules = {
            "backend.core.supabase": supabase
            or SimpleNamespace(get_profile=lambda _uid: None)
        }
        with patch.object(research_api, "ensure_app_state"), patch.object(
            research_api, "resolve_pdf_paths", AsyncMock(return_value=["doc.pdf"])
        ), patch.object(research_api, "get_tracer", return_value=_tracer()), patch.dict(
            sys.modules, modules
        ), patch.object(
            limiter, "enabled", False
        ):
            return (
                asyncio_run(
                    research_api.run_research(
                        request,
                        body,
                        current_user=_user(),
                        session=MagicMock(),
                        ctx=_ctx(),
                    )
                ),
                manager,
            )

    def test_successful_run_returns_result_and_closes_stream(self):
        graph = MagicMock()
        graph.ainvoke = AsyncMock(
            return_value={
                "status": "completed",
                "answer": "The answer",
                "sources": [{"title": "Source"}],
                "plan": [{"agent": "research_agent"}],
                "logs": [{"agent": "planner"}],
                "errors": [],
                "agent_metrics": {"planner": {"status": "ok"}},
                "plan_reasoning": "Because",
                "answer_mode": "normal",
                "evidence_summary": {"web_count": 1},
                "has_evidence": True,
            }
        )
        response, manager = self._run(graph)

        assert response.status == "completed"
        assert response.answer == "The answer"
        assert response.sources == [{"title": "Source"}]
        assert response.plan == [{"agent": "research_agent"}]
        assert response.evidence_summary == {"web_count": 1}
        assert response.has_evidence is True
        assert manager.closed
        graph.ainvoke.assert_awaited_once()

    def test_missing_status_is_normalized_to_failed(self):
        graph = MagicMock()
        graph.ainvoke = AsyncMock(return_value={"answer": "partial"})
        response, _ = self._run(graph)
        assert response.status == "failed"
        assert any("terminal status" in error for error in response.errors)

    def test_graph_failure_returns_failed_response(self):
        graph = MagicMock()
        graph.ainvoke = AsyncMock(side_effect=RuntimeError("graph exploded"))
        response, manager = self._run(graph)
        assert response.status == "failed"
        assert response.errors == ["graph exploded"]
        assert manager.closed

    def test_cancellation_is_reraised_after_cleanup(self):
        graph = MagicMock()
        graph.ainvoke = AsyncMock(side_effect=asyncio.CancelledError)
        manager = FakeStreamManager()
        request = _request(manager, graph)
        with patch.object(research_api, "ensure_app_state"), patch.object(
            research_api, "resolve_pdf_paths", AsyncMock(return_value=[])
        ), patch.object(research_api, "get_tracer", return_value=_tracer()), patch.dict(
            sys.modules,
            {"backend.core.supabase": SimpleNamespace(get_profile=lambda _uid: None)},
        ), patch.object(
            limiter, "enabled", False
        ):
            with pytest.raises(asyncio.CancelledError):
                asyncio_run(
                    research_api.run_research(
                        request,
                        ResearchRequest(query="Cancel me"),
                        current_user=_user(),
                        session=MagicMock(),
                        ctx=_ctx(),
                    )
                )
        assert manager.closed

    def test_supabase_session_is_created_and_finalized(self):
        graph = MagicMock()
        graph.ainvoke = AsyncMock(
            return_value={"status": "completed", "answer": "answer"}
        )
        supabase = MagicMock()
        supabase.get_profile.return_value = {"id": "sb-user"}
        supabase.create_session.return_value = {"id": "sb-session"}
        with patch.object(research_api, "finalize_supabase_run") as finalize:
            response, manager = self._run(graph, supabase=supabase)

        assert response.supabase_session_id == "sb-session"
        supabase.insert_message.assert_called_once()
        assert manager.persisted[0][1] == {
            "supabase_user_id": "sb-user",
            "session_id": "sb-session",
        }
        assert manager.logs[0][1]["agent"] == "system"
        finalize.assert_called_once()
        assert finalize.call_args.kwargs["session_id"] == "sb-session"

    def test_supabase_initialization_failure_is_ignored(self):
        graph = MagicMock()
        graph.ainvoke = AsyncMock(return_value={"status": "completed"})
        supabase = MagicMock()
        supabase.get_profile.side_effect = RuntimeError("supabase down")
        response, _ = self._run(graph, supabase=supabase)
        assert response.status == "completed"
        assert response.supabase_session_id is None


class TestResearchStreamRoute:
    def test_stream_runs_graph_and_emits_done(self):
        manager = StreamManager()
        graph = MagicMock()
        graph.ainvoke = AsyncMock(return_value={})
        request = _request(manager, graph)

        with patch.object(research_api, "ensure_app_state"), patch.object(
            research_api, "resolve_pdf_paths", AsyncMock(return_value=[])
        ), patch.object(limiter, "enabled", False):
            response = asyncio_run(
                research_api.research_stream(
                    request,
                    query="What is RAG?",
                    conversation_id=None,
                    document_ids="doc-1, doc-2",
                    current_user=_user(),
                    session=MagicMock(),
                    ctx=_ctx(),
                )
            )

        assert isinstance(response, StreamingResponse)

        async def consume():
            return [event async for event in response.body_iterator]

        events = asyncio_run(consume())
        assert any("event: log" in event for event in events)
        assert any("event: done" in event for event in events)
        graph.ainvoke.assert_awaited_once()

    def test_stream_reports_graph_errors(self):
        manager = StreamManager()
        graph = MagicMock()
        graph.ainvoke = AsyncMock(side_effect=RuntimeError("graph failed"))
        request = _request(manager, graph)

        with patch.object(research_api, "ensure_app_state"), patch.object(
            research_api, "resolve_pdf_paths", AsyncMock(return_value=[])
        ), patch.object(limiter, "enabled", False):
            response = asyncio_run(
                research_api.research_stream(
                    request,
                    query="What is RAG?",
                    conversation_id="conv-1",
                    document_ids="",
                    current_user=_user(),
                    session=MagicMock(),
                    ctx=_ctx(),
                )
            )

        async def consume():
            return [event async for event in response.body_iterator]

        events = asyncio_run(consume())
        assert any("graph failed" in event for event in events)
        assert any("event: done" in event for event in events)
