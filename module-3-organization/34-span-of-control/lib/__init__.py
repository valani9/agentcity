"""agentcity.span_of_control — Deterministic Span-of-Control /
Centralization calculator for AI agent crews. Fourth Module 3
(organizational) pattern.

Six quantitative metrics computed locally in Python (no LLM in the
math): max_span, mean_span, centralization_index, hierarchy_depth,
span_gini, decision_bottleneck. The LLM is only used for qualitative
intervention generation on top of the computed metrics — the math is
locked.

Pairs with Pattern #33: where #33 is the LLM-driven qualitative
structural-fit diagnostic across six dimensions, #34 is the
deterministic numeric audit. The two compose: #33 tells you what fits
the task class; #34 tells you whether the math actually works under
load.

Quick start:

    from agentcity.span_of_control import (
        SpanLoadCalculator,
        CrewLoadTrace,
        AgentNode,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = CrewLoadTrace(
        crew_id="customer-support-crew",
        task="Handle 100 requests/minute customer support load.",
        agents=[
            AgentNode(agent_id="orchestrator", decision_authority="full"),
            *[
                AgentNode(
                    agent_id=f"worker-{i}",
                    reports_to=["orchestrator"],
                    decision_authority="advisory",
                )
                for i in range(12)
            ],
        ],
        incoming_request_rate=100.0,
        outcome="Orchestrator throughput maxed; queue backed up.",
        success=False,
    )
    analysis = SpanLoadCalculator(AnthropicClient()).run(trace)
    print(analysis.to_markdown())
    # max_span=12, centralization=high, bottleneck=orchestrator
"""

from .generator import LLMClient, SpanLoadCalculator
from .metrics import (
    centralization_index,
    compute_all_metrics_payload,
    compute_span_counts,
    decision_bottleneck_score,
    hierarchy_depth,
    max_span,
    mean_span,
    span_gini,
)
from .schema import (
    AgentNode,
    CrewLoadTrace,
    SpanIntervention,
    SpanLoadAnalysis,
    SpanMetric,
)

__all__ = [
    "SpanLoadCalculator",
    "LLMClient",
    "AgentNode",
    "CrewLoadTrace",
    "SpanLoadAnalysis",
    "SpanMetric",
    "SpanIntervention",
    "compute_span_counts",
    "max_span",
    "mean_span",
    "centralization_index",
    "hierarchy_depth",
    "span_gini",
    "decision_bottleneck_score",
    "compute_all_metrics_payload",
]

__version__ = "0.1.0"
