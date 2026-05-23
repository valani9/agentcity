"""Schema for the Span-of-Control / Centralization Calculator.

Drawn from the same Galbraith/Mintzberg org-design canon as Pattern #33,
but with a different operational target. Where #33 provides an
LLM-driven qualitative fit diagnostic across six structural dimensions,
#34 computes precise QUANTITATIVE metrics on the org graph itself:

  - SPAN OF CONTROL distribution
  - CENTRALIZATION index
  - HIERARCHY DEPTH
  - SUPERVISOR LOAD imbalance (Gini)
  - DECISION BOTTLENECK score

All five metrics are computed DETERMINISTICALLY in Python from the
agent roster + reports_to edges + decision_authority field. The LLM is
used only for qualitative explanations + severity assessment +
intervention recommendations on the deterministic numbers.

v0.2.0 adds three pipeline modes (quick=0 LLM calls / standard=1 /
forensic=3), a 7-point severity scale, eight profile patterns, forensic
audits (StructuralAnomaly, LoadAmplification), calibration baselines,
composition handoff, attached playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SpanMode = Literal["quick", "standard", "forensic"]
SPAN_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

Severity = Literal["none", "trace", "low", "moderate", "medium", "high", "critical"]
SEVERITY_ORDER: tuple[str, ...] = (
    "none",
    "trace",
    "low",
    "moderate",
    "medium",
    "high",
    "critical",
)


def severity_from_load(load_score: float) -> Severity:
    s = max(0.0, min(1.0, float(load_score)))
    if s < 0.10:
        return "none"
    if s < 0.25:
        return "trace"
    if s < 0.40:
        return "low"
    if s < 0.55:
        return "moderate"
    if s < 0.70:
        return "medium"
    if s < 0.85:
        return "high"
    return "critical"


SpanProfilePattern = Literal[
    "well_balanced",
    "wide_span_orchestrator",
    "deep_hierarchy",
    "single_bottleneck",
    "load_amplified_bottleneck",
    "imbalanced_supervisors",
    "over_centralized",
    "under_centralized",
    "broadly_overloaded",
    "indeterminate",
]
SPAN_PROFILE_PATTERNS: tuple[str, ...] = (
    "well_balanced",
    "wide_span_orchestrator",
    "deep_hierarchy",
    "single_bottleneck",
    "load_amplified_bottleneck",
    "imbalanced_supervisors",
    "over_centralized",
    "under_centralized",
    "broadly_overloaded",
    "indeterminate",
)


SPAN_METRIC_NAMES: tuple[str, ...] = (
    "max_span",
    "mean_span",
    "centralization_index",
    "hierarchy_depth",
    "span_gini",
    "decision_bottleneck",
)

InterventionType = Literal[
    "add_supervisor_layer",
    "flatten_hierarchy",
    "split_supervisor_load",
    "delegate_decision_authority",
    "consolidate_supervisors",
    "redistribute_subordinates",
    "add_redundant_path",
    "remove_bottleneck_agent",
    "new_eval",
    "human_review",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "add_supervisor_layer",
    "flatten_hierarchy",
    "split_supervisor_load",
    "delegate_decision_authority",
    "consolidate_supervisors",
    "redistribute_subordinates",
    "add_redundant_path",
    "remove_bottleneck_agent",
    "new_eval",
    "human_review",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent crew structure --------------------------------------


class AgentNode(BaseModel):
    """One agent in the crew."""

    agent_id: str
    role_name: str = Field(default="generalist")
    reports_to: list[str] = Field(
        default_factory=list,
        description="agent_ids this agent escalates to. Empty = top-level.",
    )
    decision_authority: Literal["full", "partial", "advisory", "none"] = Field(
        default="partial",
        description="Can this agent commit work without escalation?",
    )


class CrewLoadTrace(BaseModel):
    """A crew + traffic trace ready for the span-of-control diagnostic."""

    crew_id: str | None = None
    framework: str | None = None
    task: str
    agents: list[AgentNode] = Field(min_length=1)
    incoming_request_rate: float = Field(
        default=1.0,
        ge=0.0,
        description=(
            "Requests/minute hitting the crew. Used to amplify bottleneck scoring under load."
        ),
    )
    observed_behaviors: list[str] = Field(default_factory=list)
    outcome: str
    success: bool
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


# --- Output: per-metric scores + interventions -------------------------


class SpanMetric(BaseModel):
    """One quantitative structural metric."""

    metric: Literal[
        "max_span",
        "mean_span",
        "centralization_index",
        "hierarchy_depth",
        "span_gini",
        "decision_bottleneck",
    ]
    value: float = Field(description="Raw metric value (units depend on metric).")
    normalized_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "0 = healthy on this metric; 1 = severely degraded. Allows the "
            "metrics to compose into a single load score."
        ),
    )
    explanation: str = ""


class StructuralAnomalyAudit(BaseModel):
    """Forensic-mode: cycles, orphans, dangling references, multi-parent edges."""

    cycles_detected: bool = False
    cycle_paths: list[list[str]] = Field(default_factory=list)
    orphans: list[str] = Field(default_factory=list)
    multi_parent_agents: list[str] = Field(default_factory=list)
    dangling_reports_to: list[str] = Field(default_factory=list)
    explanation: str = ""


class LoadAmplificationAudit(BaseModel):
    """Forensic-mode: how the incoming-request-rate compounds the bottleneck."""

    incoming_request_rate: float = Field(default=0.0, ge=0.0)
    base_bottleneck_score: float = Field(default=0.0, ge=0.0, le=1.0)
    amplified_bottleneck_score: float = Field(default=0.0, ge=0.0, le=1.0)
    breaking_rate_estimate: float | None = Field(
        default=None,
        description="Estimated request rate at which the bottleneck saturates.",
    )
    explanation: str = ""


class SpanIntervention(BaseModel):
    """A concrete intervention to relieve structural load."""

    target_metric: Literal[
        "max_span",
        "mean_span",
        "centralization_index",
        "hierarchy_depth",
        "span_gini",
        "decision_bottleneck",
    ]
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    metric: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_profile_pattern: str | None = None
    score_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class SpanLoadAnalysis(BaseModel):
    """The full Span-of-Control diagnostic output."""

    crew_id: str | None = None
    metrics: list[SpanMetric]
    structural_load_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Composite of the metric normalized scores.",
    )
    structural_load_quality: Literal["well-balanced", "under-stress", "overloaded"]
    bottleneck_agent_ids: list[str] = Field(
        default_factory=list,
        description="Agents flagged as decision bottlenecks (load amplifies risk).",
    )
    interventions: list[SpanIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # v0.2.0
    mode: SpanMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: SpanProfilePattern = "indeterminate"
    structural_anomaly_audit: StructuralAnomalyAudit | None = None
    load_amplification_audit: LoadAmplificationAudit | None = None
    baseline: BaselineComparison | None = None
    composition_handoff: ComposedPatternHandoff | None = None
    attached_playbooks: list[AttachedPlaybook] = Field(default_factory=list)
    run_id: str | None = None
    cost_usd: float = Field(default=0.0, ge=0.0)
    tokens_total: int = Field(default=0, ge=0)
    tokens_input: int = Field(default=0, ge=0)
    tokens_output: int = Field(default=0, ge=0)
    llm_calls: int = Field(default=0, ge=0)
    elapsed_ms: float = Field(default=0.0, ge=0.0)
    injection_detected: bool = False

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Span-of-Control / Centralization Analysis\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(
            f"_Structural load quality: **{self.structural_load_quality.upper()}** "
            f"(severity: {self.severity})_\n"
        )
        out.append(f"_Structural load score: {self.structural_load_score:.2f}_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.bottleneck_agent_ids:
            out.append(f"_Bottleneck agents: **{', '.join(self.bottleneck_agent_ids)}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Quantitative Metrics\n")
        out.append("Computed deterministically from the org graph (no LLM in the math).\n\n")
        for m in self.metrics:
            bar = "#" * int(round(m.normalized_score * 10))
            out.append(
                f"- **{m.metric}**: {m.value:.2f} (normalized {m.normalized_score:.2f}) "
                f"`{bar:<10}`\n"
            )
            if m.explanation:
                out.append(f"  - {m.explanation}\n")

        if self.structural_anomaly_audit:
            sa = self.structural_anomaly_audit
            out.append("\n## Structural Anomaly Audit (Forensic)\n")
            out.append(f"- cycles_detected: {sa.cycles_detected}\n")
            if sa.cycle_paths:
                for path in sa.cycle_paths:
                    out.append(f"  - cycle: {' -> '.join(path)}\n")
            if sa.orphans:
                out.append(f"- orphans: {', '.join(sa.orphans)}\n")
            if sa.multi_parent_agents:
                out.append(f"- multi_parent_agents: {', '.join(sa.multi_parent_agents)}\n")
            if sa.dangling_reports_to:
                out.append(f"- dangling_reports_to: {', '.join(sa.dangling_reports_to)}\n")
            if sa.explanation:
                out.append(f"- {sa.explanation}\n")

        if self.load_amplification_audit:
            la = self.load_amplification_audit
            out.append("\n## Load Amplification Audit (Forensic)\n")
            out.append(f"- incoming_request_rate: {la.incoming_request_rate:.1f}/min\n")
            out.append(f"- base_bottleneck_score: {la.base_bottleneck_score:.2f}\n")
            out.append(f"- amplified_bottleneck_score: {la.amplified_bottleneck_score:.2f}\n")
            if la.breaking_rate_estimate is not None:
                out.append(f"- breaking_rate_estimate: {la.breaking_rate_estimate:.1f}/min\n")
            if la.explanation:
                out.append(f"- {la.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: relieve `{iv.target_metric}` "
                f"via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        if self.attached_playbooks:
            out.append("\n## Attached Playbooks\n")
            for pb in self.attached_playbooks:
                out.append(
                    f"\n### {pb.title} _(metric={pb.metric}, failure_mode={pb.failure_mode})_\n"
                )
                for j, pb_step in enumerate(pb.steps, 1):
                    out.append(f"{j}. {pb_step}\n")

        if self.composition_handoff and (
            self.composition_handoff.downstream_patterns
            or self.composition_handoff.upstream_patterns
        ):
            out.append("\n## Composition Handoff\n")
            ch = self.composition_handoff
            if ch.upstream_patterns:
                out.append(f"- **Upstream:** {', '.join(f'`{p}`' for p in ch.upstream_patterns)}\n")
            if ch.downstream_patterns:
                out.append(
                    f"- **Recommended downstream:** "
                    f"{', '.join(f'`{p}`' for p in ch.downstream_patterns)}\n"
                )

        return "".join(out)


__all__ = [
    "SEVERITY_ORDER",
    "SPAN_METRIC_NAMES",
    "SPAN_MODES",
    "SPAN_PROFILE_PATTERNS",
    "AgentNode",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "CrewLoadTrace",
    "EffortEstimate",
    "InterventionType",
    "LoadAmplificationAudit",
    "Severity",
    "SpanIntervention",
    "SpanLoadAnalysis",
    "SpanMetric",
    "SpanMode",
    "SpanProfilePattern",
    "StructuralAnomalyAudit",
    "severity_from_load",
]
