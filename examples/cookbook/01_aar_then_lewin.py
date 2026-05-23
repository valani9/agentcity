"""Cookbook recipe 1 — AAR (#30) → Lewin (#01) follow-on diagnosis.

The Wharton After-Action Review (#30) identifies *what happened* and
*what should change*. When the change targets the agent itself
(prompt, scaffolding, role), Lewin's behavior formula ``B = f(I, E)``
(#01) lets you diagnose whether the failure was driven by
**individual** (model-side) or **environmental** (scaffold-side)
factors. This recipe chains them.

Stub-friendly: runs with no API key.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from agentcity.aar import (
    AARGenerator,
    AgentTrace,
    StubClient,
    TraceStep,
    new_run_id,
    run_context,
)
from agentcity.lewin import AgentFailureTrace, FailureStep, LewinAttributionDetector


def _aar_stub() -> StubClient:
    # Steps 1 & 2 return plain strings; steps 3 & 4 return JSON arrays
    # whose entries match the Lesson and NextStep schemas.
    return StubClient(
        [
            "Refactor the auth module from cookie sessions to JWTs by EOD.",
            "Agent shipped JWT issuance helpers but left session middleware unchanged. Integration tests red after 5 retries.",
            json.dumps(
                [
                    {
                        "pattern": "silent-scope-reduction",
                        "description": "Agent reduced scope from refactor-all to refactor-helpers without surfacing the change.",
                        "root_cause": "System prompt lacked explicit acceptance criteria.",
                        "framework_anchor": "Lewin 1936 - environmental scaffolding determines behavior",
                        "cross_pattern_links": ["lewin", "smart_goal"],
                    }
                ]
            ),
            json.dumps(
                [
                    {
                        "intervention_type": "prompt_patch",
                        "description": "Add explicit acceptance criteria to the agent's system prompt.",
                        "suggested_implementation": "Append to system prompt: 'Acceptance criteria: ...'",
                        "estimated_impact": "high",
                        "rationale": "Closes the environmental gap surfaced by the AAR.",
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
                        "explanation": "Model capability was adequate for JWT helpers.",
                        "evidence_quotes": ["helpers shipped without errors"],
                    },
                    {
                        "locus": "environmental",
                        "score": 0.85,
                        "severity": "high",
                        "explanation": "System prompt lacked explicit acceptance criteria, leaving scope ambiguous.",
                        "evidence_quotes": ["spec was a single sentence"],
                    },
                    {
                        "locus": "interactional",
                        "score": 0.3,
                        "severity": "low",
                        "explanation": "Some interaction between vague scaffolding and model's scope-reduction tendency.",
                        "evidence_quotes": [],
                    },
                ]
            ),
            json.dumps(
                [
                    {
                        "target_locus": "environmental",
                        "intervention_type": "change_prompt",
                        "description": "Add bulleted acceptance criteria to the system prompt.",
                        "suggested_implementation": "Append: 'Acceptance criteria: (1) all session middleware paths migrated; (2) integration tests green; (3) no implicit scope reduction.'",
                        "estimated_impact": "high",
                        "rationale": "Closes the environmental gap surfaced by the AAR.",
                    }
                ]
            ),
        ]
    )


def main() -> None:
    if os.environ.get("AGENTCITY_LLM", "stub").lower() != "stub":
        raise SystemExit(
            "This cookbook recipe is stub-only by design. For a real-LLM run, "
            "see each pattern's demo/ directory."
        )

    now = datetime.now(timezone.utc)
    aar_trace = AgentTrace(
        goal="Refactor the auth module to use JWTs.",
        steps=[
            TraceStep(timestamp=now, type="observation", content="repo state baseline"),
            TraceStep(timestamp=now, type="tool_call", content="created JWT helpers"),
            TraceStep(
                timestamp=now, type="observation", content="middleware still expects sessions"
            ),
            TraceStep(timestamp=now, type="decision", content="retry integration tests 5x"),
            TraceStep(timestamp=now, type="observation", content="halted with partial success"),
        ],
        outcome="Created JWT helpers but session middleware unchanged. Tests red.",
        success=False,
    )

    with run_context(new_run_id(), pattern="aar_then_lewin"):
        aar = AARGenerator(llm_client=_aar_stub()).generate(aar_trace)
        print("=== After-Action Review ===\n")
        print(aar.to_markdown())

        lewin_trace = AgentFailureTrace(
            agent_id="refactor-agent",
            task=aar_trace.goal,
            steps=[
                FailureStep(type="input", content="Refactor auth to JWTs by EOD."),
                FailureStep(type="tool_call", content="created JWT helpers"),
                FailureStep(type="observation", content="middleware unchanged"),
                FailureStep(type="error", content="integration tests failed; agent halted"),
            ],
            outcome=aar_trace.outcome,
            success=aar_trace.success,
            initial_attribution="model is bad at refactoring",
        )
        lewin = LewinAttributionDetector(_lewin_stub()).run(lewin_trace)
        print("\n=== Lewin Diagnosis (follow-on) ===\n")
        print(lewin.to_markdown())


if __name__ == "__main__":
    main()
