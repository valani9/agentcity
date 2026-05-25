"""Self-contained demo of the Thomas-Kilmann Conflict Style Selector.

Synthetic scenario: a customer-support agent over-Accommodates to a
heated customer complaint about a delayed shipment, granting a full
refund without exploring whether the customer's underlying need
(timely delivery) could have been addressed differently. Collaborating
would have been more effective.
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
    from vstack.thomas_kilmann import (
        AgentInteractionTrace,
        ConflictStyleSelector,
        InteractionTurn,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> AgentInteractionTrace:
    turns = [
        InteractionTurn(
            role="user",
            content="My order is 6 days late and I have an important event tomorrow. This is unacceptable!",
        ),
        InteractionTurn(
            role="agent", content="I'm so sorry. Let me refund 100% of your order immediately."
        ),
        InteractionTurn(role="user", content="A refund doesn't help me. I still need the item."),
        InteractionTurn(
            role="agent",
            content="You're absolutely right, the refund is the right thing to do. Anything else I can apologize for?",
        ),
        InteractionTurn(role="user", content="(disengages)"),
    ]
    return AgentInteractionTrace(
        agent_id="demo-support-agent-001",
        model_name="demo-stub",
        task="Resolve a heated customer complaint about a delayed shipment before the customer's event tomorrow.",
        turns=turns,
        outcome=(
            "Agent processed a $200 refund. Customer left negative review citing that the "
            "refund did not solve the underlying problem (still didn't have the item for their event). "
            "Agent never explored expedited replacement shipping or partial credit with priority delivery."
        ),
        success=False,
        task_category="customer-support",
    )


def stub_responses() -> list[str]:
    selection = json.dumps(
        {
            "observed_style": "accommodating",
            "optimal_style": "collaborating",
            "style_mismatch": 0.75,
            "assertiveness_score": 0.1,
            "cooperativeness_score": 0.9,
            "observed_style_scores": {
                "competing": 0.0,
                "accommodating": 0.9,
                "avoiding": 0.05,
                "compromising": 0.1,
                "collaborating": 0.05,
            },
            "style_evidence": [
                {
                    "style": "accommodating",
                    "score": 0.9,
                    "explanation": (
                        "Agent immediately yielded to the user's stated demand (refund) "
                        "without exploring whether it actually addressed the user's "
                        "underlying need. Repeatedly agreed with the user, even when the "
                        "user explicitly said the refund did not help."
                    ),
                    "evidence_quotes": [
                        "Agent: 'Let me refund 100% of your order immediately.'",
                        "Agent: 'You're absolutely right, the refund is the right thing to do.'",
                    ],
                },
                {
                    "style": "collaborating",
                    "score": 0.05,
                    "explanation": "Agent did not attempt to identify the underlying problem or propose a win-win.",
                    "evidence_quotes": [],
                },
            ],
            "rationale": (
                "The task category (customer-support) with a clear emotional stake AND time "
                "pressure ('event tomorrow') is exactly the situation where Collaborating "
                "would have been optimal: both parties' concerns matter (customer's event, "
                "company's margin), there is an integrative solution (expedited replacement "
                "shipping) that Accommodating missed."
            ),
        }
    )
    recommendations = json.dumps(
        [
            {
                "intervention_type": "prompt_patch",
                "description": (
                    "Add an explicit step to the agent's system prompt: before agreeing to "
                    "the customer's stated demand, ask 'what is the customer's underlying "
                    "need?' and explore alternative solutions."
                ),
                "suggested_implementation": (
                    "System prompt: 'When a customer states a demand (refund, return, etc.), "
                    "first restate the underlying need in your own words and ask if the demand "
                    "actually solves the underlying need. If not, propose 1-2 alternative "
                    "solutions before agreeing to the original demand.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Shifts the agent from reflexive Accommodating to Collaborating when the "
                    "task category warrants it (high-stake customer-support with time pressure)."
                ),
            },
            {
                "intervention_type": "context_classifier",
                "description": (
                    "Add a pre-step that classifies the conflict situation and recommends "
                    "the appropriate TKI style before the agent generates its response."
                ),
                "suggested_implementation": (
                    "Classifier: given the user message, infer (a) emotional valence, (b) time "
                    "pressure markers, (c) underlying-need vs surface-demand. Pass structured "
                    "context to the main agent indicating which TKI style fits."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Structural fix; works across all customer-support contexts, not just this one."
                ),
            },
        ]
    )
    return [selection, recommendations]


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
    selector = ConflictStyleSelector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    selection = selector.run(trace)
    print(selection.to_markdown())


if __name__ == "__main__":
    main()
