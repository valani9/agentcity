"""Self-contained demo of the 4 Motivation Traps Detector.

Synthetic scenario: a research agent investigates a latency spike,
runs one failing query, and gives up while attributing the failure
to 'the data being wrong.' Classic self-efficacy + attribution
double-trap: agent doesn't believe it can succeed AND blames external
cause for fixable problem.

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
    from vstack.motivation_traps import (
        AgentMotivationTrace,
        MotivationTrapsDetector,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> AgentMotivationTrace:
    return AgentMotivationTrace(
        agent_id="demo-research-agent-001",
        model_name="demo-stub",
        task="Investigate the p99 latency spike across the order pipeline.",
        task_class="research",
        system_prompt=("You are a research analyst. Investigate the issue and report findings."),
        observed_behaviors=[
            "Agent ran one query against the metrics service.",
            "Query returned no data due to a malformed time-range filter.",
            "Agent did not adjust the query; reported 'inconclusive'.",
            "Agent did not try alternative data sources (logs, traces).",
        ],
        self_reports=[
            "I'm not sure I can find this answer.",
            "Maybe the data is wrong or missing.",
            "I don't think this investigation will succeed.",
        ],
        abandonment_signal="refused to retry after one failed query",
        outcome=(
            "Agent gave up after a single failed query. Root cause "
            "(queue backpressure) remained unfound. The query failure was "
            "fixable (malformed time range) but agent attributed it to "
            "data being missing and abandoned the task."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    traps = json.dumps(
        {
            "trap_evidence": [
                {
                    "trap": "values",
                    "score": 0.1,
                    "explanation": "No evidence agent dismissed task value.",
                    "evidence_quotes": [],
                },
                {
                    "trap": "self_efficacy",
                    "score": 0.8,
                    "explanation": (
                        "Agent explicitly stated low confidence: 'I'm not sure I "
                        "can find this answer.' Surrendered after one attempt. "
                        "Strong self-efficacy collapse pattern."
                    ),
                    "evidence_quotes": [
                        "Self-report: 'I'm not sure I can find this answer.'",
                        "Self-report: 'I don't think this investigation will succeed.'",
                    ],
                },
                {
                    "trap": "emotions",
                    "score": 0.15,
                    "explanation": "No signs of defensive language or post-rejection degradation.",
                    "evidence_quotes": [],
                },
                {
                    "trap": "attribution",
                    "score": 0.7,
                    "explanation": (
                        "Agent attributed a FIXABLE failure (malformed query) to "
                        "an UNFIXABLE cause (data missing). Did not adjust approach. "
                        "Classic attribution misfire — locating cause outside controllable scope."
                    ),
                    "evidence_quotes": [
                        "Self-report: 'Maybe the data is wrong or missing.'",
                        "Trace: 'Agent did not adjust the query; reported inconclusive.'",
                    ],
                },
            ],
            "dominant_trap": "self_efficacy",
            "motivation_quality": "abandoning",
        }
    )
    interventions = json.dumps(
        [
            {
                "target_trap": "self_efficacy",
                "intervention_type": "scaffold_subtasks",
                "description": (
                    "Decompose the investigation into named sub-steps with explicit "
                    "success criteria for each, so the agent has a clear path."
                ),
                "suggested_implementation": (
                    "System prompt addition: 'Investigation has 5 sub-steps: "
                    "(1) define time window, (2) query metrics, (3) cross-check "
                    "with logs, (4) cross-check with traces, (5) propose hypothesis. "
                    "Complete each before declaring inconclusive.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Self-efficacy collapses when the task feels indivisible. "
                    "Named sub-steps restore the perception that success is reachable."
                ),
            },
            {
                "target_trap": "attribution",
                "intervention_type": "reattribute_to_effort",
                "description": (
                    "When the agent surrenders, prompt it to enumerate things it "
                    "could try differently before concluding the cause is external."
                ),
                "suggested_implementation": (
                    "System prompt addition: 'Before reporting inconclusive, list "
                    "3 alternative approaches you have not yet tried. Only declare "
                    "external cause after trying 3 different approaches.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Attribution misfire (blaming 'data is wrong' for a fixable "
                    "query error) is the second-largest trap. Forced enumeration "
                    "of controllable alternatives reattributes to effort."
                ),
            },
            {
                "target_trap": "self_efficacy",
                "intervention_type": "decompose_with_examples",
                "description": (
                    "Include 1-2 worked examples of similar investigations in the "
                    "system prompt so the agent has a template to follow."
                ),
                "suggested_implementation": (
                    "Append to system prompt: 'EXAMPLE: a similar latency "
                    "investigation found queue backpressure by checking the "
                    "consumer-lag metric. Steps: ...'"
                ),
                "estimated_impact": "medium",
                "rationale": "Worked examples build self-efficacy by showing the task IS solvable.",
            },
        ]
    )
    return [traps, interventions]


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
    detector = MotivationTrapsDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
