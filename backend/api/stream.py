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
    finally:
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

    def create_stream(self, task_id: str) -> AsyncQueueAdapter:
        """Create a new log queue adapter for a task stream."""
        adapter = AsyncQueueAdapter(maxsize=500)
        self._queues[task_id] = adapter
        return adapter

    def get_or_create_stream(self, task_id: str) -> AsyncQueueAdapter:
        """Return existing queue or create one."""
        if task_id not in self._queues:
            return self.create_stream(task_id)
        return self._queues[task_id]

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
        """Close and remove a stream."""
        adapter = self._queues.pop(task_id, None)
        if adapter:
            adapter.close()
        self._persistence.pop(task_id, None)


# Singleton
_stream_manager: Optional[StreamManager] = None


def get_stream_manager() -> StreamManager:
    """Get or create the global stream manager."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager
