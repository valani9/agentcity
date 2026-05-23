"""Schema for the Org-Structure Matrix Analyzer.

Drawn from the org-design literature consolidated in Galbraith's Star
Model, Mintzberg's structural configurations, and Stanford's Designing
Dynamic Organizations curriculum. The matrix scores six structural
dimensions independently:

  - SPECIALIZATION       - how narrowly are agent roles defined?
  - FORMALIZATION        - how rule-bound vs improvisational is the work?
  - CENTRALIZATION       - where do decisions actually get made?
  - HIERARCHY            - how many levels of supervisory escalation?
  - SPAN_OF_CONTROL      - how many subordinates does each supervisor manage?
  - DEPARTMENTALIZATION  - by what dimension are agents grouped (function,
                            product, customer, geography, matrix)?

Where Schein's Iceberg (#31) and Robbins/Judge's 7-Characteristics (#32)
diagnose *culture*, this pattern diagnoses *structure*.

v0.2.0 adds three pipeline modes, a 7-point severity scale, eight
profile patterns, forensic-mode audits (Reporting-Graph Analysis,
Decision-Bottleneck Risk), calibration baselines, composition handoff,
attached playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

STRUCTURE_DIMENSIONS: tuple[str, ...] = (
    "specialization",
    "formalization",
    "centralization",
    "hierarchy",
    "span_of_control",
    "departmentalization",
)

StructureMode = Literal["quick", "standard", "forensic"]
STRUCTURE_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_misfit(misfit: float) -> Severity:
    s = max(0.0, min(1.0, float(misfit)))
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


StructureArchetype = Literal[
    "flat-peer",
    "hierarchical",
    "centralized-functional",
    "decentralized-product",
    "matrix",
    "mixed",
]
STRUCTURE_ARCHETYPES: tuple[str, ...] = (
    "flat-peer",
    "hierarchical",
    "centralized-functional",
    "decentralized-product",
    "matrix",
    "mixed",
)


StructureProfilePattern = Literal[
    "well_fit",
    "too_flat_for_critical_task",
    "too_hierarchical_for_creative",
    "decision_bottleneck",
    "no_clear_authority",
    "over_specialized",
    "under_specialized",
    "matrix_overhead",
    "broadly_misfit",
    "indeterminate",
]
STRUCTURE_PROFILE_PATTERNS: tuple[str, ...] = (
    "well_fit",
    "too_flat_for_critical_task",
    "too_hierarchical_for_creative",
    "decision_bottleneck",
    "no_clear_authority",
    "over_specialized",
    "under_specialized",
    "matrix_overhead",
    "broadly_misfit",
    "indeterminate",
)


InterventionType = Literal[
    "flatten_hierarchy",
    "add_supervisor_layer",
    "consolidate_roles",
    "split_roles",
    "shift_decision_authority",
    "regroup_by_product",
    "regroup_by_function",
    "introduce_matrix",
    "add_routing_layer",
    "remove_routing_layer",
    "new_eval",
    "human_review",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "flatten_hierarchy",
    "add_supervisor_layer",
    "consolidate_roles",
    "split_roles",
    "shift_decision_authority",
    "regroup_by_product",
    "regroup_by_function",
    "introduce_matrix",
    "add_routing_layer",
    "remove_routing_layer",
    "new_eval",
    "human_review",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]

TaskClass = Literal[
    "creative_brainstorm",
    "research_exploration",
    "incident_response",
    "regulated_workflow",
    "customer_support",
    "code_review",
    "high_throughput_pipeline",
    "general_purpose",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent crew structure trace ---------------------------------


class AgentRole(BaseModel):
    """One agent's role within the crew structure."""

    agent_id: str
    role_name: str = Field(description="e.g. 'orchestrator', 'researcher', 'reviewer'.")
    reports_to: list[str] = Field(
        default_factory=list,
        description="agent_ids that this agent escalates to. Empty = top-level.",
    )
    grouped_by: Literal["function", "product", "customer", "geography", "matrix", "none"] = Field(
        default="none"
    )
    decision_authority: Literal["full", "partial", "advisory", "none"] = Field(
        default="partial",
        description="Can this agent commit work without escalation?",
    )


class CrewStructureTrace(BaseModel):
    """A crew + task class ready for the structural diagnostic."""

    crew_id: str | None = None
    framework: str | None = None
    task: str
    task_class: TaskClass = Field(
        default="general_purpose",
        description="The task class drives the target structure profile.",
    )
    agents: list[AgentRole] = Field(min_length=1)
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


# --- Output: per-dimension profile + recommendations -------------------


class StructureDimensionScore(BaseModel):
    """One structural dimension, scored against the crew."""

    dimension: Literal[
        "specialization",
        "formalization",
        "centralization",
        "hierarchy",
        "span_of_control",
        "departmentalization",
    ]
    observed_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = absent / flat / informal; 1 = strongly present / steep / rigid.",
    )
    target_score: float = Field(
        ge=0.0,
        le=1.0,
        description="What the score should be for the given task class.",
    )
    fit_score: float = Field(
        ge=0.0,
        le=1.0,
        description="1 - abs(observed - target). 1 = perfect fit; 0 = inverted.",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    risk: Literal["low", "medium", "high"] = "medium"


class ReportingGraphAudit(BaseModel):
    """Forensic-mode: structural properties of the reporting DAG."""

    depth: int = Field(default=0, ge=0)
    branching_factor: float = Field(default=0.0, ge=0.0)
    cycles_detected: bool = False
    orphans: list[str] = Field(default_factory=list)
    bottleneck_agents: list[str] = Field(default_factory=list)
    explanation: str = ""


class DecisionBottleneckAudit(BaseModel):
    """Forensic-mode: which agent(s) gate critical decisions?"""

    bottleneck_agent_id: str | None = None
    affected_dimensions: list[str] = Field(default_factory=list)
    severity_estimate: Literal["low", "medium", "high"] = "medium"
    explanation: str = ""


class StructureIntervention(BaseModel):
    """A concrete intervention to shift one dimension toward the target."""

    target_dimension: Literal[
        "specialization",
        "formalization",
        "centralization",
        "hierarchy",
        "span_of_control",
        "departmentalization",
    ]
    direction: Literal["increase", "decrease", "redesign"]
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    dimension: str
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


class StructureAnalysis(BaseModel):
    """The full Org-Structure Matrix diagnostic output."""

    crew_id: str | None = None
    task_class: TaskClass
    archetype: StructureArchetype
    dimensions: list[StructureDimensionScore]
    overall_fit: float = Field(
        ge=0.0,
        le=1.0,
        description="Mean fit score across the six dimensions.",
    )
    fit_quality: Literal["well-fit", "partial-fit", "misfit"]
    biggest_gap: Literal[
        "specialization",
        "formalization",
        "centralization",
        "hierarchy",
        "span_of_control",
        "departmentalization",
        "none",
    ]
    interventions: list[StructureIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # v0.2.0
    mode: StructureMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: StructureProfilePattern = "indeterminate"
    reporting_graph_audit: ReportingGraphAudit | None = None
    decision_bottleneck_audit: DecisionBottleneckAudit | None = None
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
        out.append("# Org-Structure Matrix Analysis\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Task class: **{self.task_class}**_\n")
        out.append(f"_Archetype: **{self.archetype}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Fit quality: **{self.fit_quality.upper()}** (severity: {self.severity})_\n")
        out.append(f"_Overall fit: {self.overall_fit:.2f}_\n")
        out.append(f"_Biggest gap: **{self.biggest_gap}**_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Per-Dimension Profile\n")
        out.append("Each row shows observed structure vs target for this task class.\n\n")
        for d in self.dimensions:
            obs_bar = "#" * int(round(d.observed_score * 10))
            target_bar = "." * int(round(d.target_score * 10))
            out.append(
                f"- **{d.dimension}**: obs {d.observed_score:.2f} `{obs_bar:<10}` "
                f"target {d.target_score:.2f} `{target_bar:<10}` fit {d.fit_score:.2f}\n"
            )

        out.append("\n## Evidence\n")
        for d in self.dimensions:
            out.append(f"\n### {d.dimension} (fit {d.fit_score:.2f})\n")
            out.append(f"{d.explanation}\n")
            if d.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in d.evidence_quotes:
                    out.append(f"> {quote}\n")

        if self.reporting_graph_audit:
            rg = self.reporting_graph_audit
            out.append("\n## Reporting Graph Audit (Forensic)\n")
            out.append(f"- depth: {rg.depth}\n")
            out.append(f"- branching_factor: {rg.branching_factor:.2f}\n")
            out.append(f"- cycles_detected: {rg.cycles_detected}\n")
            if rg.orphans:
                out.append(f"- orphans: {', '.join(rg.orphans)}\n")
            if rg.bottleneck_agents:
                out.append(f"- bottleneck_agents: {', '.join(rg.bottleneck_agents)}\n")
            if rg.explanation:
                out.append(f"- {rg.explanation}\n")

        if self.decision_bottleneck_audit:
            db = self.decision_bottleneck_audit
            out.append("\n## Decision Bottleneck Audit (Forensic)\n")
            out.append(f"- bottleneck_agent_id: {db.bottleneck_agent_id}\n")
            out.append(f"- severity_estimate: {db.severity_estimate}\n")
            if db.affected_dimensions:
                out.append(f"- affected_dimensions: {', '.join(db.affected_dimensions)}\n")
            if db.explanation:
                out.append(f"- {db.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: {iv.direction} `{iv.target_dimension}` "
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
                    f"\n### {pb.title} _(dimension={pb.dimension}, "
                    f"failure_mode={pb.failure_mode})_\n"
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
    "STRUCTURE_ARCHETYPES",
    "STRUCTURE_DIMENSIONS",
    "STRUCTURE_MODES",
    "STRUCTURE_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "AgentRole",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "CrewStructureTrace",
    "DecisionBottleneckAudit",
    "EffortEstimate",
    "InterventionType",
    "ReportingGraphAudit",
    "Severity",
    "StructureAnalysis",
    "StructureArchetype",
    "StructureDimensionScore",
    "StructureIntervention",
    "StructureMode",
    "StructureProfilePattern",
    "TaskClass",
    "severity_from_misfit",
]
