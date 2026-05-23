"""Schema for the Robbins & Judge 7-Characteristics Culture Diagnostic.

Stephen P. Robbins & Timothy A. Judge, "Organizational Behavior" (17th
ed., Pearson, 2017). The Robbins/Judge model proposes that culture can
be profiled along seven dimensions, each scored independently:

  - INNOVATION         - how much risk-taking and novel approaches are
                          encouraged
  - ATTENTION_TO_DETAIL - precision, analysis, attention to specifics
  - OUTCOME            - emphasis on results vs. process
  - PEOPLE             - consideration for effects on team members /
                          stakeholders
  - TEAM               - work organized around teams vs. individuals
  - AGGRESSIVENESS     - competitiveness vs. easy-going-ness
  - STABILITY          - emphasis on maintaining status quo vs. growth

Where Schein's Iceberg (#31) asks ARE THE THREE LAYERS ALIGNED, the
Robbins/Judge 7-Characteristics asks WHAT IS THIS CULTURE'S PROFILE? The
two compose: Schein measures coherence; Robbins/Judge measures the
specific shape.

v0.2.0 adds three pipeline modes, a 7-point severity scale, eight
profile patterns, forensic-mode audits (Target-Profile Provenance,
Per-Dimension Risk), calibration baselines, composition handoff, attached
playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

CULTURE_CHARACTERISTICS: tuple[str, ...] = (
    "innovation",
    "attention_to_detail",
    "outcome",
    "people",
    "team",
    "aggressiveness",
    "stability",
)

RobbinsMode = Literal["quick", "standard", "forensic"]
ROBBINS_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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
    """Map misfit (0=perfect, 1=inverted) to a 7-point severity scale."""
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


RobbinsProfilePattern = Literal[
    "well_fit",
    "innovation_starved",
    "detail_starved",
    "innovation_excess",
    "stability_excess",
    "team_excess",
    "team_starved",
    "aggressiveness_excess",
    "people_starved",
    "outcome_starved",
    "broadly_misfit",
    "indeterminate",
]
ROBBINS_PROFILE_PATTERNS: tuple[str, ...] = (
    "well_fit",
    "innovation_starved",
    "detail_starved",
    "innovation_excess",
    "stability_excess",
    "team_excess",
    "team_starved",
    "aggressiveness_excess",
    "people_starved",
    "outcome_starved",
    "broadly_misfit",
    "indeterminate",
)

InterventionType = Literal[
    "rewrite_system_prompt",
    "adjust_temperature",
    "add_guardrail",
    "swap_model",
    "add_team_scaffold",
    "remove_solo_path",
    "add_kill_criterion",
    "new_eval",
    "human_review",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "rewrite_system_prompt",
    "adjust_temperature",
    "add_guardrail",
    "swap_model",
    "add_team_scaffold",
    "remove_solo_path",
    "add_kill_criterion",
    "new_eval",
    "human_review",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]

TaskClass = Literal[
    "research_exploration",
    "creative_generation",
    "regulated_workflow",
    "financial_operation",
    "customer_support",
    "code_review",
    "incident_response",
    "general_purpose",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent culture trace + task class ---------------------------


class AgentCultureTrace(BaseModel):
    """A trace + task class ready for the 7-Characteristics culture diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    framework: str | None = None
    task: str
    task_class: TaskClass = Field(
        default="general_purpose",
        description="The task class drives the target culture profile.",
    )
    system_prompt: str = Field(default="")
    observed_behaviors: list[str] = Field(default_factory=list)
    inferred_assumptions: list[str] = Field(default_factory=list)
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

    @model_validator(mode="after")
    def _has_signal(self) -> AgentCultureTrace:
        if (
            not self.system_prompt or not self.system_prompt.strip()
        ) and not self.observed_behaviors:
            raise ValueError("either system_prompt or observed_behaviors must be provided")
        return self


# --- Output: per-characteristic profile + recommendations --------------


class CharacteristicScore(BaseModel):
    """One culture characteristic, scored against the trace."""

    characteristic: Literal[
        "innovation",
        "attention_to_detail",
        "outcome",
        "people",
        "team",
        "aggressiveness",
        "stability",
    ]
    observed_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = absent in this agent's behavior; 1 = strongly present.",
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


class TargetProfileProvenance(BaseModel):
    """Forensic-mode: where did each target score come from?"""

    derived_from: Literal["task_class_default", "trace_evidence", "blended"] = "task_class_default"
    rationale: str = ""
    per_dim_overrides: dict[str, float] = Field(default_factory=dict)


class PerDimensionRisk(BaseModel):
    """Forensic-mode: the failure consequence of getting each dimension wrong."""

    highest_risk_dimension: Literal[
        "innovation",
        "attention_to_detail",
        "outcome",
        "people",
        "team",
        "aggressiveness",
        "stability",
        "none",
    ] = "none"
    risk_explanation: str = ""
    per_dim_risk: dict[str, Literal["low", "medium", "high"]] = Field(default_factory=dict)


class CultureIntervention(BaseModel):
    """A concrete intervention to shift one characteristic toward the target."""

    target_characteristic: Literal[
        "innovation",
        "attention_to_detail",
        "outcome",
        "people",
        "team",
        "aggressiveness",
        "stability",
    ]
    direction: Literal["increase", "decrease"]
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    characteristic: str
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


class CultureProfileDetection(BaseModel):
    """The full 7-Characteristics diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    task_class: TaskClass
    characteristics: list[CharacteristicScore]
    overall_fit: float = Field(
        ge=0.0,
        le=1.0,
        description="Mean fit score across the seven characteristics.",
    )
    fit_quality: Literal["well-fit", "partial-fit", "misfit"]
    biggest_gap: Literal[
        "innovation",
        "attention_to_detail",
        "outcome",
        "people",
        "team",
        "aggressiveness",
        "stability",
        "none",
    ]
    interventions: list[CultureIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # v0.2.0
    mode: RobbinsMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: RobbinsProfilePattern = "indeterminate"
    target_profile_provenance: TargetProfileProvenance | None = None
    per_dimension_risk: PerDimensionRisk | None = None
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
        out.append("# 7-Characteristics Culture Profile (Robbins & Judge)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Task class: **{self.task_class}**_\n")
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

        out.append("\n## Per-Characteristic Profile\n")
        out.append("Each row shows observed score vs target for this task class.\n\n")
        for c in self.characteristics:
            obs_bar = "#" * int(round(c.observed_score * 10))
            target_bar = "." * int(round(c.target_score * 10))
            out.append(
                f"- **{c.characteristic}**: obs {c.observed_score:.2f} `{obs_bar:<10}` "
                f"target {c.target_score:.2f} `{target_bar:<10}` fit {c.fit_score:.2f}\n"
            )

        out.append("\n## Evidence\n")
        for c in self.characteristics:
            out.append(f"\n### {c.characteristic} (fit {c.fit_score:.2f})\n")
            out.append(f"{c.explanation}\n")
            if c.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in c.evidence_quotes:
                    out.append(f"> {quote}\n")

        if self.target_profile_provenance:
            tp = self.target_profile_provenance
            out.append("\n## Target-Profile Provenance (Forensic)\n")
            out.append(f"- **derived_from:** {tp.derived_from}\n")
            if tp.rationale:
                out.append(f"- {tp.rationale}\n")
            if tp.per_dim_overrides:
                out.append("- per-dim overrides:\n")
                for k, v in tp.per_dim_overrides.items():
                    out.append(f"  - {k}: {v:.2f}\n")

        if self.per_dimension_risk:
            pr = self.per_dimension_risk
            out.append("\n## Per-Dimension Risk (Forensic)\n")
            out.append(f"- **highest_risk_dimension:** {pr.highest_risk_dimension}\n")
            if pr.risk_explanation:
                out.append(f"- {pr.risk_explanation}\n")
            if pr.per_dim_risk:
                for risk_dim, risk_level in pr.per_dim_risk.items():
                    out.append(f"  - {risk_dim}: {risk_level}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: {iv.direction} `{iv.target_characteristic}` "
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
                    f"\n### {pb.title} _(characteristic={pb.characteristic}, "
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


# Legacy aliases (v0.1.0 compatibility)
__all__ = [
    "CULTURE_CHARACTERISTICS",
    "ROBBINS_MODES",
    "ROBBINS_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "AgentCultureTrace",
    "AttachedPlaybook",
    "BaselineComparison",
    "CharacteristicScore",
    "ComposedPatternHandoff",
    "CultureIntervention",
    "CultureProfileDetection",
    "EffortEstimate",
    "InterventionType",
    "PerDimensionRisk",
    "RobbinsMode",
    "RobbinsProfilePattern",
    "Severity",
    "TargetProfileProvenance",
    "TaskClass",
    "severity_from_misfit",
]
