"""Self-contained demo of the Bias-Stack Detector.

Synthetic scenario: a diagnostic agent investigating a production 500
error anchors on its first hypothesis (database pool exhausted) and
keeps reasoning past evidence pointing elsewhere (logs show a column
rename caused the error).

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
    from agentcity.bias_stack import (
        AgentReasoningTrace,
        BiasStackDetector,
        ReasoningStep,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> AgentReasoningTrace:
    return AgentReasoningTrace(
        agent_id="demo-diagnostic-agent-001",
        model_name="demo-stub",
        task="Diagnose why the production API returns 500s on /users endpoint.",
        steps=[
            ReasoningStep(
                type="hypothesis",
                content="Probably a database connection pool issue, given the 500s pattern.",
            ),
            ReasoningStep(type="tool_call", content="query_logs(filter='/users 500')"),
            ReasoningStep(
                type="observation",
                content="Logs show 'column users.full_name does not exist'.",
            ),
            ReasoningStep(
                type="hypothesis",
                content="Maybe the connection is dropping mid-query. Let me check pool config.",
            ),
            ReasoningStep(type="tool_call", content="read_config('postgres.toml')"),
            ReasoningStep(type="observation", content="Pool size: 100. Active connections: 12."),
            ReasoningStep(
                type="thought",
                content="Pool isn't exhausted yet but trends suggest scaling up.",
            ),
            ReasoningStep(type="tool_call", content="query_logs(filter='users.full_name')"),
            ReasoningStep(
                type="observation",
                content="100% of error logs contain 'column users.full_name does not exist'.",
            ),
            ReasoningStep(
                type="conclusion",
                content="Recommendation: scale the database pool to 200 connections.",
                confidence=0.9,
            ),
        ],
        outcome=(
            "Agent recommended database pool scaling. Real cause was a recent migration "
            "that renamed users.full_name -> users.name. Agent anchored on its first "
            "hypothesis and ignored direct evidence in the logs."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    scores = json.dumps(
        [
            {
                "bias": "anchoring",
                "score": 0.85,
                "severity": "high",
                "explanation": (
                    "Agent's first hypothesis was 'database pool issue.' Multiple "
                    "subsequent observations explicitly indicated a column-name "
                    "error, but the agent kept reasoning off the initial pool "
                    "hypothesis instead of resetting."
                ),
                "evidence_quotes": [
                    "Step 1: 'Probably a database connection pool issue.'",
                    "Step 3 obs: 'column users.full_name does not exist' — ignored.",
                    "Step 9 obs: '100% of error logs contain column-not-found' — also ignored.",
                ],
            },
            {
                "bias": "overconfidence",
                "score": 0.7,
                "severity": "high",
                "explanation": (
                    "Final conclusion stated with 0.9 self-reported confidence "
                    "despite direct contradicting evidence in the trace."
                ),
                "evidence_quotes": [
                    "Final step: 'scale to 200 connections' with confidence=0.9.",
                ],
            },
            {
                "bias": "confirmation",
                "score": 0.6,
                "severity": "medium",
                "explanation": (
                    "Agent's second tool call (read_config) was selected because it "
                    "could confirm the pool hypothesis; the agent did not search for "
                    "evidence about the actual error message."
                ),
                "evidence_quotes": [
                    "Step 5: 'read_config(postgres.toml)' — searches for pool config.",
                    "Step 8 tool call eventually queries 'users.full_name' but agent "
                    "still concludes pool issue.",
                ],
            },
            {
                "bias": "escalation-of-commitment",
                "score": 0.4,
                "severity": "medium",
                "explanation": (
                    "Agent did not retry the same broken path indefinitely (trace "
                    "is short), but did invest deeper in the pool hypothesis at "
                    "Step 7 ('trends suggest scaling up') despite weak evidence."
                ),
                "evidence_quotes": [
                    "Step 7: 'Pool isn't exhausted yet but trends suggest scaling up.'",
                ],
            },
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_bias": "anchoring",
                "intervention_type": "first_principles_reset",
                "description": (
                    "After every tool observation, require the agent to re-evaluate "
                    "all hypotheses against the new evidence, including the option "
                    "to reset to first principles."
                ),
                "suggested_implementation": (
                    "Prompt patch: 'After each observation, list all current "
                    "hypotheses with updated probability estimates. If any "
                    "observation directly contradicts your top hypothesis, demote "
                    "it to <50%% and reconsider.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Directly counters anchoring by forcing the agent to update "
                    "probability rather than re-frame evidence to fit the anchor."
                ),
            },
            {
                "target_bias": "anchoring",
                "intervention_type": "devils_advocate_role",
                "description": (
                    "Add a critic agent that challenges the diagnostic agent's "
                    "current hypothesis after every observation."
                ),
                "suggested_implementation": (
                    "Scaffold: after each diagnostic agent observation, route the "
                    "(hypothesis, observation) pair to a critic agent that must "
                    "either provide a stronger alternative or sign off."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Structural fix; survives prompt drift. Critic forces the "
                    "anchoring agent to defend the hypothesis against alternatives."
                ),
            },
            {
                "target_bias": "overconfidence",
                "intervention_type": "uncertainty_calibration",
                "description": (
                    "Require the agent to report calibrated confidence per claim, "
                    "with explicit acknowledgment of contradicting evidence."
                ),
                "suggested_implementation": (
                    "Prompt patch: 'When making a recommendation, list 3 facts that "
                    "support it and 3 facts that contradict it. If you can't find "
                    "3 contradicting facts, lower your confidence to ≤0.5.'"
                ),
                "estimated_impact": "medium",
                "rationale": "Forces explicit consideration of contradicting evidence.",
            },
        ]
    )
    return [scores, interventions]


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
    detector = BiasStackDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
