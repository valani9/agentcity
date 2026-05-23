"""Schema for the Group Decision Models generator.

Facilitator canon (Kaner 2014 "Facilitator's Guide to Participatory
Decision-Making"; Stewart meeting-design literature). Five
decision-aggregation methods: concurring, majority, consensus,
fist_to_five, unanimous.

This is a GENERATIVE pattern (alongside #13 GRPI, #23 Plus/Delta, #24
SMART): it picks a decision model + emits a protocol spec, and
optionally tallies a supplied vote set.

v0.2.0 adds three pipeline modes, a 7-point severity scale, eight
profile patterns, forensic-mode audits (Method Fit, Tally Integrity),
calibration baselines, composition handoff, attached playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

DECISION_MODELS: tuple[str, ...] = (
    "concurring",
    "majority",
    "consensus",
    "fist_to_five",
    "unanimous",
)

GroupDecisionMode = Literal["quick", "standard", "forensic"]
GROUP_DECISION_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_fit(fit_score: float) -> Severity:
    """Map model-fit score (0=poor, 1=excellent) to inverse-severity."""
    s = max(0.0, min(1.0, float(fit_score)))
    deficit = 1.0 - s
    if deficit < 0.10:
        return "none"
    if deficit < 0.25:
        return "trace"
    if deficit < 0.40:
        return "low"
    if deficit < 0.55:
        return "moderate"
    if deficit < 0.70:
        return "medium"
    if deficit < 0.85:
        return "high"
    return "critical"


GroupDecisionProfilePattern = Literal[
    "good_fit_protocol",
    "consensus_overused",
    "majority_when_consensus_needed",
    "concurring_when_buyin_needed",
    "fist_to_five_underused",
    "no_quorum_specified",
    "no_tie_breaker",
    "indeterminate",
]
GROUP_DECISION_PROFILE_PATTERNS: tuple[str, ...] = (
    "good_fit_protocol",
    "consensus_overused",
    "majority_when_consensus_needed",
    "concurring_when_buyin_needed",
    "fist_to_five_underused",
    "no_quorum_specified",
    "no_tie_breaker",
    "indeterminate",
)


InterventionType = Literal[
    "switch_to_concurring",
    "switch_to_majority",
    "switch_to_consensus",
    "switch_to_fist_to_five",
    "switch_to_unanimous",
    "add_quorum",
    "add_tie_breaker",
    "add_fallback",
    "tighten_threshold",
    "new_eval",
    "human_review",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "switch_to_concurring",
    "switch_to_majority",
    "switch_to_consensus",
    "switch_to_fist_to_five",
    "switch_to_unanimous",
    "add_quorum",
    "add_tie_breaker",
    "add_fallback",
    "tighten_threshold",
    "new_eval",
    "human_review",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DecisionOption(BaseModel):
    option_id: str
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    decision_id: str | None = None
    title: str
    options: list[DecisionOption]
    agents: list[str]
    stakes: Literal["low", "medium", "high"]
    reversibility: Literal["reversible", "partial", "irreversible"] = "reversible"
    time_pressure: Literal["none", "moderate", "urgent"] = "moderate"
    expertise_asymmetry: Literal["balanced", "moderate", "high"] = "balanced"
    regulatory_exposure: bool = False
    buy_in_required: bool = False
    framework: str | None = None
    forced_model: (
        Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"] | None
    ) = None
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


class AgentVote(BaseModel):
    agent_name: str
    option_id: str | None = None
    score: int | None = Field(default=None, ge=0, le=5)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    comment: str = ""


class AggregationResult(BaseModel):
    method_used: Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"]
    winner: str | None = None
    outcome: Literal["decided", "tied", "blocked", "insufficient_votes", "no_quorum"]
    vote_counts: dict[str, int] = Field(default_factory=dict)
    fist_to_five_averages: dict[str, float] = Field(default_factory=dict)
    dissenters: list[str] = Field(default_factory=list)
    explanation: str = ""


class MethodFitAudit(BaseModel):
    """Forensic-mode: does the chosen model fit the decision properties?"""

    fit_score: float = Field(default=0.5, ge=0.0, le=1.0)
    stakes_aligned: bool = True
    reversibility_aligned: bool = True
    time_pressure_aligned: bool = True
    buy_in_aligned: bool = True
    regulatory_aligned: bool = True
    explanation: str = ""


class TallyIntegrityAudit(BaseModel):
    """Forensic-mode: is the tally robust to dissent / abstain edge cases?"""

    quorum_specified: bool = False
    tie_breaker_specified: bool = False
    fallback_specified: bool = False
    dissent_recording_specified: bool = True
    integrity_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class GroupDecisionIntervention(BaseModel):
    target_dimension: Literal["model", "threshold", "quorum", "tie_breaker", "fallback", "overall"]
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    model: str
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


class DecisionProtocol(BaseModel):
    decision_id: str | None = None
    title: str
    recommended_model: Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"]
    rationale: str
    protocol_steps: list[str]
    threshold: str
    quorum: int | None = None
    tie_breaker: str = ""
    fallback_model: (
        Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"] | None
    ) = None
    tally_result: AggregationResult | None = None

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None

    # v0.2.0
    mode: GroupDecisionMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: GroupDecisionProfilePattern = "indeterminate"
    fit_score: float = Field(default=0.5, ge=0.0, le=1.0)
    method_fit_audit: MethodFitAudit | None = None
    tally_integrity_audit: TallyIntegrityAudit | None = None
    interventions: list[GroupDecisionIntervention] = Field(default_factory=list)
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
        out.append("# Group Decision Protocol (Kaner / facilitator canon)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Generated by: {self.generator_model}_\n")
        if self.decision_id:
            out.append(f"_Decision: {self.decision_id}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Fit score: {self.fit_score:.2f} (severity: {self.severity})_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append(f"\n## Decision\n\n{self.title}\n")
        out.append(f"\n## Recommended Model\n\n**{self.recommended_model}**\n")
        out.append(f"\n{self.rationale}\n")
        out.append(f"\n**Threshold:** {self.threshold}\n")
        if self.quorum is not None:
            out.append(f"\n**Quorum:** {self.quorum} agents required\n")
        if self.tie_breaker:
            out.append(f"\n**Tie-breaker:** {self.tie_breaker}\n")
        if self.fallback_model:
            out.append(f"\n**Fallback model:** {self.fallback_model}\n")

        out.append("\n## Protocol Steps\n")
        for i, step in enumerate(self.protocol_steps, 1):
            out.append(f"{i}. {step}\n")

        if self.tally_result is not None:
            out.append("\n## Tally Result\n")
            out.append(f"- **Method used:** {self.tally_result.method_used}\n")
            out.append(f"- **Outcome:** {self.tally_result.outcome}\n")
            if self.tally_result.winner is not None:
                out.append(f"- **Winner:** `{self.tally_result.winner}`\n")
            if self.tally_result.vote_counts:
                out.append("- **Vote counts:**\n")
                for opt, count in self.tally_result.vote_counts.items():
                    out.append(f"  - `{opt}`: {count}\n")
            if self.tally_result.fist_to_five_averages:
                out.append("- **Fist-to-five averages:**\n")
                for opt, avg in self.tally_result.fist_to_five_averages.items():
                    out.append(f"  - `{opt}`: {avg:.2f}\n")
            if self.tally_result.dissenters:
                out.append(f"- **Dissenters:** {', '.join(self.tally_result.dissenters)}\n")
            if self.tally_result.explanation:
                out.append(f"\n{self.tally_result.explanation}\n")

        if self.method_fit_audit:
            ma = self.method_fit_audit
            out.append("\n## Method Fit Audit (Forensic)\n")
            out.append(
                f"- fit_score: {ma.fit_score:.2f}\n"
                f"- stakes_aligned: {ma.stakes_aligned}\n"
                f"- reversibility_aligned: {ma.reversibility_aligned}\n"
                f"- time_pressure_aligned: {ma.time_pressure_aligned}\n"
                f"- buy_in_aligned: {ma.buy_in_aligned}\n"
                f"- regulatory_aligned: {ma.regulatory_aligned}\n"
            )
            if ma.explanation:
                out.append(f"- {ma.explanation}\n")

        if self.tally_integrity_audit:
            ta = self.tally_integrity_audit
            out.append("\n## Tally Integrity Audit (Forensic)\n")
            out.append(
                f"- quorum_specified: {ta.quorum_specified}\n"
                f"- tie_breaker_specified: {ta.tie_breaker_specified}\n"
                f"- fallback_specified: {ta.fallback_specified}\n"
                f"- dissent_recording_specified: {ta.dissent_recording_specified}\n"
                f"- integrity_estimate: {ta.integrity_estimate:.2f}\n"
            )
            if ta.explanation:
                out.append(f"- {ta.explanation}\n")

        if self.interventions:
            out.append("\n## Quality Interventions\n")
            for i, iv in enumerate(self.interventions, 1):
                out.append(
                    f"\n### Intervention {i}: targets `{iv.target_dimension}` via "
                    f"`{iv.intervention_type}`\n"
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
                    f"\n### {pb.title} _(model={pb.model}, failure_mode={pb.failure_mode})_\n"
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

    def to_orchestrator_preamble(self) -> str:
        lines = [
            "DECISION PROTOCOL:",
            f"Title: {self.title}",
            f"Model: {self.recommended_model}",
            f"Threshold: {self.threshold}",
        ]
        if self.tie_breaker:
            lines.append(f"Tie-breaker: {self.tie_breaker}")
        if self.fallback_model:
            lines.append(f"Fallback if no convergence: {self.fallback_model}")
        lines.append("Protocol steps:")
        for i, step in enumerate(self.protocol_steps, 1):
            lines.append(f"  {i}. {step}")
        return "\n".join(lines)
