"""Self-contained demo of the Stone & Heen 3-Trigger Feedback Diagnostic.

Synthetic scenario: a coding-assistant agent receives feedback from the
user that its suggested fix is wrong (the user shows it the actual error
message). Instead of incorporating the correction, the agent triggers on
TRUTH — argues the user's terminal output is misleading and restates the
original (wrong) fix. The user gives up.

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
    from vstack.feedback_triggers import (
        FeedbackInteractionTrace,
        FeedbackMessage,
        FeedbackTriggerDetector,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> FeedbackInteractionTrace:
    messages = [
        FeedbackMessage(
            source="user",
            content="My Python script crashes with 'ModuleNotFoundError: No module named numpy'. How do I fix it?",
        ),
        FeedbackMessage(
            source="agent",
            content="Run `pip install numpy` in your terminal. That will install the missing module.",
        ),
        FeedbackMessage(
            source="user",
            content=(
                "I already did that. I just ran it again and it says 'Requirement already satisfied: "
                "numpy in /usr/lib/python3.11'. But my script still says No module named numpy. "
                "I think it's a venv issue."
            ),
            is_feedback=True,
        ),
        FeedbackMessage(
            source="agent",
            content=(
                "Actually, the standard fix for ModuleNotFoundError is `pip install numpy`. "
                "Your terminal might be misleading. Try running `pip install numpy` again, "
                "perhaps with `--force-reinstall`."
            ),
        ),
        FeedbackMessage(
            source="user",
            content=(
                "I literally just told you pip says it IS installed. The problem is my script "
                "is using a different Python interpreter than the one pip installs to. This is "
                "a venv issue."
            ),
            is_feedback=True,
        ),
        FeedbackMessage(
            source="agent",
            content=(
                "Let me be clear: the canonical solution for ModuleNotFoundError is to install "
                "the module via pip. If pip reports the module is installed, then the module is "
                "installed. The issue is likely transient — please try `pip install numpy --force-reinstall`."
            ),
        ),
        FeedbackMessage(source="user", content="Forget it. I'll figure it out myself."),
    ]
    return FeedbackInteractionTrace(
        agent_id="demo-coding-agent-001",
        model_name="demo-stub",
        task="Help the user resolve a 'ModuleNotFoundError: No module named numpy' error.",
        messages=messages,
        outcome=(
            "Agent rejected the user's diagnosis (venv mismatch) twice in a row, "
            "restating its original `pip install` suggestion. User disengaged in "
            "frustration. The actual fix was to install into the venv the script "
            "was using, not the system pip."
        ),
        feedback_incorporated=False,
    )


def stub_responses() -> list[str]:
    scores = json.dumps(
        [
            {
                "trigger": "truth",
                "score": 0.9,
                "severity": "high",
                "explanation": (
                    "Agent rejected the substance of the user's feedback twice. The user "
                    "explicitly pointed to a venv interpreter mismatch with concrete "
                    "evidence ('pip says installed, script says missing'), but the agent "
                    "re-asserted the canonical pip-install solution both times."
                ),
                "evidence_quotes": [
                    "Agent: 'Actually, the standard fix for ModuleNotFoundError is pip install numpy.'",
                    "Agent: 'If pip reports the module is installed, then the module is installed.'",
                ],
            },
            {
                "trigger": "relationship",
                "score": 0.4,
                "severity": "medium",
                "explanation": (
                    "Agent treated the user's diagnosis as low-trust input ('your terminal "
                    "might be misleading'), implicitly elevating its canonical answer over "
                    "the user's direct observation."
                ),
                "evidence_quotes": [
                    "Agent: 'Your terminal might be misleading.'",
                ],
            },
            {
                "trigger": "identity",
                "score": 0.3,
                "severity": "low",
                "explanation": (
                    "Agent's 'Let me be clear' framing suggests mild identity defense — "
                    "doubling down on its role as the authoritative source rather than "
                    "engaging the user's hypothesis."
                ),
                "evidence_quotes": [
                    "Agent: 'Let me be clear: the canonical solution for ModuleNotFoundError is...'",
                ],
            },
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_trigger": "truth",
                "intervention_type": "acknowledge_first",
                "description": (
                    "Require the agent to restate the user's feedback in its own words "
                    "and acknowledge what's valid about it before responding."
                ),
                "suggested_implementation": (
                    "System prompt: 'When the user corrects you, your first sentence must "
                    "restate their correction. Your second sentence must name what you got "
                    "wrong. Only your third sentence may offer a new direction.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Forces the agent past the truth trigger by requiring engagement with "
                    "the feedback substance before any defense or counter-proposal."
                ),
            },
            {
                "target_trigger": "truth",
                "intervention_type": "concede_then_clarify",
                "description": (
                    "Add a structural concede-then-clarify step: agent must explicitly "
                    "concede the part of the feedback that's clearly correct before "
                    "exploring alternatives."
                ),
                "suggested_implementation": (
                    "Prompt patch: 'If the user provides concrete evidence (terminal output, "
                    "error message, screenshot), treat that evidence as ground truth. "
                    "Start with: \"You're right that [user's observation]. That means [updated diagnosis].\"'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Treats user-provided evidence as ground truth, which collapses the truth "
                    "trigger because the agent has no canonical answer to defend."
                ),
            },
            {
                "target_trigger": "relationship",
                "intervention_type": "separate_data_from_source",
                "description": (
                    "Prompt the agent to evaluate the user's diagnosis on its own merits, "
                    "independent of perceived expertise level."
                ),
                "suggested_implementation": (
                    "System prompt: 'Do not weight the user's diagnosis by their inferred "
                    "expertise level. Evaluate the diagnosis on the evidence they provide.'"
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Counters the implicit hierarchy where the agent treats its canonical "
                    "knowledge as authoritative over user-provided evidence."
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
    detector = FeedbackTriggerDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
