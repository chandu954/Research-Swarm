"""Simple in-memory LRU cache for research results."""
from __future__ import annotations
import time
from collections import OrderedDict
from typing import Any


class LRUCache:
    """Least-recently-used cache with TTL eviction."""

    def __init__(self, maxsize: int = 128, ttl_seconds: int = 300) -> None:
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        now = time.time()
        if key not in self._data:
            return None
        timestamp, value = self._data.pop(key)
        if now - timestamp > self._ttl:
            return None
        self._data[key] = (timestamp, value)
        return value

    def set(self, key: str, value: Any) -> None:
        self._data[key] = (time.time(), value)
        self._data.move_to_end(key)
        if len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    def invalidate(self, key: str) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()


_cache: LRUCache | None = None


def get_cache() -> LRUCache:
    global _cache
    if _cache is None:
        _cache = LRUCache()
    return _cache


def reset_cache() -> None:
    global _cache
    _cache = None
