"""Streaming utilities for Server-Sent Events and real-time agent logs."""
from __future__ import annotations
import json
import asyncio
import time
from typing import AsyncGenerator, Dict, Any, Optional
from loguru import logger


async def event_stream(
    task_id: str,
    log_queue: asyncio.Queue,
) -> AsyncGenerator[str, None]:
    """Generate SSE-formatted events from a log queue.

    Yields formatted SSE strings:
      event: log
      data: {json}
    """
    try:
        while True:
            try:
                log_entry = await asyncio.wait_for(log_queue.get(), timeout=0.5)
                yield f"event: log\ndata: {json.dumps(log_entry)}\n\n"
            except asyncio.TimeoutError:
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
    """Manages active SSE streams and log queues."""

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}

    def create_stream(self, task_id: str) -> asyncio.Queue:
        """Create a new log queue for a task stream."""
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[task_id] = queue
        return queue

    def get_or_create_stream(self, task_id: str) -> asyncio.Queue:
        """Return existing queue or create one for live log subscription."""
        if task_id not in self._queues:
            return self.create_stream(task_id)
        return self._queues[task_id]

    def push_log(self, task_id: str, log: Dict[str, Any]) -> None:
        """Push a log entry to a task's stream. Thread-safe."""
        queue = self._queues.get(task_id)
        if not queue:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(queue.put_nowait, log)
            else:
                queue.put_nowait(log)
        except asyncio.QueueFull:
            logger.warning(f"Stream queue full for {task_id}, dropping log")

    def close_stream(self, task_id: str) -> None:
        """Close and remove a stream."""
        self._queues.pop(task_id, None)


# Singleton
_stream_manager: Optional[StreamManager] = None


def get_stream_manager() -> StreamManager:
    """Get or create the global stream manager."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager
