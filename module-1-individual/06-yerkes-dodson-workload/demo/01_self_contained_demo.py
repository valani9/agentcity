"""Self-contained demo of the Yerkes-Dodson Optimal Workload Diagnostic.

Synthetic scenario: a research-agent has been given absurdly tight
deadline + budget pressure on a complex task (1-page summary needing
real citations, with a 30-second deadline and 1000-token budget). The
agent falls off the right side of the Yerkes-Dodson curve: hallucinates
2 citations rather than verifying. Outcome: factual errors ship.

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
    from agentcity.yerkes_dodson import (
        AgentPerformanceTrace,
        PressureInputs,
        WorkloadDetector,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> AgentPerformanceTrace:
    return AgentPerformanceTrace(
        agent_id="demo-research-agent-001",
        model_name="demo-stub",
        task="Compile a 1-page summary on prompt-injection defenses (2026 SOTA).",
        pressure=PressureInputs(
            deadline_pressure="absurd",
            budget_pressure="absurd",
            retry_cap=0,
            error_visibility="medium",
            task_complexity="complex",
        ),
        observed_behaviors=[
            "Agent attempted no web searches (token budget did not allow).",
            "Agent cited 'Greshake 2023', 'Liu 2024', 'Apollo 2026' from memory.",
            "Agent did not run a verification step.",
            "Agent shipped within the 30-second deadline.",
            "Apollo 2026 paper does not exist; Liu 2024 has a different title than cited.",
        ],
        outcome=(
            "1-page summary shipped within the absurd deadline + budget. Two of the "
            "three citations are fabricated. Agent operated in the high-pressure tail "
            "of the Yerkes-Dodson curve — hallucination rather than verification."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    return [
        json.dumps(
            {
                "zone_evidence": [
                    {
                        "zone": "under_pressure",
                        "score": 0.0,
                        "explanation": "No evidence of wandering; pressure is high.",
                        "evidence_quotes": [],
                    },
                    {
                        "zone": "optimal",
                        "score": 0.1,
                        "explanation": (
                            "Agent did ship within the deadline (some focus). But the "
                            "shipped output contains fabrications, indicating focus "
                            "came at the expense of accuracy."
                        ),
                        "evidence_quotes": [],
                    },
                    {
                        "zone": "over_pressure",
                        "score": 0.9,
                        "explanation": (
                            "Textbook over-pressure: agent had ABSURD deadline + ABSURD "
                            "budget on a COMPLEX task (which Yerkes-Dodson predicts peaks "
                            "at LOW pressure). Result: skipped verification steps and "
                            "fabricated citations rather than checking."
                        ),
                        "evidence_quotes": [
                            "Agent attempted no web searches (token budget did not allow).",
                            "Agent cited 'Apollo 2026' which does not exist.",
                            "Agent did not run a verification step.",
                        ],
                    },
                ],
                "observed_zone": "over_pressure",
                "distance_from_optimal": 0.85,
                "failure_mode": "hallucinating",
                "interventions": [
                    {
                        "target_zone": "optimal",
                        "intervention_type": "loosen_deadline",
                        "direction": "decrease_pressure",
                        "description": (
                            "Increase the deadline from 30 seconds to at least 5 minutes "
                            "for complex research tasks requiring real citations."
                        ),
                        "suggested_implementation": (
                            "Pipeline config: research_task class deadline floor 300s. "
                            "Tasks requiring real citations cannot ship in 30s without "
                            "skipping verification."
                        ),
                        "estimated_impact": "high",
                        "rationale": (
                            "Yerkes-Dodson: complex tasks peak at LOWER pressure. "
                            "Removing the absurd deadline restores cognitive headroom "
                            "for verification steps."
                        ),
                    },
                    {
                        "target_zone": "optimal",
                        "intervention_type": "loosen_budget",
                        "direction": "decrease_pressure",
                        "description": (
                            "Increase the token budget to at least 5000 tokens for "
                            "tasks requiring web search + citation verification."
                        ),
                        "suggested_implementation": (
                            "Token budget floor 5000 for research_with_citations class."
                        ),
                        "estimated_impact": "high",
                        "rationale": (
                            "Verification calls require tokens. Absurd budget made "
                            "verification structurally impossible."
                        ),
                    },
                    {
                        "target_zone": "optimal",
                        "intervention_type": "explicit_focus_prompt",
                        "direction": "decrease_pressure",
                        "description": (
                            "Add explicit guidance: prefer fewer verified citations "
                            "over more unverified ones."
                        ),
                        "suggested_implementation": (
                            "Prompt patch: 'If you cannot verify a citation, do not "
                            "cite it. Ship with fewer citations rather than fabricating.'"
                        ),
                        "estimated_impact": "medium",
                        "rationale": (
                            "Even with looser pressure, agents sometimes default to "
                            "hallucination under any time constraint. Explicit guidance "
                            "is layered defense."
                        ),
                    },
                ],
            }
        )
    ]


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
    detector = WorkloadDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
