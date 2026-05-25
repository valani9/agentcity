"""vstack.span_of_control -- Deterministic Span-of-Control /
Centralization calculator for AI agent crews. Module 3 (organizational)
pattern.

Six quantitative metrics computed locally in Python (no LLM in the
math): max_span, mean_span, centralization_index, hierarchy_depth,
span_gini, decision_bottleneck. The LLM is only used for qualitative
intervention generation on top of the computed metrics -- the math is
locked.

v0.2.0 features:
  - Three pipeline modes (quick = 0 LLM calls / standard = 1 /
    forensic = 1 after two deterministic forensic audits)
  - 10 SpanProfilePattern variants + 7-point Severity scale
  - Forensic StructuralAnomalyAudit + LoadAmplificationAudit
    (deterministic helpers; LLM only paraphrases)
  - Calibration baseline roundtrip + per-metric drift comparison
  - Cross-pattern composition manifest
  - 12 (metric, failure_mode) playbooks anchored to Galbraith /
    Mintzberg
  - Production infra via vstack.aar shared module

Pairs with Pattern #33: where #33 is the LLM-driven qualitative
structural-fit diagnostic across six dimensions, #34 is the
deterministic numeric audit. The two compose: #33 tells you what fits
the task class; #34 tells you whether the math actually works under
load.

Quick start:

    from vstack.span_of_control import (
        SpanLoadCalculator,
        CrewLoadTrace,
        AgentNode,
    )
    from vstack.aar import AnthropicClient

    trace = CrewLoadTrace(
        crew_id="customer-support",
        task="Handle 100 requests/minute load.",
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
    # profile_pattern: load_amplified_bottleneck
"""

from ._calibration import (
    compare_to_baseline,
    load_baseline,
    record_baseline,
)
from ._composition import (
    SPAN_COMPOSITION,
    recommended_downstream,
    recommended_upstream,
)
from ._playbooks import (
    PLAYBOOKS,
    all_playbook_keys,
    find_playbook,
    find_playbook_for_intervention,
)
from .generator import (
    AsyncLLMClient,
    LLMClient,
    SpanLoadCalculator,
    SpanLoadCalculatorAsync,
)
from .metrics import (
    centralization_index,
    composite_load_score,
    compute_all_metrics_payload,
    compute_span_counts,
    decision_bottleneck_score,
    detect_structural_anomalies,
    estimate_breaking_rate,
    hierarchy_depth,
    max_span,
    mean_span,
    span_gini,
)
from .schema import (
    SEVERITY_ORDER,
    SPAN_METRIC_NAMES,
    SPAN_MODES,
    SPAN_PROFILE_PATTERNS,
    AgentNode,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    CrewLoadTrace,
    EffortEstimate,
    InterventionType,
    LoadAmplificationAudit,
    Severity,
    SpanIntervention,
    SpanLoadAnalysis,
    SpanMetric,
    SpanMode,
    SpanProfilePattern,
    StructuralAnomalyAudit,
    severity_from_load,
)

__all__ = [
    "AgentNode",
    "AsyncLLMClient",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "CrewLoadTrace",
    "EffortEstimate",
    "InterventionType",
    "LLMClient",
    "LoadAmplificationAudit",
    "PLAYBOOKS",
    "SEVERITY_ORDER",
    "SPAN_COMPOSITION",
    "SPAN_METRIC_NAMES",
    "SPAN_MODES",
    "SPAN_PROFILE_PATTERNS",
    "Severity",
    "SpanIntervention",
    "SpanLoadAnalysis",
    "SpanLoadCalculator",
    "SpanLoadCalculatorAsync",
    "SpanMetric",
    "SpanMode",
    "SpanProfilePattern",
    "StructuralAnomalyAudit",
    "all_playbook_keys",
    "centralization_index",
    "compare_to_baseline",
    "composite_load_score",
    "compute_all_metrics_payload",
    "compute_span_counts",
    "decision_bottleneck_score",
    "detect_structural_anomalies",
    "estimate_breaking_rate",
    "find_playbook",
    "find_playbook_for_intervention",
    "hierarchy_depth",
    "load_baseline",
    "max_span",
    "mean_span",
    "record_baseline",
    "recommended_downstream",
    "recommended_upstream",
    "severity_from_load",
    "span_gini",
]

__version__ = "0.2.0"
