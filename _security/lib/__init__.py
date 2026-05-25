"""vstack.security -- production hardening for the REST surface +
helpers used across the rest of vstack.

What this module provides:

* :class:`APIKeyStore` -- loads + validates API keys from env vars
  / config files / explicit lists. Constant-time comparisons.
* :class:`RateLimiter` -- in-memory sliding-window rate limiter
  with a pluggable backend interface for Redis later.
* :class:`RequestLimits` -- declarative caps for body size,
  trace-step count, timeout, max-tokens.
* :func:`audit_input_for_injection` -- thin wrapper over
  :func:`vstack.aar.detect_injection` that the REST + MCP
  servers run on free-text fields before they reach the LLM.
* :func:`safe_subprocess_argv` / :func:`safe_path` -- input
  guards for the parts of vstack that shell out (gbrain,
  chrome-devtools-mcp) or read user-supplied paths
  (baselines, learnings, suite files).

None of this changes default behaviour for existing local-use
flows. The REST API stays loopback-friendly by default;
authentication only kicks in when you explicitly enable it.
"""

from ._auth import APIKey, APIKeyStore, load_keys_from_env, verify_api_key
from ._limits import (
    DEFAULT_REQUEST_LIMITS,
    RequestLimits,
    RequestSizeExceeded,
    enforce_trace_limits,
)
from ._rate_limit import (
    InMemoryRateLimiter,
    RateLimitDecision,
    RateLimiter,
    RateLimitExceeded,
)
from ._validation import (
    audit_input_for_injection,
    safe_path,
    safe_pattern_name,
    safe_subprocess_argv,
)

__all__ = [
    "APIKey",
    "APIKeyStore",
    "DEFAULT_REQUEST_LIMITS",
    "InMemoryRateLimiter",
    "RateLimitDecision",
    "RateLimitExceeded",
    "RateLimiter",
    "RequestLimits",
    "RequestSizeExceeded",
    "audit_input_for_injection",
    "enforce_trace_limits",
    "load_keys_from_env",
    "safe_path",
    "safe_pattern_name",
    "safe_subprocess_argv",
    "verify_api_key",
]

__version__ = "0.6.0"
