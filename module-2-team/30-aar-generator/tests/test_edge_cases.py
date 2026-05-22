"""
Edge-case tests for the AAR Generator's production-readiness.

Covers:
  - Empty / whitespace-only required fields are rejected at validation
  - Huge traces are truncated, not crashed
  - Malformed LLM JSON does not crash the pipeline
  - Unicode and emoji content survives round-trip
  - Lessons / NextSteps with bad shapes are dropped, not raised
  - The retry helper distinguishes retryable from non-retryable errors
  - JSON extraction handles markdown fences, prose wrapping, and naked JSON
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_PATTERN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PATTERN_ROOT))

from lib._json_parsing import extract_json_array  # noqa: E402
from lib._retry import _is_retryable, with_retry  # noqa: E402
from lib.clients import StubClient  # noqa: E402
from lib.generator import AARGenerator  # noqa: E402
from lib.schema import AgentTrace, TraceStep  # noqa: E402


def _trace(**overrides: object) -> AgentTrace:
    base: dict[str, object] = dict(
        goal="default goal",
        steps=[
            TraceStep(
                timestamp=datetime.now(timezone.utc),
                type="message",
                content="x",
            )
        ],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return AgentTrace(**base)  # type: ignore[arg-type]


class TestInputValidation:
    def test_empty_goal_rejected(self) -> None:
        stub = StubClient(["g", "r", "[]", "[]"])
        gen = AARGenerator(stub)
        with pytest.raises(ValueError, match="goal"):
            gen.generate(_trace(goal=""))

    def test_whitespace_goal_rejected(self) -> None:
        stub = StubClient(["g", "r", "[]", "[]"])
        gen = AARGenerator(stub)
        with pytest.raises(ValueError, match="goal"):
            gen.generate(_trace(goal="   \n\t  "))

    def test_empty_outcome_rejected(self) -> None:
        stub = StubClient(["g", "r", "[]", "[]"])
        gen = AARGenerator(stub)
        with pytest.raises(ValueError, match="outcome"):
            gen.generate(_trace(outcome=""))

    def test_empty_steps_allowed(self) -> None:
        """An empty step list is unusual but legitimate (a 'no-op' run);
        the validator should not reject it."""
        stub = StubClient(["g", "r", "[]", "[]"])
        gen = AARGenerator(stub)
        aar = gen.generate(_trace(steps=[]))
        assert aar.goal == "g"


class TestTraceSerialization:
    def test_huge_trace_is_truncated(self) -> None:
        big_step_content = "X" * 5000
        steps = [
            TraceStep(
                timestamp=datetime.now(timezone.utc),
                type="message",
                content=big_step_content,
            )
            for _ in range(200)
        ]
        stub = StubClient(["g", "r", "[]", "[]"])
        gen = AARGenerator(stub, max_trace_chars=10_000)
        # Should not crash.
        aar = gen.generate(_trace(steps=steps))
        assert aar.goal == "g"

    def test_unicode_content_survives(self) -> None:
        steps = [
            TraceStep(
                timestamp=datetime.now(timezone.utc),
                type="message",
                content="测试 emoji 🤖 русский العربية 日本語",
            )
        ]
        stub = StubClient(["g", "r", "[]", "[]"])
        gen = AARGenerator(stub)
        aar = gen.generate(_trace(steps=steps))
        # Serialization should preserve the original content.
        assert "🤖" in gen._serialize_trace(_trace(steps=steps))
        assert aar is not None


class TestMalformedLLMOutput:
    def test_lessons_with_bad_shape_are_dropped_not_raised(self) -> None:
        responses = [
            "g",
            "r",
            json.dumps(
                [
                    # First lesson is well-formed
                    {
                        "pattern": "good",
                        "description": "ok",
                        "root_cause": "ok",
                        "framework_anchor": "ok",
                        "cross_pattern_links": [],
                    },
                    # Second lesson is missing required fields
                    {"pattern": "bad-shape"},
                ]
            ),
            "[]",
        ]
        gen = AARGenerator(StubClient(responses))
        aar = gen.generate(_trace())
        # The well-formed lesson survives, the malformed one is dropped.
        assert len(aar.lessons) == 1
        assert aar.lessons[0].pattern == "good"

    def test_unparseable_json_yields_empty_list(self) -> None:
        responses = ["g", "r", "this is not JSON at all", "[]"]
        gen = AARGenerator(StubClient(responses))
        aar = gen.generate(_trace())
        assert aar.lessons == []

    def test_json_array_extracted_from_markdown_fence(self) -> None:
        fenced = '```json\n[{"pattern":"p","description":"d","root_cause":"r","framework_anchor":"a"}]\n```'
        result = extract_json_array(fenced)
        assert len(result) == 1
        assert result[0]["pattern"] == "p"

    def test_json_array_extracted_from_prose_wrapper(self) -> None:
        wrapped = (
            "Sure! Here is the JSON you asked for:\n"
            '[{"pattern":"p","description":"d","root_cause":"r","framework_anchor":"a"}]\n'
            "Let me know if you need anything else!"
        )
        result = extract_json_array(wrapped)
        assert len(result) == 1

    def test_naked_json_object_wrapped_into_list(self) -> None:
        result = extract_json_array(
            '{"pattern":"p","description":"d","root_cause":"r","framework_anchor":"a"}'
        )
        assert len(result) == 1


class TestRetry:
    def test_authentication_error_is_not_retried(self) -> None:
        class AuthenticationError(Exception):
            pass

        exc = AuthenticationError("bad token")
        assert not _is_retryable(exc)

    def test_rate_limit_error_is_retried(self) -> None:
        class RateLimitError(Exception):
            pass

        exc = RateLimitError("slow down")
        assert _is_retryable(exc)

    def test_connection_error_is_retried(self) -> None:
        exc = ConnectionError("network unreachable")
        assert _is_retryable(exc)

    def test_retry_succeeds_on_second_attempt(self) -> None:
        attempts = {"n": 0}

        class TransientRateLimitError(Exception):
            pass

        def flaky() -> str:
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise TransientRateLimitError("rate limit")
            return "ok"

        wrapped = with_retry(flaky, max_attempts=3, base_delay=0.001)
        assert wrapped() == "ok"
        assert attempts["n"] == 2

    def test_retry_gives_up_after_max_attempts(self) -> None:
        class TransientRateLimitError(Exception):
            pass

        def always_fails() -> str:
            raise TransientRateLimitError("rate limit")

        wrapped = with_retry(always_fails, max_attempts=2, base_delay=0.001)
        with pytest.raises(TransientRateLimitError):
            wrapped()
