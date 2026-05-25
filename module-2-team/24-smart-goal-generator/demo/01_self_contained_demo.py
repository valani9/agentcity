"""Self-contained demo of the SMART Goal Generator.

Synthetic scenario: an internal PM asks an agent to "improve the user
onboarding flow." Without a SMART restatement, the agent will burn budget
on vague exploration — no completion criteria, no kill criteria, no
deadline. With a SMART spec, the agent has a concrete target ('lift
day-1 activation from 35% to >=50% by end of Q2'), observable success
metrics, kill criteria, and a deadline.

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
    from vstack.smart_goal import GoalRequest, SMARTGoalGenerator
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_request() -> GoalRequest:
    return GoalRequest(
        goal_id="onboarding-q2-2026",
        vague_goal="Improve the user onboarding flow.",
        context=(
            "B2B SaaS product. Current day-1 activation rate (signup -> "
            "first meaningful action) is ~35%. Industry benchmark ~50%. "
            "Drop-off concentrated on the workspace-setup screen. The agent "
            "has read access to Mixpanel + Amplitude + Figma."
        ),
        available_resources=[
            "Mixpanel + Amplitude analytics read access",
            "Figma design files for current onboarding screens",
            "design team for 5h/week",
            "10000-token agent budget per iteration",
        ],
        known_constraints=[
            "no engineering bandwidth this sprint (eng locked on Q1 release)",
            "cannot ship code; can only produce design + copy + analytics changes",
            "cannot modify the auth provider",
        ],
        deadline_hint="end of Q2 (2026-06-30)",
        framework="crewai",
    )


def stub_response() -> str:
    return json.dumps(
        {
            "smart_statement": (
                "Lift day-1 activation rate (signup to first meaningful workspace action) "
                "from 35% to >=50% by 2026-06-30, by iterating on the workspace-setup "
                "screen's copy, layout, and progressive-disclosure structure. Constrained "
                "to design + copy + analytics changes (no eng work) within a per-iteration "
                "budget of 10,000 tokens."
            ),
            "criteria": [
                {
                    "criterion": "specific",
                    "statement": (
                        "Target the workspace-setup screen (not the whole onboarding flow), "
                        "with day-1 activation as the named metric."
                    ),
                    "quality_score": 0.9,
                },
                {
                    "criterion": "measurable",
                    "statement": (
                        "Activation rate measured via Mixpanel cohort 'signup-to-first-action-within-24h'. "
                        "Pass if rate >=50% on a rolling 7-day window."
                    ),
                    "quality_score": 0.95,
                },
                {
                    "criterion": "achievable",
                    "statement": (
                        "50% is industry benchmark, achievable via design + copy iteration "
                        "alone in similar products. Achievable within constraints (no eng work)."
                    ),
                    "quality_score": 0.7,
                },
                {
                    "criterion": "relevant",
                    "statement": (
                        "Drop-off is concentrated on the workspace-setup screen per analytics, "
                        "so improvements here directly address the activation gap."
                    ),
                    "quality_score": 0.85,
                },
                {
                    "criterion": "time_bound",
                    "statement": "2026-06-30 hard deadline; per-iteration budget of 10,000 tokens.",
                    "quality_score": 1.0,
                },
            ],
            "completion_criteria": [
                "Day-1 activation rate on rolling 7-day window >= 50%.",
                "At least 3 design + copy iterations shipped to the workspace-setup screen.",
                "Mixpanel cohort 'signup-to-first-action-within-24h' instrumentation verified.",
                "Final report to PM with iteration log + measured deltas.",
            ],
            "success_metrics": [
                {
                    "name": "day_1_activation_rate",
                    "target": ">=50% (7-day rolling)",
                    "measurement_method": "Mixpanel cohort report; auto-pulled weekly.",
                },
                {
                    "name": "workspace_setup_completion_rate",
                    "target": ">=75%",
                    "measurement_method": "Amplitude funnel: 'signup -> workspace_setup_complete'.",
                },
                {
                    "name": "iteration_count",
                    "target": ">=3 shipped iterations",
                    "measurement_method": "Iteration log in agent workspace.",
                },
            ],
            "kill_criteria": [
                {
                    "name": "budget_exhausted",
                    "condition": "Cumulative token usage > 100,000 across all iterations.",
                    "action_on_trigger": "escalate_to_human",
                },
                {
                    "name": "deadline_overrun",
                    "condition": "Date passes 2026-06-30 AND activation rate < 45%.",
                    "action_on_trigger": "escalate_to_human",
                },
                {
                    "name": "negative_impact",
                    "condition": (
                        "Any iteration drops 7-day rolling activation below baseline (35%) "
                        "for >3 days."
                    ),
                    "action_on_trigger": "rollback_and_escalate",
                },
                {
                    "name": "non_design_blocker",
                    "condition": "Required change needs engineering work (out of scope).",
                    "action_on_trigger": "escalate_to_human",
                },
            ],
            "deadline": "2026-06-30",
            "open_questions": [
                "Does the agent have access to ship Mixpanel cohort changes itself, or does that route through analytics team?",
                "Are A/B tests permitted on the workspace-setup screen, or rolling rollouts only?",
            ],
            "overall_smart_score": 0.88,
            "smart_quality": "strong",
        }
    )


def pick_client() -> object:
    choice = os.environ.get("vstack_LLM", "stub").lower()
    if choice == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if choice == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if choice == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient([stub_response()])


def main() -> None:
    request = build_request()
    client = pick_client()
    generator = SMARTGoalGenerator(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    goal = generator.run(request)
    print(goal.to_markdown())
    print("\n\n--- Agent preamble (for system prompt) ---\n")
    print(goal.to_agent_preamble())


if __name__ == "__main__":
    main()
