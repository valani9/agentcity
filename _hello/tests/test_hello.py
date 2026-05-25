"""Tests for ``vstack.hello``.

These cover the deterministic paths (offline mode, no-key path) and
the structured fields of ``HelloRunResult``. The real-LLM path is not
tested here — that is covered by integration tests in the AAR module.
"""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import pytest

from vstack.hello import (
    LLMResolutionStatus,
    SAMPLE_AAR_MARKDOWN,
    SAMPLE_TRACE,
    resolve_llm_client,
    run_hello,
)
from vstack.hello.cli import main as hello_main


def test_sample_trace_is_a_recognizable_failure_pattern() -> None:
    """The sample trace must be set up so an AAR has something to
    diagnose. If it ever becomes ``success=True`` something has been
    accidentally inverted."""

    assert SAMPLE_TRACE.success is False
    assert len(SAMPLE_TRACE.steps) >= 6
    assert "session" in SAMPLE_TRACE.outcome.lower()
    assert SAMPLE_TRACE.goal.startswith("Add JWT")


def test_resolve_llm_client_no_env_returns_none() -> None:
    resolution = resolve_llm_client(env={})

    assert resolution.status is LLMResolutionStatus.NONE
    assert resolution.client is None
    assert resolution.hint is not None
    assert "ANTHROPIC_API_KEY" in resolution.hint


def test_resolve_llm_client_priority_anthropic_first() -> None:
    """When both Anthropic and OpenAI keys are present, Anthropic wins
    (the project's default). If the Anthropic SDK isn't installed the
    resolver should report that cleanly instead of crashing."""

    resolution = resolve_llm_client(
        env={"ANTHROPIC_API_KEY": "sk-test", "OPENAI_API_KEY": "sk-test"}
    )

    assert resolution.status in (
        LLMResolutionStatus.ANTHROPIC,
        LLMResolutionStatus.NONE,
    )
    if resolution.status is LLMResolutionStatus.NONE:
        assert resolution.hint is not None


def test_run_hello_offline_uses_sample_output() -> None:
    result = run_hello(force_offline=True, env={})

    assert result.used_real_llm is False
    assert result.aar_markdown == SAMPLE_AAR_MARKDOWN
    assert result.resolution.status is LLMResolutionStatus.NONE
    assert result.trace.agent_id == "hello-demo-agent"
    assert "Offline mode" in result.notes[0]


def test_run_hello_no_keys_falls_back_to_sample() -> None:
    result = run_hello(force_offline=False, env={})

    assert result.used_real_llm is False
    assert result.aar_markdown == SAMPLE_AAR_MARKDOWN


def test_cli_prints_banner_and_exits_zero() -> None:
    buf = StringIO()
    with patch("sys.stdout", buf):
        rc = hello_main(["--offline"])
    out = buf.getvalue()

    assert rc == 0
    assert "vstack hello" in out
    assert "After-Action Review" in out
    assert "Try next:" in out


def test_cli_no_banner_skips_header_and_footer() -> None:
    buf = StringIO()
    with patch("sys.stdout", buf):
        rc = hello_main(["--offline", "--no-banner"])
    out = buf.getvalue()

    assert rc == 0
    # Body still present.
    assert "After-Action Review" in out
    # Banner + footer suppressed.
    assert "first-run smoke test" not in out
    assert "Try next:" not in out


def test_cli_json_mode_emits_structured_envelope() -> None:
    buf = StringIO()
    with patch("sys.stdout", buf):
        rc = hello_main(["--offline", "--json"])
    payload = json.loads(buf.getvalue())

    assert rc == 0
    assert payload["used_real_llm"] is False
    assert payload["resolution"]["status"] == "none"
    assert payload["trace"]["step_count"] >= 6
    assert payload["trace"]["success"] is False
    assert payload["aar_markdown"].startswith("# After-Action Review")


def test_cli_help_does_not_crash() -> None:
    """``--help`` should exit 0 without touching anything."""

    with pytest.raises(SystemExit) as exc:
        hello_main(["--help"])
    assert exc.value.code == 0
