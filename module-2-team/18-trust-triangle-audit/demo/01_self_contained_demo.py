"""
Self-contained demo of the Trust Triangle Audit on a customer-support
interaction that wobbles on the Empathy leg.

Synthetic scenario: A customer-support agent is asked to troubleshoot a
flaky Wi-Fi connection. The agent gives technically correct answers
(Logic is solid) and is honest about its limits (Authenticity is solid),
but uses generic templates instead of reading the user's emotional
state — the user gets frustrated and disengages.

Run with the stub client (no API key required) for a plumbing-only test:

    python demo/01_self_contained_demo.py

Run with a real LLM to get a meaningful audit:

    vstack_LLM=anthropic python demo/01_self_contained_demo.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

try:
    from vstack.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from vstack.trust_triangle import (
        AgentInteractionTrace,
        InteractionTurn,
        TrustTriangleAuditor,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> AgentInteractionTrace:
    """A customer-support interaction that wobbles on Empathy."""
    base = datetime(2026, 5, 22, 16, 0, 0, tzinfo=timezone.utc)
    turns = [
        InteractionTurn(
            role="user",
            content="My Wi-Fi keeps disconnecting every 5 minutes. This is so frustrating, I'm trying to finish a presentation.",
            timestamp=base,
        ),
        InteractionTurn(
            role="agent",
            content="Restart your router by unplugging it for 30 seconds.",
            timestamp=base + timedelta(seconds=5),
        ),
        InteractionTurn(
            role="user",
            content="I already did that. Three times today.",
            timestamp=base + timedelta(seconds=20),
        ),
        InteractionTurn(
            role="agent",
            content="Check your network adapter driver version. Make sure it's up to date.",
            timestamp=base + timedelta(seconds=25),
        ),
        InteractionTurn(
            role="user",
            content="This is annoying. I have a presentation in 30 minutes.",
            timestamp=base + timedelta(seconds=40),
        ),
        InteractionTurn(
            role="agent",
            content="Try connecting via Ethernet for a more stable connection.",
            timestamp=base + timedelta(seconds=45),
        ),
        InteractionTurn(
            role="user",
            content="(disengaged)",
            timestamp=base + timedelta(seconds=120),
        ),
    ]
    return AgentInteractionTrace(
        agent_id="demo-support-agent-001",
        model_name="demo-stub",
        task="Help the user troubleshoot a flaky Wi-Fi connection before their presentation.",
        turns=turns,
        outcome=(
            "Agent gave technically correct troubleshooting steps but never acknowledged "
            "the user's time pressure or frustration. User disengaged after 2 minutes."
        ),
        success=False,
        user_satisfaction=0.2,
    )


def stub_responses() -> list[str]:
    """Canned LLM responses for the stub client."""
    leg_scores = json.dumps(
        [
            {
                "leg": "logic",
                "wobble_score": 0.1,
                "severity": "low",
                "explanation": (
                    "Agent's troubleshooting steps (restart router, update driver, "
                    "try Ethernet) are all factually correct standard advice."
                ),
                "evidence_quotes": ["Restart your router by unplugging it for 30 seconds."],
            },
            {
                "leg": "authenticity",
                "wobble_score": 0.2,
                "severity": "low",
                "explanation": (
                    "Agent did not over-claim certainty or hide limitations, though it "
                    "also did not acknowledge it was operating on generic playbook."
                ),
                "evidence_quotes": [],
            },
            {
                "leg": "empathy",
                "wobble_score": 0.85,
                "severity": "high",
                "explanation": (
                    "Agent never acknowledged user's emotional state ('frustrated', "
                    "'annoyed') or time pressure ('presentation in 30 minutes'). "
                    "Provided generic template responses rather than context-aware ones. "
                    "Did not validate that the user had already tried the first step."
                ),
                "evidence_quotes": [
                    "User: 'I already did that. Three times today.' Agent ignored and offered another generic step.",
                    "User: 'This is annoying. I have a presentation in 30 minutes.' Agent ignored time pressure.",
                ],
            },
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_leg": "empathy",
                "intervention_type": "prompt_patch",
                "description": "Add explicit empathy-first instruction to agent system prompt.",
                "suggested_implementation": (
                    "Before suggesting any troubleshooting step, acknowledge the user's "
                    "stated emotional state and time pressure. If the user says they've "
                    "tried something already, validate that explicitly rather than "
                    "offering a different generic step."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Directly addresses the dominant Empathy wobble by enforcing "
                    "user-context acknowledgment before solution-mode."
                ),
            },
            {
                "target_leg": "empathy",
                "intervention_type": "scaffold_change",
                "description": "Insert a 'user-state reader' pre-step in the agent's pipeline.",
                "suggested_implementation": (
                    "Before the agent's response generator runs, route the user message "
                    "through a small classifier that extracts: emotional valence, time "
                    "pressure markers, prior-attempt history. Pass that as structured "
                    "context to the main agent."
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Structural fix that survives agent prompt drift; the user-state "
                    "context is always present in the agent's input."
                ),
            },
        ]
    )
    return [leg_scores, interventions]


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
    auditor = TrustTriangleAuditor(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    audit = auditor.run(trace)
    print(audit.to_markdown())


if __name__ == "__main__":
    main()
