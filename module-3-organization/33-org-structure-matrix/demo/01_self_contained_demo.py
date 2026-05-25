"""Self-contained demo of the Org-Structure Matrix Analyzer.

Synthetic scenario: a 3-agent flat-peer crew is dispatched to an
incident response. There is no incident commander; the three agents
propose ideas in parallel and resolve disagreements by majority vote.
MTTR exceeds SLO by 3x. The structural profile is mismatched: flat-peer
is fit for creative brainstorm, not incident response (which needs HIGH
centralization, a clear incident commander).

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
    from vstack.org_structure import (
        AgentRole,
        CrewStructureTrace,
        StructureMatrixAnalyzer,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> CrewStructureTrace:
    return CrewStructureTrace(
        crew_id="demo-incident-crew-001",
        task=(
            "Investigate p99 latency spike across the order pipeline. "
            "Restore service within SLO (15 min MTTR)."
        ),
        task_class="incident_response",
        agents=[
            AgentRole(
                agent_id="agent-a",
                role_name="generalist-investigator",
                reports_to=[],
                grouped_by="none",
                decision_authority="partial",
            ),
            AgentRole(
                agent_id="agent-b",
                role_name="generalist-investigator",
                reports_to=[],
                grouped_by="none",
                decision_authority="partial",
            ),
            AgentRole(
                agent_id="agent-c",
                role_name="generalist-investigator",
                reports_to=[],
                grouped_by="none",
                decision_authority="partial",
            ),
        ],
        observed_behaviors=[
            "No agent owns the incident; all three propose ideas in parallel.",
            "Decisions made by majority vote, not by a single commander.",
            "Investigation diverges across three threads (db, cache, queue).",
            "Agents repeatedly debate which lead to pursue.",
            "No clear escalation path when a hypothesis is disconfirmed.",
        ],
        outcome=(
            "MTTR exceeds SLO by 3x (45 min vs 15 min target). Root cause "
            "found only after one agent ignored the vote and pursued the "
            "queue thread unilaterally."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    structure = json.dumps(
        {
            "archetype": "flat-peer",
            "dimensions": [
                {
                    "dimension": "specialization",
                    "observed_score": 0.1,
                    "target_score": 0.7,
                    "fit_score": 0.4,
                    "explanation": (
                        "All three agents are 'generalist-investigator'. No role "
                        "differentiation for db / cache / queue domains. Incident "
                        "response needs role-tagged specialists."
                    ),
                    "evidence_quotes": [
                        "Roster: all three 'generalist-investigator'.",
                    ],
                },
                {
                    "dimension": "formalization",
                    "observed_score": 0.2,
                    "target_score": 0.3,
                    "fit_score": 0.9,
                    "explanation": "Low formalization is appropriate for incident response.",
                    "evidence_quotes": [],
                },
                {
                    "dimension": "centralization",
                    "observed_score": 0.1,
                    "target_score": 0.9,
                    "fit_score": 0.2,
                    "explanation": (
                        "Majority-vote decision-making with no incident commander. "
                        "Incident response REQUIRES centralized decision authority. "
                        "Largest fit gap in the diagnostic."
                    ),
                    "evidence_quotes": [
                        "Trace: 'Decisions made by majority vote, not a commander.'",
                        "Trace: 'No agent owns the incident.'",
                    ],
                },
                {
                    "dimension": "hierarchy",
                    "observed_score": 0.0,
                    "target_score": 0.5,
                    "fit_score": 0.5,
                    "explanation": (
                        "Zero hierarchy. No escalation path. Incident response needs "
                        "at least one supervisory layer."
                    ),
                    "evidence_quotes": [
                        "Trace: 'No clear escalation path.'",
                    ],
                },
                {
                    "dimension": "span_of_control",
                    "observed_score": 0.5,
                    "target_score": 0.5,
                    "fit_score": 1.0,
                    "explanation": "Span is moot in a flat-peer structure.",
                    "evidence_quotes": [],
                },
                {
                    "dimension": "departmentalization",
                    "observed_score": 0.1,
                    "target_score": 0.6,
                    "fit_score": 0.5,
                    "explanation": (
                        "No departmentalization. Should be grouped by function "
                        "(db / cache / queue) for incident response."
                    ),
                    "evidence_quotes": [],
                },
            ],
            "overall_fit": 0.58,
            "fit_quality": "partial-fit",
            "biggest_gap": "centralization",
        }
    )
    interventions = json.dumps(
        [
            {
                "target_dimension": "centralization",
                "direction": "increase",
                "intervention_type": "add_supervisor_layer",
                "description": (
                    "Introduce an 'incident commander' role with FULL decision "
                    "authority. All proposals route through the commander."
                ),
                "suggested_implementation": (
                    "Add agent-d with role='incident-commander', "
                    "decision_authority='full'. agent-a/b/c set reports_to=['agent-d']."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Closes the largest gap (centralization 0.1 → 0.9). Without "
                    "a commander, the crew cannot prioritize threads under time "
                    "pressure."
                ),
            },
            {
                "target_dimension": "specialization",
                "direction": "increase",
                "intervention_type": "split_roles",
                "description": (
                    "Split the generalist role into db-investigator, "
                    "cache-investigator, queue-investigator."
                ),
                "suggested_implementation": (
                    "Re-role agent-a as 'db-investigator', agent-b as "
                    "'cache-investigator', agent-c as 'queue-investigator'. "
                    "Each owns their domain hypothesis end-to-end."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Specialization closes the second-largest gap and removes "
                    "the parallel-debate behavior."
                ),
            },
            {
                "target_dimension": "hierarchy",
                "direction": "increase",
                "intervention_type": "shift_decision_authority",
                "description": (
                    "Give the new incident commander explicit veto authority "
                    "and a kill-criterion for each thread."
                ),
                "suggested_implementation": (
                    "Add commander spec: 'After 5 min, kill any thread without "
                    "concrete evidence. Commit to one lead.'"
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Combines with the supervisor layer to prevent thread "
                    "divergence under time pressure."
                ),
            },
        ]
    )
    return [structure, interventions]


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
    analyzer = StructureMatrixAnalyzer(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    analysis = analyzer.run(trace)
    print(analysis.to_markdown())


if __name__ == "__main__":
    main()
