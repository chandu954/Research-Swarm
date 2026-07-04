"""Tests for the LRU cache."""
from __future__ import annotations
import time
from backend.core.cache import LRUCache, get_cache, reset_cache


class TestLRUCache:
    def test_set_and_get(self):
        c = LRUCache(maxsize=10, ttl_seconds=60)
        c.set("key1", "value1")
        assert c.get("key1") == "value1"

    def test_missing_key(self):
        c = LRUCache()
        assert c.get("nope") is None

    def test_ttl_expiry(self):
        c = LRUCache(maxsize=10, ttl_seconds=0)
        c.set("key", "val")
        time.sleep(0.01)
        assert c.get("key") is None

    def test_lru_eviction(self):
        c = LRUCache(maxsize=2, ttl_seconds=60)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        assert c.get("a") is None
        assert c.get("b") == 2
        assert c.get("c") == 3

    def test_access_refreshes_order(self):
        c = LRUCache(maxsize=2, ttl_seconds=60)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")
        c.set("c", 3)
        assert c.get("a") == 1
        assert c.get("b") is None
        assert c.get("c") == 3

    def test_invalidate(self):
        c = LRUCache()
        c.set("key", "val")
        c.invalidate("key")
        assert c.get("key") is None

    def test_clear(self):
        c = LRUCache()
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert c.get("a") is None
        assert c.get("b") is None

    def test_cache_singleton(self):
        reset_cache()
        c1 = get_cache()
        c2 = get_cache()
        assert c1 is c2

    def test_reset(self):
        c1 = get_cache()
        reset_cache()
        c2 = get_cache()
        assert c1 is not c2
