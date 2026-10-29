"""Tests for SSE stream infrastructure (queue adapter, event stream, stream manager).

Split from backend/tests/test_realtime_stream_infra.py.
"""

from __future__ import annotations

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.api.stream import (
    AsyncQueueAdapter,
    StreamManager,
    event_stream,
    get_stream_manager,
    make_log,
)


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


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
