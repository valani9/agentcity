"""vstack.cache -- optional caching layer for analyzer detections.

Identical traces produce identical detections (modulo LLM
non-determinism). Caching the (pattern, mode, model, trace_hash)
-> detection map across analyzer runs is a free cost reduction for
the busy-server case: a typical observability pipeline replays the
same trace through multiple patterns + multiple modes, often within
seconds.

The default backend is in-memory LRU. The :class:`CacheBackend`
protocol lets a downstream user plug in Redis / Memcached / disk
without touching the call sites in :mod:`vstack.adapters`.

The cache is **opt-in**. Set ``VSTACK_CACHE=memory`` or pass a
backend instance to :func:`vstack.adapters.run_pattern_dispatch`
to enable. Default is no-cache, so existing tests + flows are
unchanged.

Key construction: SHA-256 of ``(pattern, mode, model,
trace_json_canonical)`` — canonical because Python dict ordering
isn't trace-content. Detection model determinism is the LLM's
problem; the cache trusts the pattern's output is reproducible
when the inputs match.
"""

from ._cache import (
    CacheBackend,
    CacheEntry,
    CacheStats,
    InMemoryLRUCache,
    NullCache,
    build_cache_key,
    resolve_cache_from_env,
)

__all__ = [
    "CacheBackend",
    "CacheEntry",
    "CacheStats",
    "InMemoryLRUCache",
    "NullCache",
    "build_cache_key",
    "resolve_cache_from_env",
]

__version__ = "0.6.0"
