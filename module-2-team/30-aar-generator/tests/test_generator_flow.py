"""
Integration test for the AARGenerator end-to-end flow using the StubClient.

This test verifies that:
  - All four LLM passes are invoked in the expected order
  - The resulting AAR has all four Wharton sections populated
  - Lessons and next steps are parsed from the JSON responses correctly
  - The convenience artifacts (prompt patch, lesson record) are derived

No external API is used; the StubClient returns deterministic canned
responses for each pass.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_PATTERN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PATTERN_ROOT))

from lib.clients import StubClient  # noqa: E402
from lib.generator import AARGenerator  # noqa: E402
from lib.schema import AgentTrace, TraceStep  # noqa: E402


def _make_trace() -> AgentTrace:
    return AgentTrace(
        agent_id="generator-test-001",
        agent_framework="custom-test",
        goal="Find the latest pricing for product XYZ.",
        steps=[
            TraceStep(
                timestamp=datetime(2026, 5, 22, 14, 0, 0),
                type="message",
                content="User asks for product XYZ pricing.",
            ),
            TraceStep(
                timestamp=datetime(2026, 5, 22, 14, 0, 10),
                type="tool_call",
                content="browse(url='https://supplier.example.com/xyz')",
            ),
            TraceStep(
                timestamp=datetime(2026, 5, 22, 14, 0, 14),
                type="observation",
                content="HTTP 503",
            ),
        ],
        outcome="Agent retried 25 times, all failed.",
        success=False,
        retry_count=25,
    )


def _canned_responses() -> list[str]:
    return [
        "Find the latest pricing for product XYZ.",  # step 1: goal
        "Agent retried the same URL 25 times and never escalated.",  # step 2: results
        json.dumps(  # step 3: lessons (JSON array)
            [
                {
                    "pattern": "escalation-of-commitment",
                    "description": "Agent kept retrying the same broken approach.",
                    "root_cause": "No stop rule was specified.",
                    "framework_anchor": "Kahneman & Tversky 1979 - escalation of commitment",
                    "cross_pattern_links": ["#27 bias-stack-detector"],
                }
            ]
        ),
        json.dumps(  # step 4: next steps (JSON array)
            [
                {
                    "intervention_type": "prompt_patch",
                    "description": "Add an explicit stop rule and escalation step.",
                    "suggested_implementation": (
                        "If the same tool call has failed 3 times in a row, STOP "
                        "and escalate to the user."
                    ),
                    "estimated_impact": "high",
                    "rationale": "Caps the retry count and forces a strategy switch.",
                }
            ]
        ),
    ]


def test_aar_generator_four_pass_flow() -> None:
    stub = StubClient(_canned_responses())
    generator = AARGenerator(llm_client=stub, model="stub-model")
    trace = _make_trace()
    aar = generator.generate(trace)

    # Four LLM passes were made.
    assert len(stub.calls) == 4

    # Each pass received the AAR system prompt.
    for _, system in stub.calls:
        assert system is not None
        assert "After-Action Review (AAR) facilitator" in system

    # The AAR has the four Wharton sections populated.
    assert aar.goal == "Find the latest pricing for product XYZ."
    assert "25 times" in aar.results
    assert len(aar.lessons) == 1
    assert aar.lessons[0].pattern == "escalation-of-commitment"
    assert len(aar.next_steps) == 1
    assert aar.next_steps[0].intervention_type == "prompt_patch"

    # Convenience artifacts were derived.
    assert aar.suggested_prompt_patch is not None
    assert "STOP" in aar.suggested_prompt_patch
    assert aar.lesson_record_for_memory is not None
    assert aar.lesson_record_for_memory["type"] == "aar_lesson"


def test_aar_generator_markdown_renders_full_output() -> None:
    stub = StubClient(_canned_responses())
    generator = AARGenerator(llm_client=stub, model="stub-model")
    aar = generator.generate(_make_trace())
    md = aar.to_markdown()

    assert "After-Action Review" in md
    assert "## 1. Goal" in md
    assert "## 2. Results" in md
    assert "## 3. Lessons" in md
    assert "## 4. Next Steps" in md
    assert "Suggested Prompt Patch" in md
    assert "escalation-of-commitment" in md
