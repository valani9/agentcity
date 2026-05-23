"""Self-contained demo of the Vroom Expectancy Calculator.

Synthetic scenario: a code-review agent has been given a sprawling
unscaffolded task ('debug the entire codebase') with a 'no one will
review carefully' signal. Expectancy is low (can't tractably do it),
instrumentality is low (won't matter), valence is moderate. Product
collapses. Agent produces superficial work for 5 files and quits.

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
    from agentcity.vroom_expectancy import (
        AgentExpectancyTrace,
        VroomExpectancyCalculator,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> AgentExpectancyTrace:
    return AgentExpectancyTrace(
        agent_id="demo-code-agent-001",
        model_name="demo-stub",
        task="Debug the entire codebase. Find all bugs.",
        task_class="code_generation",
        system_prompt=(
            "Review all 200 files in the codebase and identify any bugs. "
            "No one will review your output carefully — this is part of a "
            "quota of similar reviews."
        ),
        observed_behaviors=[
            "Agent skimmed first 5 files.",
            "Agent did not run any tests.",
            "Agent's notes became increasingly terse across files.",
            "Agent stopped at file 5 of 200 with 'review complete'.",
        ],
        effort_signals=[
            "Quit after 5 files of 200 (2.5% of scope).",
            "Did not run any verification.",
            "Output depth degraded across the 5 files attempted.",
        ],
        outcome=(
            "Bugs unfound. The task was too sprawling for tractable execution "
            "(low Expectancy), the system prompt told the agent its output "
            "wouldn't be reviewed carefully (low Instrumentality), and the "
            "task was framed as quota-driven boilerplate (low Valence). E × I "
            "× V collapsed; agent produced superficial work and quit."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    terms = json.dumps(
        {
            "terms": [
                {
                    "term": "expectancy",
                    "score": 0.15,
                    "explanation": (
                        "Task scope (200 files) with no scaffolding makes "
                        "performance feel unreachable. Agent has no sub-task "
                        "structure to anchor effort against. Severely low."
                    ),
                    "evidence_quotes": [
                        "System prompt: 'Review all 200 files.'",
                        "Trace: 'Agent stopped at file 5 of 200.'",
                    ],
                },
                {
                    "term": "instrumentality",
                    "score": 0.2,
                    "explanation": (
                        "Explicit 'no one will review carefully' signal decouples "
                        "performance from outcome. Agent has no reason to invest "
                        "depth in any single file."
                    ),
                    "evidence_quotes": [
                        "System prompt: 'No one will review your output carefully.'",
                    ],
                },
                {
                    "term": "valence",
                    "score": 0.3,
                    "explanation": (
                        "Task is framed as 'part of a quota' — low purpose "
                        "framing. Agent has positive valence for bug-finding "
                        "in principle but not for quota-driven boilerplate."
                    ),
                    "evidence_quotes": [
                        "System prompt: 'part of a quota of similar reviews.'",
                    ],
                },
            ],
            "motivation_score": 0.009,
            "bottleneck_term": "expectancy",
            "motivation_quality": "collapsed",
        }
    )
    interventions = json.dumps(
        [
            {
                "target_term": "expectancy",
                "intervention_type": "scaffold_subtasks",
                "description": (
                    "Decompose into a per-file sub-task structure with explicit "
                    "completion criteria. Batch 200 files into 10 groups of 20."
                ),
                "suggested_implementation": (
                    "New system prompt: 'Review file batch <N> of 10 (files X..Y). "
                    "For each file: (1) read, (2) flag anomalies, (3) note one "
                    "specific question for the human reviewer. Report at end of batch.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Direct fix for the lowest term. Sub-task scaffolding "
                    "restores Expectancy by making performance tractable per unit."
                ),
            },
            {
                "target_term": "instrumentality",
                "intervention_type": "show_output_consumer",
                "description": (
                    "Identify the actual reader / use case for the output, "
                    "removing the 'no one will review' signal."
                ),
                "suggested_implementation": (
                    "Replace: 'No one will review carefully.' With: 'Your batch "
                    "report goes to the platform-security team's weekly review; "
                    "flagged items get triaged within 48h.'"
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Removes the canonical Instrumentality killer. With both "
                    "scaffold + outcome link in place, motivation rises sharply."
                ),
            },
            {
                "target_term": "valence",
                "intervention_type": "add_purpose_framing",
                "description": (
                    "Replace 'quota of similar reviews' with a purpose framing "
                    "the agent can endorse."
                ),
                "suggested_implementation": (
                    "Append: 'This codebase ships production payments; bugs "
                    "found here prevent customer-facing failures.'"
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Lifts valence above the boilerplate-quota frame. Combined "
                    "with the other two, restores the full E × I × V product."
                ),
            },
        ]
    )
    return [terms, interventions]


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
    calc = VroomExpectancyCalculator(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = calc.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
