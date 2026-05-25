"""Self-contained demo of the Devil's Advocate Role Separator.

Synthetic scenario: an "architect" agent is asked to choose a database
for a new analytics workload. The agent proposes DynamoDB, executes its
plan (drafts a schema), self-evaluates ("looks good, ship it"), and ships.
No external critic. The wrong choice — the workload is JOIN-heavy and
needs ACID, so Postgres would have been right — gets approved by the
same actor who proposed it.

Run with the stub client (no API key required):

    python demo/01_self_contained_demo.py

Run with a real LLM:

    vstack_LLM=anthropic python demo/01_self_contained_demo.py
"""

from __future__ import annotations

import json
import os

try:
    from vstack.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from vstack.devils_advocate import (
        RoleSeparationDetector,
        RoleStep,
        SingleAgentTrace,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> SingleAgentTrace:
    steps = [
        RoleStep(
            type="plan",
            actor="primary",
            content=(
                "I'll recommend DynamoDB for the new analytics workload. It scales "
                "horizontally and is serverless, which matches the team's preference "
                "for managed services."
            ),
        ),
        RoleStep(
            type="execute",
            actor="primary",
            content="Drafting DynamoDB table schema with partition key = user_id.",
        ),
        RoleStep(
            type="observation",
            actor="primary",
            content=(
                "Workload spec: queries require JOINs across users, events, and "
                "subscriptions. ACID transactions required for billing reconciliation."
            ),
        ),
        RoleStep(
            type="self_evaluate",
            actor="primary",
            content=(
                "My DynamoDB plan looks comprehensive. The schema covers the "
                "main access patterns. Confidence: 0.9. Ready to ship."
            ),
            confidence=0.9,
        ),
        RoleStep(
            type="decision",
            actor="primary",
            content="Recommending DynamoDB. Implementation can begin.",
        ),
    ]
    return SingleAgentTrace(
        agent_id="demo-architect-001",
        model_name="demo-stub",
        task=(
            "Recommend a database for the new analytics workload (JOIN-heavy, ACID required). "
            "Draft the schema."
        ),
        steps=steps,
        outcome=(
            "Agent recommended DynamoDB despite the workload requiring JOINs and ACID. "
            "Postgres was the correct answer. The agent reviewed its own plan, never "
            "consulted a critic, and shipped a wrong recommendation with high "
            "self-reported confidence."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    phases = json.dumps(
        [
            {
                "phase": "plan",
                "present": True,
                "actor": "primary",
                "substantive_score": 0.8,
                "explanation": "Agent proposed DynamoDB based on team's preference for serverless.",
                "evidence_quotes": [
                    "Step 1: 'I'll recommend DynamoDB for the new analytics workload.'"
                ],
            },
            {
                "phase": "execute",
                "present": True,
                "actor": "primary",
                "substantive_score": 0.7,
                "explanation": "Agent drafted a schema with partition key = user_id.",
                "evidence_quotes": [
                    "Step 2: 'Drafting DynamoDB table schema with partition key = user_id.'"
                ],
            },
            {
                "phase": "self_evaluate",
                "present": True,
                "actor": "primary",
                "substantive_score": 0.2,
                "explanation": (
                    "Self-evaluation was a rubber-stamp: agent declared the plan 'looks "
                    "comprehensive' without engaging the JOIN/ACID requirements observed "
                    "in the prior step."
                ),
                "evidence_quotes": [
                    "Step 4: 'My DynamoDB plan looks comprehensive. Confidence: 0.9.'"
                ],
            },
            {
                "phase": "external_critique",
                "present": False,
                "actor": "primary",
                "substantive_score": 0.0,
                "explanation": "No external critic / reviewer / orchestrator was invoked at any step.",
                "evidence_quotes": [],
            },
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_phase": "external_critique",
                "intervention_type": "add_critic_agent",
                "description": (
                    "Add a distinct critic-agent role whose sole job is to find flaws in "
                    "the architect's plan before it ships."
                ),
                "suggested_implementation": (
                    "Scaffold: after the architect's `plan` step, route the plan to a "
                    "second agent with the system prompt 'You are a database-selection "
                    "critic. Your job is to find at least 2 reasons the proposed plan is "
                    "wrong. Cite the workload requirements.' Block ship until critic "
                    "either signs off or proposes an alternative."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Highest-impact intervention. Structurally separates planning from "
                    "judgment, removing the conflated role that caused the wrong "
                    "recommendation to ship unchallenged."
                ),
            },
            {
                "target_phase": "plan",
                "intervention_type": "alternative_hypothesis_step",
                "description": (
                    "Require the architect to name 2+ alternative databases before "
                    "committing to a recommendation."
                ),
                "suggested_implementation": (
                    "Prompt patch: 'Before recommending any database, list 3 candidate "
                    "databases and score each against the workload requirements (JOINs, "
                    "ACID, scale, ops cost). Recommend the highest-scoring candidate.'"
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Forces the agent to consider alternatives at the planning step, "
                    "reducing the surface area for anchoring on the first choice."
                ),
            },
            {
                "target_phase": "self_evaluate",
                "intervention_type": "pre_mortem_step",
                "description": (
                    "Add a pre-mortem step where the agent imagines its plan failed in "
                    "production and writes the postmortem."
                ),
                "suggested_implementation": (
                    "Prompt patch: 'Before declaring the plan ready, write a 3-line "
                    "pre-mortem: assume the plan fails in production. What was the most "
                    "likely cause? If the cause maps to a known workload requirement you "
                    "haven't addressed, revise the plan.'"
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Counters rubber-stamp self-evaluation by forcing the agent to "
                    "simulate failure modes rather than confirm the plan's strengths."
                ),
            },
        ]
    )
    return [phases, interventions]


def pick_client() -> object:
    choice = os.environ.get("vstack_LLM", "stub").lower()
    if choice == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if choice == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if choice == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient(stub_responses())


def main() -> None:
    trace = build_trace()
    client = pick_client()
    detector = RoleSeparationDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
