"""Streaming utilities for Server-Sent Events and real-time agent logs.

Architecture:
  - Uses threading.Queue (thread-safe) instead of asyncio.Queue so that
    LangGraph nodes running in ThreadPoolExecutor threads can push logs
    without needing an event loop.
  - A background asyncio task drains the threading.Queue and exposes the
    logs via an async generator for SSE streaming.
"""
from __future__ import annotations
import json
import asyncio
import queue as _queue
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Any, Optional
from loguru import logger


class AsyncQueueAdapter:
    """Bridges a threading.Queue to an async generator so the SSE endpoint
    can await new items without blocking the event loop."""

    def __init__(self, maxsize: int = 500):
        self._queue = _queue.Queue(maxsize=maxsize)
        self._closed = False

    def put(self, item: Any) -> None:
        if self._closed:
            return
        try:
            self._queue.put_nowait(item)
        except Exception:
            pass

    def close(self) -> None:
        self._closed = True

    async def get_async(self) -> Any:
        """Await the next item from the queue without blocking the event loop."""
        while True:
            try:
                return self._queue.get_nowait()
            except Exception:
                pass
            await asyncio.sleep(0.05)


async def event_stream(
    task_id: str,
    queue_adapter: AsyncQueueAdapter,
) -> AsyncGenerator[str, None]:
    """Generate SSE-formatted events from a thread-safe queue adapter.

    Terminates when the adapter is closed and the queue is drained.
    Yields formatted SSE strings:
      event: log
      data: {json}

    Cancellation is re-raised (never swallowed) and the trailing `done`
    event is only emitted on normal termination — yielding inside a
    `finally` block would raise ``RuntimeError`` when a client disconnects
    and the generator is closed mid-iteration.
    """
    try:
        while True:
            # Exit when the adapter is closed and nothing left in queue
            if queue_adapter._closed and queue_adapter._queue.empty():
                break
            try:
                log_entry = await asyncio.wait_for(queue_adapter.get_async(), timeout=0.5)
                if log_entry is None:
                    break
                yield f"event: log\ndata: {json.dumps(log_entry)}\n\n"
            except asyncio.TimeoutError:
                # Send heartbeat; if closed check again next iteration
                if queue_adapter._closed and queue_adapter._queue.empty():
                    break
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': time.time()})}\n\n"
    except asyncio.CancelledError:
        logger.debug(f"Stream {task_id} cancelled")
        raise
    else:
        yield f"event: done\ndata: {json.dumps({'task_id': task_id})}\n\n"


def make_log(
    agent: str,
    action: str,
    status: str,
    details: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a structured log entry for streaming."""
    return {
        "timestamp": time.time(),
        "agent": agent,
        "action": action,
        "status": status,
        "details": details,
    }


class StreamManager:
    """Manages active SSE streams and log queues.

    Thread-safe by design — uses threading.Queue so LangGraph nodes
    executing in ThreadPoolExecutor threads can push logs without an event loop.
    """

    def __init__(self):
        self._queues: Dict[str, AsyncQueueAdapter] = {}
        self._persistence: Dict[str, Dict[str, Any]] = {}
        self._owners: Dict[str, str] = {}
        self._tasks: Dict[str, "asyncio.Task[Any]"] = {}

    def create_stream(self, task_id: str, owner_user_id: Optional[str] = None) -> AsyncQueueAdapter:
        """Create a new log queue adapter for a task stream."""
        adapter = AsyncQueueAdapter(maxsize=500)
        self._queues[task_id] = adapter
        if owner_user_id:
            self._owners[task_id] = owner_user_id
        return adapter

    def get_stream(self, task_id: str) -> Optional[AsyncQueueAdapter]:
        """Return the existing queue adapter, if any."""
        return self._queues.get(task_id)

    def has_stream(self, task_id: str) -> bool:
        return task_id in self._queues

    def get_or_create_stream(self, task_id: str, owner_user_id: Optional[str] = None) -> AsyncQueueAdapter:
        """Return existing queue or create one."""
        if task_id not in self._queues:
            return self.create_stream(task_id, owner_user_id=owner_user_id)
        return self._queues[task_id]

    def get_owner(self, task_id: str) -> Optional[str]:
        """Return the user id that created a stream, if known."""
        return self._owners.get(task_id)

    def register_task(self, task_id: str, task: "asyncio.Task[Any]") -> None:
        """Track a background research task so it can be cancelled on shutdown."""
        self._tasks[task_id] = task

    def unregister_task(self, task_id: str, task: "asyncio.Task[Any]") -> None:
        if self._tasks.get(task_id) is task:
            self._tasks.pop(task_id, None)

    async def cancel_all_tasks(self) -> None:
        """Cancel every tracked background task (graceful shutdown)."""
        for task in list(self._tasks.values()):
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    def attach_persistence(
        self, task_id: str, *, supabase_user_id: str, session_id: str
    ) -> None:
        """Attach a Supabase session so streamed agent logs are persisted."""
        self._persistence[task_id] = {
            "user_id": supabase_user_id,
            "session_id": session_id,
        }

    def get_persistence(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._persistence.get(task_id)

    def push_log(self, task_id: str, log: Dict[str, Any]) -> None:
        """Push a log entry to a task's stream. Safe from any thread."""
        adapter = self._queues.get(task_id)
        if not adapter:
            return
        adapter.put(log)
        self._mirror_to_supabase(task_id, log)

    def _mirror_to_supabase(self, task_id: str, log: Dict[str, Any]) -> None:
        """Persist agent lifecycle events to Supabase (Phase 4/5).

        Runs synchronously on the caller thread; failures are swallowed so
        streaming is never blocked by persistence.
        """
        ctx = self._persistence.get(task_id)
        if not ctx:
            return
        try:
            from backend.core.supabase import (
                insert_message,
                update_session,
                upsert_agent_run,
            )

            agent: str = log.get("agent", "")
            action: str = log.get("action", "")
            status: str = log.get("status", "")
            details: str = log.get("details") or ""

            session_status_map = {
                "planner": "planning",
                "research_agent": "searching",
                "document_agent": "documents",
                "merge": "ranking",
                "answer_agent": "writing",
            }
            if status == "running" and agent in session_status_map:
                update_session(ctx["session_id"], status=session_status_map[agent])

            if status in ("running", "completed", "failed"):
                started_at = None
                finished_at = None
                if status == "running":
                    started_at = datetime.now(timezone.utc).isoformat()
                else:
                    finished_at = datetime.now(timezone.utc).isoformat()
                upsert_agent_run(
                    session_id=ctx["session_id"],
                    agent_key=agent,
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                )

            if action == "complete" and status == "completed":
                update_session(ctx["session_id"], status="completed")
            elif action in ("error", "cancelled") and status == "failed":
                update_session(ctx["session_id"], status="failed", error=details[:500])

            if action == "message" and agent == "system":
                insert_message(
                    session_id=ctx["session_id"],
                    role="assistant",
                    content=details,
                )
        except Exception as exc:  # pragma: no cover - resilience path
            logger.debug(f"supabase mirror failed for {task_id}: {exc}")

    def close_stream(self, task_id: str) -> None:
        """Close and remove a stream.

        The tracked task (if any) is unregistered but NOT cancelled here:
        cancellation is the responsibility of the code that owns the task
        (the SSE wrapper on disconnect, or ``cancel_all_tasks`` on shutdown),
        because this method is also called from inside the task's own
        ``finally`` block on normal completion.
        """
        adapter = self._queues.pop(task_id, None)
        if adapter:
            adapter.close()
        self._persistence.pop(task_id, None)
        self._owners.pop(task_id, None)
        self._tasks.pop(task_id, None)


# Singleton
_stream_manager: Optional[StreamManager] = None


def get_stream_manager() -> StreamManager:
    """Get or create the global stream manager."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager
