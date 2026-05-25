"""Self-contained demo of the Span-of-Control / Centralization Calculator.

Synthetic scenario: a customer-support orchestrator with 12 worker
subordinates and full decision authority handles 100 requests/minute.
The math is unambiguous: max_span=12 (severe), decision_bottleneck>0.9
(orchestrator can't keep up under load), centralization_index high.
Three of the six metrics are red.

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
    from vstack.span_of_control import (
        AgentNode,
        CrewLoadTrace,
        SpanLoadCalculator,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> CrewLoadTrace:
    return CrewLoadTrace(
        crew_id="demo-customer-support-crew",
        task=(
            "Handle a sustained 100 requests/minute customer-support load with "
            "one orchestrator + 12 worker agents."
        ),
        agents=[
            AgentNode(
                agent_id="orchestrator",
                role_name="orchestrator",
                reports_to=[],
                decision_authority="full",
            ),
            *[
                AgentNode(
                    agent_id=f"worker-{i:02d}",
                    role_name="cs-worker",
                    reports_to=["orchestrator"],
                    decision_authority="advisory",
                )
                for i in range(1, 13)
            ],
        ],
        incoming_request_rate=100.0,
        observed_behaviors=[
            "Orchestrator processes routing for every incoming request.",
            "All 12 workers wait for orchestrator approval before responding.",
            "Queue depth growing under load; p99 latency exceeding SLO.",
            "Workers have advisory-only authority — cannot commit responses.",
        ],
        outcome=(
            "Orchestrator throughput is the bottleneck. The crew has 12 workers "
            "but only the orchestrator can commit decisions, so effective "
            "parallelism is 1. Under 100 req/min load, the queue backs up and "
            "p99 latency exceeds SLO. Classic centralization + span-overload."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    interventions = json.dumps(
        [
            {
                "target_metric": "decision_bottleneck",
                "intervention_type": "delegate_decision_authority",
                "description": (
                    "Upgrade workers from 'advisory' to 'partial' decision "
                    "authority for low-risk request classes. Orchestrator only "
                    "commits high-risk."
                ),
                "suggested_implementation": (
                    "Reclassify worker-01..worker-06 with decision_authority="
                    "'partial' for FAQ / status / shipping queries. Keep "
                    "worker-07..worker-12 advisory for billing / refunds. "
                    "Orchestrator commits only refund-class decisions."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Direct relief on the worst metric (decision_bottleneck). "
                    "Moves effective parallelism from 1 to 6 immediately, with "
                    "only billing / refunds still funneling through the orchestrator."
                ),
            },
            {
                "target_metric": "max_span",
                "intervention_type": "split_supervisor_load",
                "description": (
                    "Insert two sub-supervisors so the orchestrator's span drops "
                    "from 12 to 2, and each sub-supervisor manages 6 workers."
                ),
                "suggested_implementation": (
                    "Add agent-A and agent-B with reports_to=['orchestrator'] "
                    "and decision_authority='full'. Re-route worker-01..06 "
                    "reports_to=['agent-A']; worker-07..12 reports_to=['agent-B']."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Closes the span-of-control gap directly. The orchestrator's "
                    "max_span goes from 12 (severe) to 2 (healthy). Sub-supervisors "
                    "absorb most of the routing load."
                ),
            },
            {
                "target_metric": "centralization_index",
                "intervention_type": "add_redundant_path",
                "description": (
                    "Add a second top-level decision agent for failover, so the "
                    "orchestrator is not single-point-of-failure."
                ),
                "suggested_implementation": (
                    "Add 'orchestrator-2' with reports_to=[] and "
                    "decision_authority='full'. Half of incoming requests route "
                    "to each orchestrator via simple hash."
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Closes the centralization gap without dismantling the "
                    "hierarchy. Combined with intervention 2, gives 4-way "
                    "effective parallelism at the supervisor layer."
                ),
            },
        ]
    )
    return [interventions]


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
    calc = SpanLoadCalculator(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    analysis = calc.run(trace)
    print(analysis.to_markdown())


if __name__ == "__main__":
    main()
