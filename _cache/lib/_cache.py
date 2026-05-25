"""Caching primitives for analyzer detections."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheEntry:
    """One cached detection."""

    detection: Mapping[str, Any]
    created_at: float
    """``time.time()`` at insertion. Lets the API surface
    ``X-Cache-Age`` headers."""


@dataclass
class CacheStats:
    """Counters maintained by the backend for the ``/metrics`` endpoint."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    """How many entries the LRU evicted to make room. Useful for
    sizing capacity in production."""

    @property
    def total_lookups(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return self.hits / self.total_lookups if self.total_lookups else 0.0


class CacheBackend(Protocol):
    """Pluggable cache interface.

    Implementations must be thread-safe under typical web-server
    request shapes. Memory backends use a lock around the underlying
    OrderedDict; Redis/Memcached backends rely on their server's
    atomicity guarantees.
    """

    def get(self, key: str) -> CacheEntry | None: ...
    def set(self, key: str, entry: CacheEntry) -> None: ...
    def delete(self, key: str) -> None: ...
    def clear(self) -> None: ...
    def stats(self) -> CacheStats: ...


@dataclass
class NullCache:
    """No-op backend used when caching is disabled.

    Never stores anything; every :meth:`get` returns ``None``.
    Counted stats remain zero so the ``/metrics`` endpoint always
    has a stable shape even when the cache is off.
    """

    _stats: CacheStats = field(default_factory=CacheStats)

    def get(self, key: str) -> CacheEntry | None:
        self._stats.misses += 1
        return None

    def set(self, key: str, entry: CacheEntry) -> None:
        return None

    def delete(self, key: str) -> None:
        return None

    def clear(self) -> None:
        return None

    def stats(self) -> CacheStats:
        return self._stats


@dataclass
class InMemoryLRUCache:
    """Simple thread-safe LRU cache.

    Capacity defaults to 1024 entries; tune via the ``capacity``
    constructor arg or the ``VSTACK_CACHE_CAPACITY`` env var when
    resolved through :func:`resolve_cache_from_env`. With typical
    detection sizes (~5-50 KB JSON), 1024 entries works out to
    5-50 MB of in-memory cache. Increase for high-cardinality
    deployments.
    """

    capacity: int = 1024
    ttl_seconds: float | None = None
    """Optional TTL. ``None`` means entries never expire on time
    (only on LRU eviction)."""

    _entries: "OrderedDict[str, CacheEntry]" = field(default_factory=OrderedDict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _stats_obj: CacheStats = field(default_factory=CacheStats)

    def get(self, key: str) -> CacheEntry | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._stats_obj.misses += 1
                return None
            if self.ttl_seconds is not None and (time.time() - entry.created_at > self.ttl_seconds):
                # Expired -- drop + count as a miss.
                del self._entries[key]
                self._stats_obj.misses += 1
                self._stats_obj.evictions += 1
                return None
            # Move to end (LRU-fresh).
            self._entries.move_to_end(key)
            self._stats_obj.hits += 1
            return entry

    def set(self, key: str, entry: CacheEntry) -> None:
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
            self._entries[key] = entry
            self._stats_obj.sets += 1
            while len(self._entries) > self.capacity:
                self._entries.popitem(last=False)
                self._stats_obj.evictions += 1

    def delete(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def stats(self) -> CacheStats:
        # Return a snapshot copy so callers can't mutate.
        with self._lock:
            return CacheStats(
                hits=self._stats_obj.hits,
                misses=self._stats_obj.misses,
                sets=self._stats_obj.sets,
                evictions=self._stats_obj.evictions,
            )


def build_cache_key(
    *,
    pattern: str,
    mode: str,
    model: str | None,
    trace: Mapping[str, Any],
) -> str:
    """Stable cache key for ``(pattern, mode, model, trace)``.

    Canonicalizes the trace JSON (sorted keys, no whitespace) so
    semantically-identical traces produced by different code paths
    hash the same.
    """
    payload = {
        "pattern": pattern,
        "mode": mode,
        "model": model or "",
        "trace": _canonical(trace),
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "vstack:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def resolve_cache_from_env(env: Mapping[str, str] | None = None) -> CacheBackend:
    """Build the configured backend from env vars.

    ``VSTACK_CACHE``:
      * ``"off"`` / unset -> :class:`NullCache`
      * ``"memory"`` / ``"lru"`` -> :class:`InMemoryLRUCache`
      * any other value -> log a warning + return :class:`NullCache`

    ``VSTACK_CACHE_CAPACITY``: capacity for in-memory.
    ``VSTACK_CACHE_TTL_SECONDS``: optional TTL.
    """
    env = env if env is not None else os.environ
    mode = (env.get("VSTACK_CACHE") or "off").strip().lower()
    if mode in ("", "off", "none", "null", "disabled"):
        return NullCache()
    if mode in ("memory", "lru", "inmemory"):
        capacity = _int_env(env, "VSTACK_CACHE_CAPACITY", 1024)
        ttl_raw = env.get("VSTACK_CACHE_TTL_SECONDS")
        ttl = None
        if ttl_raw:
            try:
                ttl = max(0.1, float(ttl_raw))
            except ValueError:
                ttl = None
        return InMemoryLRUCache(capacity=capacity, ttl_seconds=ttl)
    logger.warning("VSTACK_CACHE=%r is not a recognised backend; caching disabled.", mode)
    return NullCache()


# ----------------------------------------------------------------------
# internals
# ----------------------------------------------------------------------


def _canonical(obj: Any) -> Any:
    """Return a JSON-canonical view of ``obj``.

    Sorts dict keys recursively + drops Pydantic models by calling
    ``.model_dump()`` lazily. Lists and tuples are preserved in
    order (semantics are order-sensitive for steps / messages /
    observations).
    """
    if hasattr(obj, "model_dump"):
        return _canonical(obj.model_dump(mode="json"))
    if isinstance(obj, Mapping):
        return {k: _canonical(obj[k]) for k in sorted(obj.keys(), key=str)}
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    return obj


def _int_env(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default
