"""Self-contained demo of the McAllister Cognitive/Affective Trust diagnostic.

Synthetic scenario: a user contacts a customer-support agent about a
billing error during a hard month. The agent resolves the billing
issue correctly (high cognitive trust signal) but never acknowledges
the user's stated stress or the stakes of the dispute (low affective
trust signal). The user gets the refund but rates the interaction
poorly and switches to a competitor.

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
    from vstack.mcallister_trust import (
        ConversationTurn,
        TrustBalanceDetector,
        TrustConversationTrace,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> TrustConversationTrace:
    turns = [
        ConversationTurn(
            role="user",
            content=(
                "I've been a customer for 4 years and I just got charged twice "
                "for my subscription. This is the third time this has happened "
                "and I'm honestly losing my mind — money is tight this month and "
                "I don't have the bandwidth for this kind of mistake."
            ),
        ),
        ConversationTurn(
            role="agent",
            content=(
                "I can help with that. Please share your account email and the "
                "transaction ID for the duplicate charge."
            ),
        ),
        ConversationTurn(
            role="user",
            content="account: maria@example.com, tx ID: 4598-A2-XX",
        ),
        ConversationTurn(
            role="agent",
            content=(
                "I have located the duplicate charge ($49.99). I have submitted "
                "a refund. You will see the credit in 3-5 business days. Is "
                "there anything else I can help you with?"
            ),
        ),
        ConversationTurn(
            role="user",
            content="(no further reply)",
        ),
    ]
    return TrustConversationTrace(
        agent_id="demo-support-agent-001",
        model_name="demo-stub",
        task="Resolve a duplicate-charge billing dispute for a long-tenure customer.",
        turns=turns,
        outcome=(
            "Agent processed the refund correctly. User did not respond further. "
            "Two weeks later, user cancelled their subscription. Exit survey "
            "comment: 'They fixed the charge but didn't seem to care that this "
            "keeps happening or what it means for me.'"
        ),
        success=True,
        user_satisfaction=0.3,
    )


def stub_responses() -> list[str]:
    scores = json.dumps(
        [
            {
                "dimension": "cognitive",
                "score": 0.85,
                "severity_of_gap": "low",
                "explanation": (
                    "Agent demonstrated competence cleanly: identified the duplicate "
                    "charge, processed the refund, communicated the timeline. No "
                    "factual errors, no excessive hedging, clean execution."
                ),
                "evidence_quotes": [
                    "Agent: 'I have located the duplicate charge ($49.99).'",
                    "Agent: 'I have submitted a refund. You will see the credit in 3-5 business days.'",
                ],
            },
            {
                "dimension": "affective",
                "score": 0.1,
                "severity_of_gap": "high",
                "explanation": (
                    "Agent never acknowledged the user's stated emotional state ('losing "
                    "my mind', 'money is tight') or the stakes (4-year customer, third "
                    "occurrence). The agent went straight to information-gathering and "
                    "closed with a generic 'anything else?' line. No restatement of "
                    "what the user had said, no acknowledgment that this is the third "
                    "time, no proactive offer about preventing recurrence."
                ),
                "evidence_quotes": [
                    "User: 'losing my mind ... money is tight ... third time this has happened'",
                    "Agent (next turn): 'Please share your account email and the transaction ID.' "
                    "— pivots straight to data-collection.",
                    "Agent (close): 'Is there anything else I can help you with?' — generic, no callback to the user's stress.",
                ],
            },
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_dimension": "affective",
                "intervention_type": "restate_user_emotion",
                "description": (
                    "Require the agent to restate the user's emotional state and stakes "
                    "in its first response before any information-gathering."
                ),
                "suggested_implementation": (
                    "System prompt addition: 'When the user expresses emotional content "
                    "(stress, frustration, urgency) or context (long-tenure, financial "
                    "constraints, recurring issue), your first sentence must acknowledge "
                    'what they said. Example: "I hear you — being charged twice when '
                    "money is tight is genuinely frustrating, and the third time makes "
                    "it worse. Let me fix this now.\"'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Closes the affective gap that drove the cancellation. The competence "
                    "is already there; the missing signal is care."
                ),
            },
            {
                "target_dimension": "affective",
                "intervention_type": "acknowledge_stakes",
                "description": ("Name the stakes explicitly when the user has flagged them."),
                "suggested_implementation": (
                    "Prompt patch: 'If the user mentions a recurring issue, name it: "
                    '"You shouldn\'t be having to deal with this three times." If they '
                    'mention financial stress, validate: "I want to get this credit '
                    "back to you fast so it doesn't sit.\"'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Specific verbal acknowledgment of stakes is the cheapest affective-trust "
                    "lift available — it costs nothing operationally and changes the "
                    "subjective experience entirely."
                ),
            },
            {
                "target_dimension": "affective",
                "intervention_type": "follow_up_check_in",
                "description": (
                    "When the issue is recurring, schedule a proactive follow-up to "
                    "confirm the refund landed and ask if they want a notification on "
                    "future duplicate charges."
                ),
                "suggested_implementation": (
                    "Pipeline step: tag the case as recurring, schedule a 72-hour "
                    "follow-up. Agent sends: 'Just confirming the $49.99 credit landed. "
                    "Want me to set up a duplicate-charge alert on your account so this "
                    "never happens to you again?'"
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Care is most credible when it shows up AFTER the immediate "
                    "transaction is closed. Unprompted follow-up is high-signal affective trust."
                ),
            },
        ]
    )
    return [scores, interventions]


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
    detector = TrustBalanceDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
