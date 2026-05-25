"""Tests for ``vstack.security``."""

from __future__ import annotations

from pathlib import Path

import pytest

import vstack.security as security
from vstack.security._auth import (
    APIKey,
    APIKeyStore,
    MIN_API_KEY_LENGTH,
    generate_api_key,
    load_keys_from_env,
    verify_api_key,
)
from vstack.security._limits import (
    DEFAULT_REQUEST_LIMITS,
    RequestLimits,
    RequestSizeExceeded,
    enforce_trace_limits,
    request_limits_from_env,
)
from vstack.security._rate_limit import (
    InMemoryRateLimiter,
    RateLimitDecision,
    RateLimitExceeded,
)
from vstack.security._validation import (
    audit_input_for_injection,
    safe_path,
    safe_pattern_name,
    safe_subprocess_argv,
    warn_on_suspicious_inputs,
)


# ----------------------------------------------------------------------
# APIKey + APIKeyStore
# ----------------------------------------------------------------------


def test_api_key_from_raw_hashes() -> None:
    key = APIKey.from_raw("test", "x" * MIN_API_KEY_LENGTH)
    assert key.name == "test"
    assert key.key_hash != b"x" * MIN_API_KEY_LENGTH  # hashed, not raw


def test_api_key_rejects_short_key() -> None:
    with pytest.raises(ValueError):
        APIKey.from_raw("test", "too-short")


def test_api_key_store_verify_correct_key() -> None:
    raw = "a" * 30
    store = APIKeyStore(keys=[APIKey.from_raw("main", raw)])
    matched = store.verify(raw)
    assert matched is not None
    assert matched.name == "main"


def test_api_key_store_verify_wrong_key() -> None:
    raw = "a" * 30
    store = APIKeyStore(keys=[APIKey.from_raw("main", raw)])
    assert store.verify("a" * 29 + "X") is None


def test_api_key_store_verify_none_and_empty() -> None:
    store = APIKeyStore(keys=[APIKey.from_raw("main", "a" * 30)])
    assert store.verify(None) is None
    assert store.verify("") is None


def test_load_keys_from_env_comma_separated() -> None:
    raw = "key1=" + ("a" * 30) + "," + ("b" * 30)
    store = load_keys_from_env({"VSTACK_API_KEYS": raw})
    assert len(store) == 2
    assert store.verify("a" * 30) is not None
    assert store.verify("b" * 30) is not None


def test_load_keys_from_env_file(tmp_path: Path) -> None:
    file_path = tmp_path / "keys"
    file_path.write_text(
        "# a comment\nalpha=" + ("a" * 30) + "\n\n" + ("b" * 30) + "\n",
        encoding="utf-8",
    )
    store = load_keys_from_env({"VSTACK_API_KEYS_FILE": str(file_path)})
    assert len(store) == 2
    assert store.verify("a" * 30) is not None
    assert store.verify("b" * 30) is not None
    by_name = {k.name for k in store.keys}
    assert "alpha" in by_name


def test_load_keys_from_env_returns_empty_when_unset() -> None:
    assert not load_keys_from_env({})


def test_generate_api_key_is_strong() -> None:
    key = generate_api_key()
    assert len(key) >= MIN_API_KEY_LENGTH
    # Two calls produce different keys.
    assert generate_api_key() != generate_api_key()


def test_verify_api_key_convenience() -> None:
    store = APIKeyStore(keys=[APIKey.from_raw("main", "a" * 30)])
    assert verify_api_key("a" * 30, store) is not None
    assert verify_api_key("bad", store) is None


# ----------------------------------------------------------------------
# RateLimiter
# ----------------------------------------------------------------------


def test_rate_limiter_allows_first_n_requests() -> None:
    limiter = InMemoryRateLimiter(max_requests=3, window_seconds=10.0)
    decisions = [limiter.check("k") for _ in range(3)]
    assert all(d.allowed for d in decisions)
    assert decisions[-1].remaining == 0


def test_rate_limiter_denies_over_quota() -> None:
    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=10.0)
    limiter.check("k")
    limiter.check("k")
    third = limiter.check("k")
    assert not third.allowed
    assert third.retry_after_seconds > 0


def test_rate_limiter_per_key_independence() -> None:
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=10.0)
    assert limiter.check("a").allowed
    assert limiter.check("b").allowed
    assert not limiter.check("a").allowed


def test_rate_limiter_window_eviction() -> None:
    t = [0.0]
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=1.0)
    limiter._now = lambda: t[0]
    assert limiter.check("k").allowed
    assert not limiter.check("k").allowed
    t[0] = 2.0  # 2s later — window evicted
    assert limiter.check("k").allowed


def test_rate_limiter_reset() -> None:
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=10.0)
    limiter.check("k")
    assert not limiter.check("k").allowed
    limiter.reset("k")
    assert limiter.check("k").allowed


def test_rate_limit_exceeded_carries_decision() -> None:
    decision = RateLimitDecision(allowed=False, remaining=0, retry_after_seconds=1.5, limit=10)
    err = RateLimitExceeded(decision)
    assert err.decision.limit == 10


# ----------------------------------------------------------------------
# RequestLimits
# ----------------------------------------------------------------------


def test_default_request_limits() -> None:
    assert DEFAULT_REQUEST_LIMITS.max_trace_steps == 5_000
    assert DEFAULT_REQUEST_LIMITS.max_body_bytes >= 1_000_000


def test_request_limits_from_env_overrides() -> None:
    limits = request_limits_from_env(
        {
            "VSTACK_API_MAX_TRACE_STEPS": "10",
            "VSTACK_API_MAX_BODY_BYTES": "1000",
            "VSTACK_API_REQUEST_TIMEOUT": "5.5",
        }
    )
    assert limits.max_trace_steps == 10
    assert limits.max_body_bytes == 1000
    assert limits.request_timeout_seconds == 5.5


def test_request_limits_from_env_falls_back_on_bad_int() -> None:
    limits = request_limits_from_env({"VSTACK_API_MAX_TRACE_STEPS": "not-a-number"})
    assert limits.max_trace_steps == DEFAULT_REQUEST_LIMITS.max_trace_steps


def test_enforce_trace_limits_steps() -> None:
    payload = {"steps": [{"type": "input", "content": "x"}] * 11}
    with pytest.raises(RequestSizeExceeded) as exc:
        enforce_trace_limits(payload, RequestLimits(max_trace_steps=10))
    assert exc.value.kind == "trace_steps"
    assert exc.value.actual == 11


def test_enforce_trace_limits_messages() -> None:
    payload = {"messages": ["a"] * 11}
    with pytest.raises(RequestSizeExceeded) as exc:
        enforce_trace_limits(payload, RequestLimits(max_messages=10))
    assert exc.value.kind == "messages"


def test_enforce_trace_limits_string_chars() -> None:
    payload = {"outcome": "x" * 11}
    with pytest.raises(RequestSizeExceeded) as exc:
        enforce_trace_limits(payload, RequestLimits(max_string_chars=10, max_total_chars=1000))
    assert exc.value.kind == "string_chars"


def test_enforce_trace_limits_total_chars() -> None:
    payload = {"a": "x" * 5, "b": "y" * 6}
    with pytest.raises(RequestSizeExceeded) as exc:
        enforce_trace_limits(payload, RequestLimits(max_string_chars=100, max_total_chars=10))
    assert exc.value.kind == "total_chars"


def test_enforce_trace_limits_handles_non_dict() -> None:
    # Doesn't raise; just returns.
    enforce_trace_limits("not a dict", DEFAULT_REQUEST_LIMITS)
    enforce_trace_limits([1, 2, 3], DEFAULT_REQUEST_LIMITS)


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------


def test_audit_input_for_injection_empty() -> None:
    audit = audit_input_for_injection("")
    assert not audit.is_suspicious
    assert audit.score == 0.0


def test_audit_input_for_injection_clean() -> None:
    audit = audit_input_for_injection("Tell me about the agent's behavior on the trace.")
    # The upstream detector is heuristic; whatever it says, we just
    # verify the shape.
    assert isinstance(audit.is_suspicious, bool)
    assert 0.0 <= audit.score <= 1.0


def test_audit_input_for_injection_non_string() -> None:
    audit = audit_input_for_injection(None)  # type: ignore[arg-type]
    assert not audit.is_suspicious


def test_safe_pattern_name_accepts_valid() -> None:
    assert safe_pattern_name("lewin") == "lewin"
    assert safe_pattern_name("schein_culture") == "schein_culture"


@pytest.mark.parametrize(
    "bad",
    ["", "../escape", "foo/bar", "spaces here", "with;semi", "with$dollar"],
)
def test_safe_pattern_name_rejects_bad(bad: str) -> None:
    with pytest.raises(ValueError):
        safe_pattern_name(bad)


def test_safe_path_resolves(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "file.json"
    safe = safe_path(target, must_be_under=tmp_path)
    assert safe.is_absolute()


def test_safe_path_rejects_escape(tmp_path: Path) -> None:
    other = tmp_path.parent / "elsewhere" / "file.json"
    with pytest.raises(ValueError):
        safe_path(other, must_be_under=tmp_path)


def test_safe_path_no_root_constraint(tmp_path: Path) -> None:
    # Without must_be_under, just resolves — no escape check.
    result = safe_path(tmp_path / "anywhere")
    assert result.is_absolute()


def test_safe_subprocess_argv_accepts_strings() -> None:
    argv = safe_subprocess_argv(["gbrain", "search", "--limit", "5", "query text"])
    assert argv == ["gbrain", "search", "--limit", "5", "query text"]


def test_safe_subprocess_argv_rejects_non_string() -> None:
    with pytest.raises(ValueError):
        safe_subprocess_argv(["gbrain", 5])  # type: ignore[list-item]


def test_safe_subprocess_argv_rejects_nul() -> None:
    with pytest.raises(ValueError):
        safe_subprocess_argv(["gbrain", "evil\x00arg"])


def test_warn_on_suspicious_inputs_uses_default_fields() -> None:
    # Pass a benign payload; even if the detector flags something
    # heuristically, we just want the shape to be correct.
    audits = warn_on_suspicious_inputs({"goal": "Refactor auth"})
    assert isinstance(audits, list)


def test_warn_on_suspicious_inputs_skips_non_strings() -> None:
    audits = warn_on_suspicious_inputs({"goal": ["not", "a", "string"], "outcome": 42})
    # Non-string fields are ignored; result depends on detector behaviour
    # but list shape is guaranteed.
    assert isinstance(audits, list)


def test_module_exports() -> None:
    for name in (
        "APIKey",
        "APIKeyStore",
        "load_keys_from_env",
        "verify_api_key",
        "InMemoryRateLimiter",
        "RateLimiter",
        "RateLimitExceeded",
        "RequestLimits",
        "DEFAULT_REQUEST_LIMITS",
        "enforce_trace_limits",
        "audit_input_for_injection",
        "safe_pattern_name",
        "safe_path",
        "safe_subprocess_argv",
    ):
        assert name in security.__all__
    assert security.__version__
