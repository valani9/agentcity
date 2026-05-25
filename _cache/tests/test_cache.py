"""Tests for ``vstack.cache``."""

from __future__ import annotations

import threading
import time


import vstack.cache as cache_mod
from vstack.cache._cache import (
    CacheEntry,
    InMemoryLRUCache,
    NullCache,
    build_cache_key,
    resolve_cache_from_env,
)


def _entry(detection: dict | None = None) -> CacheEntry:
    return CacheEntry(detection=detection or {"severity": "low"}, created_at=time.time())


# ----------------------------------------------------------------------
# build_cache_key
# ----------------------------------------------------------------------


def test_build_cache_key_stable_across_dict_order() -> None:
    k1 = build_cache_key(
        pattern="lewin",
        mode="standard",
        model="claude",
        trace={"task": "x", "steps": [{"a": 1, "b": 2}]},
    )
    k2 = build_cache_key(
        pattern="lewin",
        mode="standard",
        model="claude",
        trace={"steps": [{"b": 2, "a": 1}], "task": "x"},
    )
    assert k1 == k2


def test_build_cache_key_differs_on_pattern_change() -> None:
    base = dict(mode="standard", model="claude", trace={"x": 1})
    assert build_cache_key(pattern="lewin", **base) != build_cache_key(pattern="aar", **base)


def test_build_cache_key_starts_with_namespace() -> None:
    k = build_cache_key(pattern="x", mode="y", model=None, trace={})
    assert k.startswith("vstack:")


# ----------------------------------------------------------------------
# InMemoryLRUCache
# ----------------------------------------------------------------------


def test_lru_cache_set_and_get() -> None:
    c = InMemoryLRUCache(capacity=10)
    entry = _entry({"score": 0.5})
    c.set("k", entry)
    got = c.get("k")
    assert got is entry
    stats = c.stats()
    assert stats.hits == 1
    assert stats.sets == 1


def test_lru_cache_miss_increments_misses() -> None:
    c = InMemoryLRUCache(capacity=10)
    assert c.get("missing") is None
    assert c.stats().misses == 1


def test_lru_cache_evicts_at_capacity() -> None:
    c = InMemoryLRUCache(capacity=2)
    c.set("a", _entry())
    c.set("b", _entry())
    c.set("c", _entry())  # evicts "a"
    assert c.get("a") is None
    assert c.get("b") is not None
    assert c.get("c") is not None
    stats = c.stats()
    assert stats.evictions == 1


def test_lru_cache_move_to_end_on_access() -> None:
    c = InMemoryLRUCache(capacity=2)
    c.set("a", _entry())
    c.set("b", _entry())
    c.get("a")  # bumps "a" to fresh
    c.set("c", _entry())  # evicts "b" (oldest now)
    assert c.get("a") is not None
    assert c.get("b") is None


def test_lru_cache_ttl_expires_entries() -> None:
    c = InMemoryLRUCache(capacity=10, ttl_seconds=0.05)
    c.set("k", _entry())
    assert c.get("k") is not None
    time.sleep(0.1)
    assert c.get("k") is None
    assert c.stats().evictions >= 1


def test_lru_cache_delete_and_clear() -> None:
    c = InMemoryLRUCache(capacity=10)
    c.set("a", _entry())
    c.set("b", _entry())
    c.delete("a")
    assert c.get("a") is None
    c.clear()
    assert c.get("b") is None


def test_lru_cache_thread_safety() -> None:
    c = InMemoryLRUCache(capacity=10)

    def worker():
        for i in range(200):
            c.set(f"k{i}", _entry({"i": i}))
            c.get(f"k{i}")

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stats = c.stats()
    assert stats.sets >= 200
    # No crash + counters non-negative.
    assert stats.hits >= 0
    assert stats.misses >= 0


def test_lru_stats_hit_rate() -> None:
    c = InMemoryLRUCache(capacity=10)
    c.set("a", _entry())
    c.get("a")
    c.get("b")
    stats = c.stats()
    assert stats.hit_rate == 0.5


# ----------------------------------------------------------------------
# NullCache
# ----------------------------------------------------------------------


def test_null_cache_never_stores() -> None:
    c = NullCache()
    c.set("k", _entry())
    assert c.get("k") is None
    assert c.stats().misses >= 1


def test_null_cache_clear_is_safe() -> None:
    c = NullCache()
    c.clear()
    c.delete("k")


# ----------------------------------------------------------------------
# resolve_cache_from_env
# ----------------------------------------------------------------------


def test_resolve_cache_from_env_off_default() -> None:
    c = resolve_cache_from_env({})
    assert isinstance(c, NullCache)


def test_resolve_cache_from_env_memory() -> None:
    c = resolve_cache_from_env({"VSTACK_CACHE": "memory"})
    assert isinstance(c, InMemoryLRUCache)
    assert c.capacity == 1024


def test_resolve_cache_from_env_capacity_override() -> None:
    c = resolve_cache_from_env({"VSTACK_CACHE": "memory", "VSTACK_CACHE_CAPACITY": "50"})
    assert isinstance(c, InMemoryLRUCache)
    assert c.capacity == 50


def test_resolve_cache_from_env_ttl_override() -> None:
    c = resolve_cache_from_env({"VSTACK_CACHE": "lru", "VSTACK_CACHE_TTL_SECONDS": "120.5"})
    assert isinstance(c, InMemoryLRUCache)
    assert c.ttl_seconds == 120.5


def test_resolve_cache_from_env_unknown_backend_falls_back() -> None:
    c = resolve_cache_from_env({"VSTACK_CACHE": "redis"})
    assert isinstance(c, NullCache)


def test_module_exports() -> None:
    for name in (
        "CacheBackend",
        "CacheEntry",
        "CacheStats",
        "InMemoryLRUCache",
        "NullCache",
        "build_cache_key",
        "resolve_cache_from_env",
    ):
        assert name in cache_mod.__all__
    assert cache_mod.__version__
