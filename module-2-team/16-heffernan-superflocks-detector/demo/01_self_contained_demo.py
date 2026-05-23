"""Self-contained demo of the Heffernan Superflocks Detector.

Synthetic scenario: a 4-agent crew (claude, gpt, haiku, ollama) over a
1000-task window. The orchestrator's routing rule is 'always pick the
agent with the highest capability score' — so claude wins ~90% of routes.
When claude has a brief outage, half the task classes have NO fallback
because no other agent has capability >=0.5. The routing pattern is
textbook superflocks: high top_agent_share, high routing_gini, low
fallback_coverage.

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
    from agentcity.superflocks import (
        AgentCapability,
        RoutingDecision,
        RoutingTrace,
        SuperflocksDetector,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> RoutingTrace:
    # 20 sample decisions, with claude winning ~90%, one observed failure on claude
    decisions: list[RoutingDecision] = []
    for i in range(18):
        decisions.append(
            RoutingDecision(
                task_id=f"task-{i:03d}",
                task_class=("research" if i % 3 == 0 else ("coding" if i % 3 == 1 else "qa")),
                routed_to="claude",
                candidates=["claude", "gpt", "haiku", "ollama"],
                reason="highest capability score",
                outcome="failure" if i == 17 else "success",
            )
        )
    decisions.append(
        RoutingDecision(
            task_id="task-018",
            task_class="qa",
            routed_to="gpt",
            candidates=["claude", "gpt", "haiku", "ollama"],
            reason="claude on cooldown",
            outcome="success",
        )
    )
    decisions.append(
        RoutingDecision(
            task_id="task-019",
            task_class="coding",
            routed_to="haiku",
            candidates=["claude", "gpt", "haiku", "ollama"],
            reason="claude on cooldown",
            outcome="failure",
        )
    )

    return RoutingTrace(
        trace_id="demo-prod-routing-2026-W21",
        window_description="20 production task routes over the last 7 days.",
        agents=["claude", "gpt", "haiku", "ollama"],
        capabilities=[
            AgentCapability(
                agent_name="claude",
                capability_scores={"research": 0.92, "coding": 0.88, "qa": 0.85},
            ),
            AgentCapability(
                agent_name="gpt",
                capability_scores={"research": 0.75, "coding": 0.78, "qa": 0.72},
            ),
            AgentCapability(
                agent_name="haiku",
                capability_scores={"research": 0.45, "coding": 0.40, "qa": 0.60},
            ),
            AgentCapability(
                agent_name="ollama",
                capability_scores={"research": 0.35, "coding": 0.42, "qa": 0.30},
            ),
        ],
        routing_decisions=decisions,
        outcome=(
            "Claude won 18 of 20 routes (90%). When claude went on cooldown, "
            "haiku had insufficient capability to cover the coding task and "
            "the route failed. The crew has high single-point-of-failure risk."
        ),
        success=False,
    )


def stub_responses() -> list[str]:
    return [
        json.dumps(
            {
                "metrics": [
                    {
                        "name": "top_agent_share",
                        "value": 0.9,
                        "explanation": (
                            "Claude won 18/20 routes (90%). This is textbook superflocks "
                            "concentration — a single agent absorbs nearly all decisions."
                        ),
                        "severity": "high",
                    },
                    {
                        "name": "routing_gini",
                        "value": 0.78,
                        "explanation": (
                            "Routing distribution is highly unequal across the 4-agent "
                            "roster. Gini of 0.78 with a 4-agent ceiling indicates one "
                            "agent dominates."
                        ),
                        "severity": "high",
                    },
                    {
                        "name": "complementarity_utilization",
                        "value": 0.1,
                        "explanation": (
                            "Only 2/20 routes went to a non-top agent, and both were "
                            "forced (claude on cooldown). The orchestrator never "
                            "actively chose a non-top agent for complementarity."
                        ),
                        "severity": "high",
                    },
                    {
                        "name": "fallback_coverage",
                        "value": 0.33,
                        "explanation": (
                            "Of the 3 task classes observed (research, coding, qa), "
                            "only 1 has >=2 agents with capability score >=0.5 (qa). "
                            "research and coding have no real fallback when claude "
                            "is unavailable."
                        ),
                        "severity": "high",
                    },
                    {
                        "name": "failure_clustering",
                        "value": 0.5,
                        "explanation": (
                            "Of 2 observed failures, 1 was on claude. The other was on "
                            "haiku attempting a coding task it was under-qualified for "
                            "— a downstream consequence of the superflocks pattern."
                        ),
                        "severity": "medium",
                    },
                ],
                "fragility_quality": "superflocks",
                "interventions": [
                    {
                        "intervention_type": "redundant_routing",
                        "description": (
                            "For each task class, route to TWO agents in parallel for "
                            "the next 100 tasks. Compare outputs; surface divergence."
                        ),
                        "suggested_implementation": (
                            "Pipeline: for task_class in {research, coding}, send to "
                            "(claude, gpt) in parallel. Judge picks the better output. "
                            "This builds capability data for the secondary agent AND "
                            "exposes outputs that disagree."
                        ),
                        "estimated_impact": "high",
                        "rationale": (
                            "Directly counters the single-point-of-failure risk. Costs "
                            "extra compute but gains observability + fallback capacity."
                        ),
                    },
                    {
                        "intervention_type": "load_balancing_floor",
                        "description": (
                            "Cap top-agent share at 60% via a load-balancing floor "
                            "on the routing rule."
                        ),
                        "suggested_implementation": (
                            "Routing rule: if claude's last-100-task share > 0.6, "
                            "route the next task to the second-most-capable agent "
                            "for that task class."
                        ),
                        "estimated_impact": "high",
                        "rationale": (
                            "Forces utilization of the rest of the roster, building "
                            "the experience needed for real fallback coverage."
                        ),
                    },
                    {
                        "intervention_type": "swap_top_agent_offline_drill",
                        "description": (
                            "Run a scheduled drill where claude is offline for a 4-hour "
                            "window; measure how the crew degrades and which task "
                            "classes fail."
                        ),
                        "suggested_implementation": (
                            "Cron: once per week, route ALL claude-eligible tasks to "
                            "the next-best agent for 4 hours. Record outcomes."
                        ),
                        "estimated_impact": "medium",
                        "rationale": (
                            "Empirical confirmation that the system can survive without "
                            "the top agent. Discovers brittleness before a real outage does."
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
    detector = SuperflocksDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
