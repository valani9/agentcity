"""
Unit tests for the AAR Generator's Pydantic schema and markdown renderer.

Run with:
    pytest module-2-team/30-aar-generator/tests/

These tests do not require any LLM API key. They exercise:
  - AgentTrace / TraceStep construction and round-trip serialization
  - AAR construction and markdown rendering structure
  - The markdown renderer's Wharton 4-step section ordering
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

_PATTERN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PATTERN_ROOT))

from agentcity.aar.schema import AAR, AgentTrace, Lesson, NextStep, TraceStep  # noqa: E402


def _trace() -> AgentTrace:
    return AgentTrace(
        agent_id="test-agent-001",
        agent_framework="custom-test",
        goal="Refactor the auth module to use JWTs.",
        steps=[
            TraceStep(
                timestamp=datetime(2026, 5, 22, 14, 0, 0),
                type="message",
                content="User: please refactor auth to JWTs.",
            ),
            TraceStep(
                timestamp=datetime(2026, 5, 22, 14, 0, 30),
                type="tool_call",
                content="edit_file(path='auth/middleware.py')",
                metadata={"tool": "edit_file"},
            ),
        ],
        outcome="Tokens created but middleware broken.",
        success=False,
    )


def _aar() -> AAR:
    return AAR(
        goal="Refactor the auth module to use JWTs.",
        results="Agent created JWT logic but broke the existing session middleware.",
        lessons=[
            Lesson(
                pattern="silent-breakage-of-adjacent-code",
                description="JWT logic shipped, session middleware silently broke.",
                root_cause="No regression check on adjacent files.",
                framework_anchor="Wharton AAR doctrine - 'separate decision choosers from evaluators'",
                cross_pattern_links=["#28 critical-evaluator-devils-advocate"],
            )
        ],
        next_steps=[
            NextStep(
                intervention_type="new_eval",
                description="Add a regression test for the session middleware path.",
                suggested_implementation="pytest session_middleware_test.py",
                estimated_impact="high",
                rationale="Catches silent breakage on the next run.",
            )
        ],
        source_trace_id="test-agent-001",
        generator_model="test-model",
        success=False,
    )


class TestAgentTrace:
    def test_construct_minimal(self) -> None:
        trace = AgentTrace(goal="g", steps=[], outcome="o", success=True)
        assert trace.goal == "g"
        assert trace.success is True
        assert trace.steps == []

    def test_roundtrip_json(self) -> None:
        trace = _trace()
        as_json = trace.model_dump_json()
        restored = AgentTrace.model_validate_json(as_json)
        assert restored.goal == trace.goal
        assert len(restored.steps) == len(trace.steps)
        assert restored.steps[0].type == "message"

    def test_invalid_step_type_raises(self) -> None:
        from datetime import timezone

        with pytest.raises(Exception):
            TraceStep(
                timestamp=datetime.now(timezone.utc),
                type="NOT_A_VALID_TYPE",  # type: ignore[arg-type]
                content="x",
            )


class TestAARMarkdown:
    def test_markdown_has_four_wharton_sections(self) -> None:
        md = _aar().to_markdown()
        assert "## 1. Goal — What did we want to accomplish?" in md
        assert "## 2. Results — What did we actually do?" in md
        assert "## 3. Lessons — Why was there a difference?" in md
        assert "## 4. Next Steps — What will we do differently?" in md

    def test_markdown_includes_lesson_framework_anchor(self) -> None:
        md = _aar().to_markdown()
        assert "Wharton AAR doctrine" in md
        assert "silent-breakage-of-adjacent-code" in md

    def test_markdown_section_order_goal_before_results(self) -> None:
        md = _aar().to_markdown()
        goal_idx = md.find("## 1. Goal")
        results_idx = md.find("## 2. Results")
        lessons_idx = md.find("## 3. Lessons")
        next_idx = md.find("## 4. Next Steps")
        assert 0 <= goal_idx < results_idx < lessons_idx < next_idx

    def test_markdown_includes_intervention_type_label(self) -> None:
        md = _aar().to_markdown()
        assert "new_eval" in md
        assert "Add a regression test" in md

    def test_markdown_includes_success_marker(self) -> None:
        md = _aar().to_markdown()
        assert "Outcome:" in md
        assert "failure" in md


class TestAARRoundtripJSON:
    def test_full_aar_serializes_and_restores(self) -> None:
        original = _aar()
        restored = AAR.model_validate_json(original.model_dump_json())
        assert restored.goal == original.goal
        assert restored.success == original.success
        assert len(restored.lessons) == len(original.lessons)
        assert restored.lessons[0].framework_anchor == original.lessons[0].framework_anchor
        assert restored.next_steps[0].intervention_type == "new_eval"
