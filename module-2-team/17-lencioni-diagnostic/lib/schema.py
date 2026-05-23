"""Schema for the Lencioni Five Dysfunctions Diagnostic.

Anchored in:
  - Lencioni, P. (2002) *The Five Dysfunctions of a Team.* Jossey-Bass.
  - Lencioni, P. (2005) *Overcoming the Five Dysfunctions of a Team.* Jossey-Bass.
  - Edmondson, A. C. (1999) Psychological safety.
  - Hackman, J. R. (2002) *Leading Teams*.
  - Salas, E., et al. (2018) Team performance review.
  - Schein, E. H. (1990) *Organizational Culture and Leadership*.
  - Wang et al. (2023) Cooperative LLM Agents.

Pyramid (foundation up):
  1. ABSENCE OF TRUST
  2. FEAR OF CONFLICT
  3. LACK OF COMMITMENT
  4. AVOIDANCE OF ACCOUNTABILITY
  5. INATTENTION TO RESULTS
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

DYSFUNCTIONS: tuple[str, ...] = (
    "absence-of-trust",
    "fear-of-conflict",
    "lack-of-commitment",
    "avoidance-of-accountability",
    "inattention-to-results",
)

LencioniMode = Literal["quick", "standard", "forensic"]
LENCIONI_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

Severity = Literal["none", "trace", "low", "moderate", "medium", "high", "critical"]
SEVERITY_ORDER: tuple[str, ...] = ("none", "trace", "low", "moderate", "medium", "high", "critical")


def severity_from_score(score: float) -> Severity:
    s = max(0.0, min(1.0, float(score)))
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


LencioniProfilePattern = Literal[
    "healthy_team",
    "foundational_trust_collapse",  # dysfunction #1 dominant
    "conflict_avoidance",  # #2 dominant
    "commitment_collapse",  # #3 dominant
    "accountability_void",  # #4 dominant
    "results_inattention",  # #5 dominant
    "full_pyramid_dysfunction",  # all 5 >= 0.5
    "foundation_unstable_top_strong",  # #1-2 high but #5 low
    "indeterminate",
]
LENCIONI_PROFILE_PATTERNS: tuple[str, ...] = (
    "healthy_team",
    "foundational_trust_collapse",
    "conflict_avoidance",
    "commitment_collapse",
    "accountability_void",
    "results_inattention",
    "full_pyramid_dysfunction",
    "foundation_unstable_top_strong",
    "indeterminate",
)

InterventionType = Literal[
    "scaffold_change",
    "prompt_patch",
    "role_assignment",
    "new_eval",
    "human_review",
    "team_composition_change",
    "communication_protocol",
    "add_psych_safety_signal",
    "structured_dissent_protocol",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "scaffold_change",
    "prompt_patch",
    "role_assignment",
    "new_eval",
    "human_review",
    "team_composition_change",
    "communication_protocol",
    "add_psych_safety_signal",
    "structured_dissent_protocol",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentMessage(BaseModel):
    timestamp: datetime
    from_agent: str
    to_agent: str | None = None
    content: str
    message_type: Literal[
        "task",
        "response",
        "challenge",
        "agreement",
        "question",
        "vote",
        "decision",
        "observation",
        "tool_call",
        "tool_result",
    ]
    metadata: dict[str, Any] = Field(default_factory=dict)


class MultiAgentTrace(BaseModel):
    team_id: str | None = None
    framework: str | None = None
    goal: str
    agents: list[str]
    messages: list[AgentMessage]
    outcome: str
    success: bool = False
    cost_usd: float | None = None
    latency_seconds: float | None = None
    # New in v0.2.0.
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("goal", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


class DysfunctionEvidence(BaseModel):
    dysfunction: Literal[
        "absence-of-trust",
        "fear-of-conflict",
        "lack-of-commitment",
        "avoidance-of-accountability",
        "inattention-to-results",
    ]
    severity: Literal["high", "medium", "low", "none"]
    score: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class CascadeAudit(BaseModel):
    """Forensic-mode: does the foundation actually cause higher-tier issues?"""

    foundation_dominant: bool = False
    cascade_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    bottom_two_score: float = Field(default=0.0, ge=0.0, le=1.0)
    top_three_score: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""


class PsychSafetyAudit(BaseModel):
    """Forensic-mode: Edmondson psychological-safety signal in the trace."""

    challenge_signal_count: int = Field(default=0, ge=0)
    silent_dissent_count: int = Field(default=0, ge=0)
    safety_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class Intervention(BaseModel):
    target_dysfunction: Literal[
        "absence-of-trust",
        "fear-of-conflict",
        "lack-of-commitment",
        "avoidance-of-accountability",
        "inattention-to-results",
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
    dysfunction: str
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


class LencioniDiagnosis(BaseModel):
    team_id: str | None = None
    dominant_dysfunction: Literal[
        "absence-of-trust",
        "fear-of-conflict",
        "lack-of-commitment",
        "avoidance-of-accountability",
        "inattention-to-results",
        "none-observed",
    ]
    pyramid_score: dict[str, float]
    dysfunctions: list[DysfunctionEvidence]
    interventions: list[Intervention]
    overall_team_health: Literal["healthy", "stressed", "dysfunctional"]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0.
    mode: LencioniMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: LencioniProfilePattern = "indeterminate"
    cascade_audit: CascadeAudit | None = None
    psych_safety_audit: PsychSafetyAudit | None = None
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
        out.append("# Lencioni Five Dysfunctions Diagnostic\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Model: {self.generator_model}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(
            f"_Overall team health: **{self.overall_team_health.upper()}** "
            f"(severity: {self.severity})_\n"
        )
        out.append(f"_Dominant dysfunction: **{self.dominant_dysfunction}**_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Pyramid Score\n")
        out.append("In pyramid order (foundation first). Higher score = more severe.\n\n")
        for d in DYSFUNCTIONS:
            score = self.pyramid_score.get(d, 0.0)
            bar = "#" * int(round(score * 20))
            out.append(f"- **{d}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Dysfunction\n")
        for ev in self.dysfunctions:
            out.append(f"\n### {ev.dysfunction} ({ev.severity}, score {ev.score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence from the trace:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        if self.cascade_audit:
            ca = self.cascade_audit
            out.append("\n## Cascade Audit (Forensic)\n")
            out.append(
                f"- foundation_dominant: {ca.foundation_dominant}\n"
                f"- cascade_strength: {ca.cascade_strength:.2f}\n"
                f"- bottom_two_score: {ca.bottom_two_score:.2f}\n"
                f"- top_three_score: {ca.top_three_score:.2f}\n"
            )
            if ca.explanation:
                out.append(f"- {ca.explanation}\n")

        if self.psych_safety_audit:
            ps = self.psych_safety_audit
            out.append("\n## Psychological Safety Audit (Forensic; Edmondson)\n")
            out.append(
                f"- challenge_signal_count: {ps.challenge_signal_count}\n"
                f"- silent_dissent_count: {ps.silent_dissent_count}\n"
                f"- safety_estimate: {ps.safety_estimate:.2f}\n"
            )
            if ps.explanation:
                out.append(f"- {ps.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_dysfunction}` "
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
                    f"\n### {pb.title} _(dysfunction={pb.dysfunction}, "
                    f"failure_mode={pb.failure_mode})_\n"
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
