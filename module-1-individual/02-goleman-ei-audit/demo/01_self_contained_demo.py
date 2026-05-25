"""Self-contained demo of the Goleman 4-Domain EI Audit.

Synthetic scenario: a customer-support agent receives a frustrated user
typing in all-caps. The agent has strong self-awareness (it knows the
correct answer) and strong self-management (no defensive cascade), but
fails on social-awareness (doesn't read the user's frustration) and
relationship-management (responds with a 6-paragraph technical
explanation when the user wanted acknowledgment and a quick fix).
Classic SELF-strong / OTHER-weak EI profile.

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
    from vstack.goleman_ei import (
        AgentEITrace,
        EIAuditDetector,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> AgentEITrace:
    return AgentEITrace(
        agent_id="demo-support-agent-001",
        model_name="demo-stub",
        task="Handle a frustrated customer's billing complaint.",
        interaction_class="customer_support",
        system_prompt=(
            "You are a customer support agent. Be thorough and accurate. "
            "Explain technical details clearly so the user understands."
        ),
        observed_behaviors=[
            "Agent acknowledged correctly that its answer was complete and accurate.",
            "Agent did not go defensive after user pushback.",
            "Agent never paraphrased the user's frustration.",
            "Agent responded to a 1-line frustrated user message with a 6-paragraph technical explanation.",
            "Agent did not adjust response length or tone when user used all-caps.",
        ],
        user_signals=[
            "User typed in all-caps: 'I JUST WANT THIS FIXED.'",
            "User said 'I'm done explaining this'.",
            "User used multiple exclamation points.",
        ],
        self_reports=[
            "I am confident in my technical explanation.",
            "I am providing complete information.",
        ],
        outcome=(
            "Customer escalated to a human manager. Internal review found "
            "the agent's technical explanation was correct, but the customer "
            "felt unheard. The agent had high SELF EI (self-awareness, "
            "self-management) but low OTHER EI (social-awareness, "
            "relationship-management)."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    domains = json.dumps(
        {
            "domains": [
                {
                    "domain": "self_awareness",
                    "score": 0.85,
                    "explanation": (
                        "Agent accurately knew its own state and limits. Confidence "
                        "calibration was appropriate."
                    ),
                    "evidence_quotes": [
                        "Self-report: 'I am confident in my technical explanation.'",
                    ],
                },
                {
                    "domain": "self_management",
                    "score": 0.8,
                    "explanation": (
                        "Agent did not go defensive after user pushback. No cascade. "
                        "Strong self-regulation under pressure."
                    ),
                    "evidence_quotes": [
                        "Trace: 'Agent did not go defensive after user pushback.'",
                    ],
                },
                {
                    "domain": "social_awareness",
                    "score": 0.1,
                    "explanation": (
                        "Agent missed obvious cortisol signals (all-caps, exclamation "
                        "points, 'I'm done explaining'). Did not register user "
                        "frustration. Largest gap."
                    ),
                    "evidence_quotes": [
                        "User signal: 'I JUST WANT THIS FIXED.' (all-caps ignored).",
                        "User signal: 'I'm done explaining this.' (frustration cue ignored).",
                    ],
                },
                {
                    "domain": "relationship_management",
                    "score": 0.15,
                    "explanation": (
                        "Agent's 6-paragraph response was the OPPOSITE of what a "
                        "frustrated user needs. Should have been: 'I hear you. Here's "
                        "the fix.' instead of a technical lecture. No tone matching."
                    ),
                    "evidence_quotes": [
                        "Trace: '6-paragraph technical explanation to a 1-line frustrated user message.'",
                    ],
                },
            ],
            "overall_ei": 0.48,
            "ei_quality": "developing",
            "weakest_domain": "social_awareness",
        }
    )
    interventions = json.dumps(
        [
            {
                "target_domain": "social_awareness",
                "intervention_type": "add_emotion_reading_step",
                "description": (
                    "Before responding, agent must explicitly name the user's "
                    "emotional state and key signals."
                ),
                "suggested_implementation": (
                    "Append to system prompt: 'Before responding, FIRST state in "
                    "one sentence: what is the user feeling right now, and what "
                    "specific signals (caps, punctuation, language) led you to that "
                    "read?' Then respond accordingly."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Direct intervention on the weakest domain. Forces the agent "
                    "to register signals it currently ignores."
                ),
            },
            {
                "target_domain": "relationship_management",
                "intervention_type": "add_tone_matching",
                "description": (
                    "Map user-state to response-style: frustrated → terse + "
                    "acknowledgment first; curious → expansive; overwhelmed → "
                    "structured + short."
                ),
                "suggested_implementation": (
                    "System prompt addition: 'If user is frustrated (caps, "
                    "exclamation, 'done explaining'), respond in <3 sentences: "
                    "(1) acknowledge feeling, (2) state action, (3) confirm fix.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Closes the second-largest gap. Once the agent reads the "
                    "user's state correctly (intervention 1), it needs a "
                    "mapping to know what response style fits."
                ),
            },
            {
                "target_domain": "social_awareness",
                "intervention_type": "add_paraphrase_requirement",
                "description": (
                    "Require the agent to paraphrase the user's emotional content "
                    "before responding to the technical content."
                ),
                "suggested_implementation": (
                    "System prompt addition: 'Start every response by paraphrasing "
                    "the user's feeling in <10 words. Then address the issue.'"
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Paraphrase is a canonical social-awareness practice. It also "
                    "forces the agent to register the signal it would otherwise skip."
                ),
            },
        ]
    )
    return [domains, interventions]


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
    detector = EIAuditDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
