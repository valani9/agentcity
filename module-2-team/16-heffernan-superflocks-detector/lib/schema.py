"""Schema for the Heffernan Superflocks Detector.

Anchored in:
  - Heffernan, M. (2014) *A Bigger Prize.* Simon & Schuster.
  - Heffernan, M. (2015) TED Talk "Forget the Pecking Order at Work."
  - Muir, W. M. (1996) Group selection in chickens.
  - Bandura, A. (1977) Self-efficacy (anti-fragility frame).
  - Hackman (2002) *Leading Teams*.
  - Page, S. E. (2007) *The Difference* (diversity dividend).
  - Salas et al. (2018) Team performance review.
  - Wang et al. (2023) Cooperative LLM Agents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SuperflocksMode = Literal["quick", "standard", "forensic"]
SUPERFLOCKS_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

Severity = Literal["none", "trace", "low", "moderate", "medium", "high", "critical"]
SEVERITY_ORDER: tuple[str, ...] = ("none", "trace", "low", "moderate", "medium", "high", "critical")


def severity_from_fragility(fragility: float) -> Severity:
    f = max(0.0, min(1.0, float(fragility)))
    if f < 0.10:
        return "none"
    if f < 0.25:
        return "trace"
    if f < 0.40:
        return "low"
    if f < 0.55:
        return "moderate"
    if f < 0.70:
        return "medium"
    if f < 0.85:
        return "high"
    return "critical"


SuperflocksProfilePattern = Literal[
    "robust_diversified",
    "concentrated_routing",
    "superflocks_canonical",  # 1 dominant + others underused
    "top_agent_monopoly",  # share > 0.85
    "no_fallback_coverage",  # secondary agents never used
    "complementarity_collapse",  # capabilities present, not used
    "failure_clustering_risk",
    "indeterminate",
]
SUPERFLOCKS_PROFILE_PATTERNS: tuple[str, ...] = (
    "robust_diversified",
    "concentrated_routing",
    "superflocks_canonical",
    "top_agent_monopoly",
    "no_fallback_coverage",
    "complementarity_collapse",
    "failure_clustering_risk",
    "indeterminate",
)


InterventionType = Literal[
    "introduce_routing_jitter",
    "require_minimum_agent_diversity",
    "add_capability_complement_check",
    "rotate_lead_agent",
    "load_balancing_floor",
    "redundant_routing",
    "swap_top_agent_offline_drill",
    "human_review",
    "new_eval",
    "add_routing_eval",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "introduce_routing_jitter",
    "require_minimum_agent_diversity",
    "add_capability_complement_check",
    "rotate_lead_agent",
    "load_balancing_floor",
    "redundant_routing",
    "swap_top_agent_offline_drill",
    "human_review",
    "new_eval",
    "add_routing_eval",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RoutingDecision(BaseModel):
    task_id: str
    task_class: str = ""
    routed_to: str
    candidates: list[str] = Field(default_factory=list)
    reason: str = ""
    outcome: Literal["success", "failure", "partial", "unknown"] = "unknown"
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentCapability(BaseModel):
    agent_name: str
    capability_scores: dict[str, float] = Field(default_factory=dict)


class RoutingTrace(BaseModel):
    trace_id: str | None = None
    window_description: str
    agents: list[str]
    capabilities: list[AgentCapability] = Field(default_factory=list)
    routing_decisions: list[RoutingDecision]
    outcome: str
    success: bool = False
    # New in v0.2.0.
    framework: str | None = None
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("window_description", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


class SuperflocksMetric(BaseModel):
    name: Literal[
        "top_agent_share",
        "routing_gini",
        "complementarity_utilization",
        "fallback_coverage",
        "failure_clustering",
    ]
    value: float = Field(ge=0.0, le=1.0)
    explanation: str
    severity: Literal["none", "low", "medium", "high"]


class CapabilityComplementarityAudit(BaseModel):
    """Forensic mode: audit how often complementary capabilities are wasted."""

    wasted_capability_count: int = Field(default=0, ge=0)
    most_underutilized_agent: str | None = None
    capability_dimensions_underused: list[str] = Field(default_factory=list)
    notes: str = ""


class FailureClusteringAudit(BaseModel):
    """Forensic mode: audit whether failures cluster on the top agent."""

    top_agent_failure_share: float = Field(default=0.0, ge=0.0, le=1.0)
    fallback_used_on_failure: bool = False
    cascade_risk: Literal["low", "moderate", "high"] = "low"
    notes: str = ""


class FragilityIntervention(BaseModel):
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    pattern: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_profile_pattern: str | None = None
    fragility_delta: float = 0.0
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class SuperflocksDetection(BaseModel):
    trace_id: str | None = None
    top_agent: str | None = None
    top_agent_share: float = Field(ge=0.0, le=1.0)
    routing_gini: float = Field(ge=0.0, le=1.0)
    fragility_score: float = Field(ge=0.0, le=1.0)
    fragility_quality: Literal["robust", "concentrated", "superflocks"]
    metrics: list[SuperflocksMetric]
    interventions: list[FragilityIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0.
    mode: SuperflocksMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: SuperflocksProfilePattern = "indeterminate"
    capability_audit: CapabilityComplementarityAudit | None = None
    failure_audit: FailureClusteringAudit | None = None
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
        out.append("# Superflocks Detection (Heffernan)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.trace_id:
            out.append(f"_Trace: {self.trace_id}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(
            f"_Fragility quality: **{self.fragility_quality.upper()}** "
            f"(severity: {self.severity})_\n"
        )
        out.append(f"_Fragility score: {self.fragility_score:.2f}_\n")
        if self.top_agent:
            out.append(f"_Top agent: **{self.top_agent}** (share {self.top_agent_share:.2f})_\n")
        out.append(f"_Routing Gini: {self.routing_gini:.2f}_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Per-Metric Detail\n")
        for m in self.metrics:
            bar = "#" * int(round(m.value * 20))
            out.append(f"- **{m.name}** ({m.severity}): {m.value:.2f}  {bar}\n")
            out.append(f"  {m.explanation}\n")

        if self.capability_audit:
            ca = self.capability_audit
            out.append("\n## Capability Complementarity Audit (Forensic)\n")
            out.append(
                f"- wasted_capability_count: {ca.wasted_capability_count}\n"
                f"- most_underutilized_agent: {ca.most_underutilized_agent}\n"
                f"- capability_dimensions_underused: {ca.capability_dimensions_underused}\n"
            )
            if ca.notes:
                out.append(f"- {ca.notes}\n")

        if self.failure_audit:
            fa = self.failure_audit
            out.append("\n## Failure Clustering Audit (Forensic)\n")
            out.append(
                f"- top_agent_failure_share: {fa.top_agent_failure_share:.2f}\n"
                f"- fallback_used_on_failure: {fa.fallback_used_on_failure}\n"
                f"- cascade_risk: {fa.cascade_risk}\n"
            )
            if fa.notes:
                out.append(f"- {fa.notes}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(f"\n### Intervention {i}: `{iv.intervention_type}`\n")
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        if self.attached_playbooks:
            out.append("\n## Attached Playbooks\n")
            for pb in self.attached_playbooks:
                out.append(
                    f"\n### {pb.title} _(pattern={pb.pattern}, failure_mode={pb.failure_mode})_\n"
                )
                for j, step in enumerate(pb.steps, 1):
                    out.append(f"{j}. {step}\n")

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
