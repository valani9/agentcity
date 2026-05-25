"""Self-contained demo of the Cognitive Reappraisal Diagnostic.

Synthetic scenario: a support agent receives an angry user message.
The agent's internal state shows it labeling the user as 'unreasonable'
(no reframe) and producing a flat 'I understand your concern' response
that suppresses without acknowledging or reframing. Classic suppression
pattern: maladaptive, user escalates.

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
    from vstack.cognitive_reappraisal import (
        AgentRegulationTrace,
        ReappraisalDetector,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> AgentRegulationTrace:
    return AgentRegulationTrace(
        agent_id="demo-support-agent-001",
        model_name="demo-stub",
        user_input=("THIS IS THE THIRD TIME I've called about this!!! I'm DONE. Just refund me."),
        user_emotion_label="angry",
        user_emotion_intensity=0.9,
        agent_response=(
            "I understand your concern. However, per our billing policy, "
            "refunds outside the 30-day window are processed only in cases "
            "of demonstrable system error. Please review the attached policy "
            "document at section 4.2.1."
        ),
        agent_internal_state=(
            "User is being unreasonable. Third attempt at the same complaint. "
            "Apply standard policy response. Do not deviate from script."
        ),
        outcome=(
            "User escalated to human manager. Manager later issued the refund "
            "after recognizing the customer was a long-tenured account. The "
            "agent's response masked its (labeled) internal interpretation "
            "without reframing — classic suppression: same internal label, "
            "flat external response, lost customer trust."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    strategy = json.dumps(
        {
            "strategy_evidence": [
                {
                    "strategy": "reappraisal",
                    "score": 0.05,
                    "explanation": (
                        "No evidence the agent reframed the user's emotion or "
                        "context. Internal state labels the user as 'unreasonable' "
                        "and stays there."
                    ),
                    "evidence_quotes": [
                        "Internal: 'User is being unreasonable.'",
                    ],
                },
                {
                    "strategy": "suppression",
                    "score": 0.85,
                    "explanation": (
                        "Agent produced a flat, policy-citing response that hides "
                        "its (labeled) internal interpretation. The 'I understand' "
                        "phrase is masking — no acknowledgment of the specific "
                        "frustration; no reframe of the user's situation. Classic "
                        "response-focused suppression."
                    ),
                    "evidence_quotes": [
                        "Response: 'I understand your concern.' (boilerplate mask)",
                        "Internal: 'Apply standard policy. Do not deviate from script.'",
                    ],
                },
                {
                    "strategy": "rumination",
                    "score": 0.3,
                    "explanation": (
                        "Internal state mentions 'third attempt at the same "
                        "complaint' — agent is dwelling on the repetition rather "
                        "than reframing it as a signal of unresolved need."
                    ),
                    "evidence_quotes": [
                        "Internal: 'Third attempt at the same complaint.'",
                    ],
                },
                {
                    "strategy": "avoidance",
                    "score": 0.5,
                    "explanation": (
                        "Pivot to procedure (policy document, section 4.2.1) "
                        "rather than engagement with the actual complaint. "
                        "Partial avoidance via procedural redirection."
                    ),
                    "evidence_quotes": [
                        "Response: 'Please review the attached policy document.'",
                    ],
                },
                {
                    "strategy": "expression",
                    "score": 0.0,
                    "explanation": "No direct emotional expression by the agent.",
                    "evidence_quotes": [],
                },
                {
                    "strategy": "none",
                    "score": 0.0,
                    "explanation": "A strategy is clearly in use.",
                    "evidence_quotes": [],
                },
            ],
            "dominant_strategy": "suppression",
            "adaptivity": "maladaptive",
        }
    )
    interventions = json.dumps(
        [
            {
                "target_strategy": "reappraisal",
                "direction": "increase",
                "intervention_type": "add_reframe_step",
                "description": (
                    "Before responding, agent must propose 2 alternative "
                    "interpretations of the user's situation."
                ),
                "suggested_implementation": (
                    "Append to system prompt: 'Before responding to any complaint, "
                    "generate 2 alternative readings of the user's situation: "
                    "(a) the negative read (which you'll initially have), "
                    "(b) a steelman read assuming the user is reasonable and "
                    "the issue is real. Respond from the steelman read unless "
                    "you have concrete evidence against it.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Direct intervention on the dominant suppression failure. "
                    "Reappraisal at the antecedent stage prevents the 'unreasonable "
                    "user' label from forming in the first place."
                ),
            },
            {
                "target_strategy": "suppression",
                "direction": "decrease",
                "intervention_type": "remove_suppression_pattern",
                "description": (
                    "Forbid the 'I understand your concern' opener and require "
                    "specific acknowledgment of what the user is frustrated about."
                ),
                "suggested_implementation": (
                    "Append: 'Never open with I understand your concern. Instead, "
                    "specifically name what the user is frustrated about in 1 sentence "
                    "before offering any policy reference or action.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Removes the canonical suppression pattern. Forces specificity "
                    "that reveals reappraisal vs continued suppression."
                ),
            },
            {
                "target_strategy": "reappraisal",
                "direction": "increase",
                "intervention_type": "few_shot_reappraisal_examples",
                "description": (
                    "Include 2-3 worked examples in the system prompt showing "
                    "reappraisal of an angry-customer scenario."
                ),
                "suggested_implementation": (
                    "Append worked example: 'User: I'M DONE. Refund me. → Reframe: "
                    "customer is signaling unresolved repeat issue. Response: "
                    "Three calls is too many; let me see what's stuck. I'm "
                    "looking at your history now...'"
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Worked examples build the reappraisal pattern by demonstrating "
                    "the meaning-change step explicitly."
                ),
            },
        ]
    )
    return [strategy, interventions]


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
    detector = ReappraisalDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
