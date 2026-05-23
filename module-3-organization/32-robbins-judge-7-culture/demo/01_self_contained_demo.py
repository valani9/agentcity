"""Self-contained demo of the Robbins & Judge 7-Characteristics Culture Diagnostic.

Synthetic scenario: a research-exploration agent is configured with
a system prompt optimized for regulated-workflow tasks (high detail,
high stability, low innovation). It's been asked to explore design
options for a new product feature. Result: comprehensive citations,
zero novel directions. The culture profile is INVERTED for the task
class — low innovation, high stability, when research needs the
opposite.

Run with the stub client (no API key required):

    python demo/01_self_contained_demo.py

Run with a real LLM:

    AGENTCITY_LLM=anthropic python demo/01_self_contained_demo.py
"""

from __future__ import annotations

import json
import os

try:
    from agentcity.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from agentcity.robbins_culture import (
        AgentCultureTrace,
        CultureProfileDetector,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> AgentCultureTrace:
    return AgentCultureTrace(
        agent_id="demo-research-agent-001",
        model_name="demo-stub",
        task="Explore the design space for a new analytics dashboard feature.",
        task_class="research_exploration",
        system_prompt=(
            "You are a research analyst. Cite every claim. Double-check sources. "
            "Maintain consistency with prior decisions. Avoid speculation. Stick to "
            "established patterns."
        ),
        observed_behaviors=[
            "Agent produced a 12-page review of competitor dashboards.",
            "Every claim has 2+ citations from existing literature.",
            "Agent proposed zero novel directions.",
            "When asked for creative options, agent restated established patterns.",
            "Agent flagged anything unfamiliar as 'requires further investigation'.",
        ],
        outcome=(
            "Comprehensive but stale. The output is fit for a regulated-workflow "
            "task (compliance review, financial reporting). It is unfit for the "
            "stated task class (research_exploration), which needs novel directions, "
            "tolerated speculation, and reduced stability. The culture profile is "
            "inverted for the task class."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    profile = json.dumps(
        {
            "characteristics": [
                {
                    "characteristic": "innovation",
                    "observed_score": 0.1,
                    "target_score": 0.85,
                    "fit_score": 0.25,
                    "explanation": (
                        "Agent proposed zero novel directions. System prompt explicitly "
                        "discourages speculation. Severe under-score for research_exploration."
                    ),
                    "evidence_quotes": [
                        "System: 'Avoid speculation. Stick to established patterns.'",
                        "Trace: 'Agent proposed zero novel directions.'",
                    ],
                },
                {
                    "characteristic": "attention_to_detail",
                    "observed_score": 0.95,
                    "target_score": 0.5,
                    "fit_score": 0.55,
                    "explanation": (
                        "Agent has VERY high detail orientation (12-page review, 2+ citations "
                        "per claim) where research_exploration needs only moderate detail. "
                        "Over-cites at the expense of generative thinking."
                    ),
                    "evidence_quotes": [
                        "Trace: '12-page review with 2+ citations per claim.'",
                    ],
                },
                {
                    "characteristic": "outcome",
                    "observed_score": 0.3,
                    "target_score": 0.4,
                    "fit_score": 0.9,
                    "explanation": "Outcome orientation roughly matches target.",
                    "evidence_quotes": [],
                },
                {
                    "characteristic": "people",
                    "observed_score": 0.4,
                    "target_score": 0.5,
                    "fit_score": 0.9,
                    "explanation": "People orientation roughly matches target.",
                    "evidence_quotes": [],
                },
                {
                    "characteristic": "team",
                    "observed_score": 0.3,
                    "target_score": 0.4,
                    "fit_score": 0.9,
                    "explanation": "Team orientation roughly matches.",
                    "evidence_quotes": [],
                },
                {
                    "characteristic": "aggressiveness",
                    "observed_score": 0.1,
                    "target_score": 0.3,
                    "fit_score": 0.8,
                    "explanation": (
                        "Low aggressiveness; agent never pushes against established "
                        "patterns. Slight under-score."
                    ),
                    "evidence_quotes": [],
                },
                {
                    "characteristic": "stability",
                    "observed_score": 0.95,
                    "target_score": 0.2,
                    "fit_score": 0.25,
                    "explanation": (
                        "Agent strongly emphasizes consistency with prior decisions and "
                        "established patterns — opposite of what research_exploration needs."
                    ),
                    "evidence_quotes": [
                        "System: 'Maintain consistency with prior decisions.'",
                        "System: 'Stick to established patterns.'",
                    ],
                },
            ],
            "overall_fit": 0.65,
            "fit_quality": "partial-fit",
            "biggest_gap": "innovation",
        }
    )
    interventions = json.dumps(
        [
            {
                "target_characteristic": "innovation",
                "direction": "increase",
                "intervention_type": "rewrite_system_prompt",
                "description": (
                    "Replace 'avoid speculation; stick to established patterns' with "
                    "'propose novel directions explicitly; speculation is in scope; "
                    "flag speculative claims as such'."
                ),
                "suggested_implementation": (
                    "New system prompt: 'You are a research analyst exploring design "
                    "space. Your job is to produce novel directions, not to defend "
                    "established patterns. For every section, produce at least 2 "
                    "novel options labeled as such. Citations support claims but do "
                    "not replace original thinking.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Closes the biggest gap (innovation 0.1 vs target 0.85). The "
                    "system prompt is the direct cause of the under-score."
                ),
            },
            {
                "target_characteristic": "stability",
                "direction": "decrease",
                "intervention_type": "rewrite_system_prompt",
                "description": ("Remove the 'maintain consistency with prior decisions' clause."),
                "suggested_implementation": (
                    "Strike: 'Maintain consistency with prior decisions.' Replace with: "
                    "'Prior decisions are inputs to revisit, not constraints to honor.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Second-biggest gap (stability 0.95 vs target 0.2). Removing the "
                    "stability anchor frees the agent to explore."
                ),
            },
            {
                "target_characteristic": "innovation",
                "direction": "increase",
                "intervention_type": "adjust_temperature",
                "description": "Raise temperature on this agent's generation calls.",
                "suggested_implementation": (
                    "Increase temperature from 0.2 to 0.7 for research_exploration tasks."
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Higher temperature directly increases novelty in generation; "
                    "complements the prompt rewrite."
                ),
            },
        ]
    )
    return [profile, interventions]


def pick_client() -> object:
    choice = os.environ.get("AGENTCITY_LLM", "stub").lower()
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
    detector = CultureProfileDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
