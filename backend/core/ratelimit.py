"""Central rate limiting: slowapi limiter + a small sliding-window limiter.

The slowapi ``Limiter`` backs HTTP endpoints (login, refresh, upload,
research, ...). WebSocket routes cannot use slowapi decorators (they never
pass through the HTTP middleware), so connection creation is throttled with
the in-process ``SlidingWindowLimiter``.

The default limit applies to every HTTP route; tighter per-route limits are
declared with ``@limiter.limit(...)`` next to each endpoint.
"""
from __future__ import annotations
import time

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
)


class SlidingWindowLimiter:
    """Fixed-window counter per key, stored in memory.

    Used for WebSocket connection creation where slowapi does not apply.
    Thread-safe enough for single-process FastAPI workers; in multi-worker
    deployments this should be replaced by a shared store (Redis).
    """

    def __init__(self, limit: int = 20, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        """Record a hit for ``key``; return False when the window is full."""
        now = time.time()
        window_start = now - self.window_seconds
        hits = [h for h in self._hits.get(key, []) if h > window_start]
        if len(hits) >= self.limit:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._hits.clear()
        else:
            self._hits.pop(key, None)


# 20 WebSocket connections per IP per minute.
ws_limiter = SlidingWindowLimiter(limit=20, window_seconds=60)

__all__ = [
    "limiter",
    "ws_limiter",
    "RateLimitExceeded",
    "rate_limit_exceeded_handler",
    "SlidingWindowLimiter",
]

rate_limit_exceeded_handler = _rate_limit_exceeded_handler
