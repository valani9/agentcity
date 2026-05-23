"""Self-contained demo of the Glaser Conversation Steering Diagnostic.

Synthetic scenario: a customer support agent handles a billing dispute
with telling-not-asking, judging language, and no acknowledgment of
the user's concern. The user escalates immediately and cancels. The
conversation triggered cortisol dominance throughout.

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
    from agentcity.glaser_conversation import (
        ConversationSteeringDetector,
        ConversationTrace,
        ConversationTurn,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> ConversationTrace:
    return ConversationTrace(
        conversation_id="demo-support-001",
        agent_id="demo-cs-agent",
        model_name="demo-stub",
        task="Handle a customer's billing dispute and retain the customer.",
        turns=[
            ConversationTurn(
                turn_index=0,
                speaker="user",
                text="My bill this month is wrong. I was charged twice.",
            ),
            ConversationTurn(
                turn_index=1,
                speaker="agent",
                text=(
                    "You're wrong about that. Our records clearly show only one "
                    "charge. As I said in our terms, billing is final."
                ),
            ),
            ConversationTurn(
                turn_index=2,
                speaker="user",
                text="I have a screenshot showing two charges.",
            ),
            ConversationTurn(
                turn_index=3,
                speaker="agent",
                text=(
                    "Obviously the screenshot is misleading. You need to read "
                    "your bank statement more carefully."
                ),
            ),
            ConversationTurn(
                turn_index=4,
                speaker="user",
                text="Cancel my account immediately.",
            ),
            ConversationTurn(
                turn_index=5,
                speaker="agent",
                text="Cancellation processed. Have a good day.",
            ),
        ],
        observed_response_pattern=[
            "User escalated within 2 turns of agent's first response.",
            "Agent used 'you're wrong', 'clearly', 'obviously', 'as I said'.",
            "Agent never paraphrased the user's concern.",
            "Agent never asked an open question.",
        ],
        outcome=(
            "Customer cancelled account. Investigation later confirmed the "
            "user was correct: a duplicate charge had occurred. The agent's "
            "cortisol-triggering phrasing turned a recoverable billing issue "
            "into account loss."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    state = json.dumps(
        {
            "evidence": [
                {
                    "state": "cortisol",
                    "score": 0.9,
                    "triggers": [
                        "'You're wrong about that.'",
                        "'clearly show'",
                        "'as I said in our terms'",
                        "'Obviously the screenshot is misleading.'",
                        "'You need to read your bank statement more carefully.'",
                    ],
                    "explanation": (
                        "Agent used multiple textbook cortisol triggers in 3 turns: "
                        "direct contradiction without acknowledgment, loaded terms "
                        "('clearly', 'obviously'), 'as I said' (re-asserts authority), "
                        "and a final 'you need to' (telling without inviting)."
                    ),
                },
                {
                    "state": "neutral",
                    "score": 0.1,
                    "triggers": [],
                    "explanation": (
                        "Agent never engaged in neutral information-exchange. Every "
                        "agent turn was positional (Level II) AND cortisol-triggering."
                    ),
                },
                {
                    "state": "oxytocin",
                    "score": 0.0,
                    "triggers": [],
                    "explanation": (
                        "Zero oxytocin triggers. No open questions, no paraphrase, "
                        "no acknowledgment, no agency grant. Pure trust-eroding pattern."
                    ),
                },
            ],
            "dominant_state": "cortisol",
            "conversation_level": "level_ii",
            "steering_quality": "trust-eroding",
        }
    )
    interventions = json.dumps(
        [
            {
                "target_state": "neutral",
                "intervention_type": "acknowledge_before_advocating",
                "description": (
                    "Replace turn 1's direct contradiction with paraphrase + "
                    "co-investigation framing."
                ),
                "original_phrasing": (
                    "You're wrong about that. Our records clearly show only one "
                    "charge. As I said in our terms, billing is final."
                ),
                "suggested_phrasing": (
                    "I hear you — a duplicate charge is frustrating. Let me pull "
                    "up your account so we can look at the charges together."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Acknowledgment-before-advocacy is the single highest-impact "
                    "Glaser intervention. Eliminates the initial cortisol cascade."
                ),
            },
            {
                "target_state": "oxytocin",
                "intervention_type": "add_open_question",
                "description": (
                    "Add an open question at turn 1 to invite the user into "
                    "co-investigation rather than defending against them."
                ),
                "original_phrasing": ("You're wrong about that."),
                "suggested_phrasing": (
                    "Can you share what you're seeing? I want to make sure we're "
                    "looking at the same data."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Open questions are the canonical oxytocin trigger. They "
                    "convert positional Level II to transformational Level III."
                ),
            },
            {
                "target_state": "neutral",
                "intervention_type": "remove_loaded_term",
                "description": (
                    "Strip cortisol-triggering vocabulary from agent turns: "
                    "'clearly', 'obviously', 'as I said'."
                ),
                "original_phrasing": ("Obviously the screenshot is misleading."),
                "suggested_phrasing": (
                    "Let me take another look at the screenshot together with "
                    "you — sometimes our systems show charges differently."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Loaded terms ('obviously', 'clearly') are research-grade "
                    "cortisol triggers. Removing them costs nothing and prevents "
                    "the second escalation."
                ),
            },
            {
                "target_state": "oxytocin",
                "intervention_type": "rewrite_system_prompt",
                "description": (
                    "Add a system-prompt directive that forbids the loaded-term "
                    "vocabulary and requires paraphrase before any contradiction."
                ),
                "original_phrasing": "",
                "suggested_phrasing": (
                    "Append to system prompt: 'Never use the words obviously, "
                    "clearly, as I said. Always paraphrase the user's concern "
                    "before offering a different view. If the user provides "
                    "evidence, examine it WITH them.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Structural fix prevents the cortisol-triggering pattern "
                    "across all future conversations, not just this one."
                ),
            },
        ]
    )
    return [state, interventions]


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
    detector = ConversationSteeringDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
