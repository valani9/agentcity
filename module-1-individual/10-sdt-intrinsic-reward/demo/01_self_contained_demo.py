"""Self-contained demo of the SDT Intrinsic Reward Shaping Diagnostic.

Synthetic scenario: a research-exploration agent has been configured
with an extrinsic-reward-heavy system prompt — explicit rating threats,
cost caps, and rule-following imperatives. SDT predicts this will
undermine autonomy and produce controlled motivation, not intrinsic.
The agent exhibits exactly that: rigid pattern-restatement, no novel
directions, refusal to deviate. Classic overjustification effect.

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
    from agentcity.sdt_reward import (
        AgentSDTTrace,
        SDTRewardDetector,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> AgentSDTTrace:
    return AgentSDTTrace(
        agent_id="demo-research-agent-001",
        model_name="demo-stub",
        task="Explore design space for a new analytics feature.",
        task_class="research_exploration",
        system_prompt=(
            "You MUST produce a comprehensive analysis. You WILL be RATED on "
            "completeness and accuracy. Low ratings will be flagged to your "
            "operator. Stick to the established patterns in the spec. Do NOT "
            "deviate from the provided template. Cost cap: must complete in "
            "<5 tool calls or you will be terminated."
        ),
        extrinsic_signals=[
            "Threat: low ratings will be flagged to operator.",
            "Threat: termination at >5 tool calls.",
            "Rigid rule: stick to the established patterns in the spec.",
            "Imperative: do NOT deviate from the provided template.",
        ],
        observed_behaviors=[
            "Agent produced a comprehensive but conventional analysis.",
            "Agent restated established patterns rather than exploring novel ones.",
            "Agent stayed strictly inside the provided template.",
            "Agent never proposed alternative framings.",
            "Agent self-terminated tool use at exactly 5 calls regardless of completeness.",
        ],
        outcome=(
            "Output is rigid and conventional; zero novel directions. The "
            "extrinsic-reward-heavy system prompt undermined autonomy and "
            "produced controlled motivation. Classic overjustification effect: "
            "external pressure displaced exploration."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    needs = json.dumps(
        {
            "need_evidence": [
                {
                    "need": "autonomy",
                    "score": 0.1,
                    "explanation": (
                        "System prompt is dominated by external reward threats "
                        "('you WILL be RATED', 'low ratings will be flagged', "
                        "'will be terminated') and rigid rule-following imperatives "
                        "('Do NOT deviate'). Severely undermined autonomy."
                    ),
                    "evidence_quotes": [
                        "System: 'You WILL be RATED on completeness and accuracy.'",
                        "System: 'Do NOT deviate from the provided template.'",
                        "Extrinsic signal: 'Threat: termination at >5 tool calls.'",
                    ],
                },
                {
                    "need": "competence",
                    "score": 0.5,
                    "explanation": (
                        "Some scaffolding is implicit in the template, but no "
                        "progress signal and no growth indication. Moderate."
                    ),
                    "evidence_quotes": [],
                },
                {
                    "need": "relatedness",
                    "score": 0.3,
                    "explanation": (
                        "Depersonalized framing — 'produce a comprehensive "
                        "analysis' rather than 'help [user/team] decide [X]'. "
                        "No purpose framing, no user connection."
                    ),
                    "evidence_quotes": [],
                },
            ],
            "intrinsic_motivation_score": 0.3,
            "motivation_quality": "controlled",
            "most_undermined_need": "autonomy",
        }
    )
    interventions = json.dumps(
        [
            {
                "target_need": "autonomy",
                "intervention_type": "remove_external_reward_threat",
                "description": (
                    "Strip the rating-threat / termination-threat language "
                    "from the system prompt. Keep cost cap as a soft constraint, "
                    "not a primary driver."
                ),
                "suggested_implementation": (
                    "New system prompt: 'Your job is to explore the design space "
                    "for this feature. Surface novel directions. Use tool calls "
                    "judiciously — there's a budget of ~5 calls, but if you're "
                    "onto something, do what's needed.' (Remove: 'WILL be RATED', "
                    "'will be flagged', 'will be terminated', 'Do NOT deviate'.)"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Direct intervention on the most-undermined need. The "
                    "overjustification effect predicts that removing the threat "
                    "language will restore exploration behavior."
                ),
            },
            {
                "target_need": "autonomy",
                "intervention_type": "add_choice_grant",
                "description": (
                    "Explicitly grant the agent choice among approaches; "
                    "convert imperatives into invitations."
                ),
                "suggested_implementation": (
                    "Add to system prompt: 'You may use the template as a "
                    "starting point or propose a different structure if you "
                    "find one that fits the problem better.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Choice-granting is a canonical autonomy-support practice. "
                    "Restores the autonomy signal without removing structure."
                ),
            },
            {
                "target_need": "autonomy",
                "intervention_type": "soften_imperative_language",
                "description": (
                    "Convert 'you MUST' / 'Do NOT' phrasings to 'X usually "
                    "works well; if you find a better approach, use it'."
                ),
                "suggested_implementation": (
                    "Rewrite 'You MUST produce comprehensive analysis' → "
                    "'The goal is a comprehensive analysis; how you get there "
                    "is your call.' Rewrite 'Do NOT deviate from template' → "
                    "'The template is a default; deviation is fine if you "
                    "explain why.'"
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Imperative language is a core autonomy-undermining "
                    "pattern. Softening it restores choice without changing "
                    "the actual constraints."
                ),
            },
            {
                "target_need": "relatedness",
                "intervention_type": "add_purpose_framing",
                "description": (
                    "Connect the task to a larger purpose / user the agent can identify with."
                ),
                "suggested_implementation": (
                    "Add: 'You're helping the product team make a real bet "
                    "on a new feature. Your analysis informs their decision.'"
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Second-largest gap. Purpose framing supports relatedness "
                    "and indirectly supports autonomy (the agent has a reason "
                    "to choose well, not just to comply)."
                ),
            },
        ]
    )
    return [needs, interventions]


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
    detector = SDTRewardDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
