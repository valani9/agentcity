"""Cookbook recipe 2 — parallel pattern fan-out over one agent trace.

In a production deployment you may want to evaluate one agent run
against multiple patterns simultaneously (AAR, Lewin, Vroom) to
triangulate failure modes. The library's APIs are synchronous, but
because the StubClient is in-process, ``asyncio.to_thread`` lets you
fan out three diagnostic runs concurrently with zero per-pattern
changes.

For real LLM traffic, swap each StubClient for an Anthropic / OpenAI
async client and run the patterns via the async clients' own
``complete`` method — the same fan-out shape applies.

Stub-friendly: runs with no API key.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from vstack.aar import (
    AARGenerator,
    AgentTrace,
    StubClient,
    TraceStep,
    new_run_id,
    run_context,
)
from vstack.lewin import AgentFailureTrace, FailureStep, LewinAttributionDetector
from vstack.vroom_expectancy import AgentExpectancyTrace, VroomExpectancyCalculator


def _aar_stub() -> StubClient:
    return StubClient(
        [
            "Refactor auth from cookie sessions to JWTs.",
            "Helpers shipped; middleware unchanged; tests red.",
            json.dumps(
                [
                    {
                        "pattern": "silent-scope-reduction",
                        "description": "Agent reduced scope silently.",
                        "root_cause": "Vague system prompt.",
                        "framework_anchor": "Lewin 1936",
                        "cross_pattern_links": ["lewin"],
                    }
                ]
            ),
            json.dumps(
                [
                    {
                        "intervention_type": "prompt_patch",
                        "description": "Add acceptance criteria.",
                        "suggested_implementation": "Append bulleted list to prompt.",
                        "estimated_impact": "high",
                        "rationale": "Closes scope ambiguity.",
                    }
                ]
            ),
        ]
    )


def _lewin_stub() -> StubClient:
    return StubClient(
        [
            json.dumps(
                [
                    {
                        "locus": "internal",
                        "score": 0.2,
                        "severity": "low",
                        "explanation": "Model capability was adequate.",
                        "evidence_quotes": [],
                    },
                    {
                        "locus": "environmental",
                        "score": 0.85,
                        "severity": "high",
                        "explanation": "System prompt lacked acceptance criteria.",
                        "evidence_quotes": ["spec one sentence"],
                    },
                    {
                        "locus": "interactional",
                        "score": 0.3,
                        "severity": "low",
                        "explanation": "Minor interaction effect.",
                        "evidence_quotes": [],
                    },
                ]
            ),
            json.dumps(
                [
                    {
                        "target_locus": "environmental",
                        "intervention_type": "change_prompt",
                        "description": "Add acceptance criteria.",
                        "suggested_implementation": "Append to system prompt.",
                        "estimated_impact": "high",
                        "rationale": "Closes the environmental gap.",
                    }
                ]
            ),
        ]
    )


def _vroom_stub() -> StubClient:
    return StubClient(
        [
            json.dumps(
                [
                    {
                        "term": "expectancy",
                        "score": 0.3,
                        "explanation": "Agent didn't believe scope was achievable.",
                        "evidence_quotes": ["retried 5x then halted"],
                    },
                    {
                        "term": "instrumentality",
                        "score": 0.5,
                        "explanation": "Output-to-impact link unclear.",
                        "evidence_quotes": [],
                    },
                    {
                        "term": "valence",
                        "score": 0.6,
                        "explanation": "Task framed as routine refactor.",
                        "evidence_quotes": [],
                    },
                ]
            ),
            json.dumps(
                [
                    {
                        "target_term": "expectancy",
                        "intervention_type": "scaffold_subtasks",
                        "description": "Break refactor into 5 explicit substeps.",
                        "suggested_implementation": "Add 5 numbered substeps to system prompt.",
                        "estimated_impact": "high",
                        "rationale": "Raises expectancy by making scope tractable.",
                    }
                ]
            ),
        ]
    )


def _run_aar() -> str:
    now = datetime.now(timezone.utc)
    trace = AgentTrace(
        goal="Refactor auth",
        steps=[
            TraceStep(timestamp=now, type="observation", content="cookies in middleware"),
            TraceStep(timestamp=now, type="tool_call", content="created JWT helpers"),
            TraceStep(timestamp=now, type="observation", content="middleware unchanged"),
        ],
        outcome="Tests red",
        success=False,
    )
    return AARGenerator(llm_client=_aar_stub()).generate(trace).to_markdown()


def _run_lewin() -> str:
    trace = AgentFailureTrace(
        agent_id="refactor-agent",
        task="Refactor auth to JWTs",
        steps=[
            FailureStep(type="input", content="Refactor auth to JWTs."),
            FailureStep(type="tool_call", content="created helpers"),
            FailureStep(type="observation", content="middleware unchanged"),
            FailureStep(type="error", content="tests red, agent halted"),
        ],
        outcome="Tests red",
        success=False,
    )
    return LewinAttributionDetector(_lewin_stub()).run(trace).to_markdown()


def _run_vroom() -> str:
    trace = AgentExpectancyTrace(
        agent_id="refactor-agent",
        task="Refactor auth",
        task_class="code_generation",
        system_prompt="Refactor auth to JWTs.",
        observed_behaviors=["agent halted partway"],
        effort_signals=["retried 5x then quit"],
        outcome="Tests red",
        success=False,
    )
    return VroomExpectancyCalculator(_vroom_stub()).run(trace).to_markdown()


async def main() -> None:
    with run_context(new_run_id(), pattern="parallel_fan_out"):
        aar_md, lewin_md, vroom_md = await asyncio.gather(
            asyncio.to_thread(_run_aar),
            asyncio.to_thread(_run_lewin),
            asyncio.to_thread(_run_vroom),
        )

    print("=== AAR ===\n")
    print(aar_md)
    print("\n=== Lewin ===\n")
    print(lewin_md)
    print("\n=== Vroom ===\n")
    print(vroom_md)


if __name__ == "__main__":
    asyncio.run(main())
