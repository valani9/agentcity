"""Schema for the Trust Triangle Audit applied to AI agents.

Frei & Morriss's three legs of trust (Harvard Business Review, May 2020):

  AUTHENTICITY  - "I experience the real you."
       /\\
      /  \\
     /    \\
  LOGIC -- EMPATHY
  "Your    "I believe you
  reasoning care about me
  is sound." and my success."

Most leaders (and most agents) wobble on exactly one leg consistently.
The Audit identifies the wobble and proposes interventions targeted to
the dominant leg.

v0.2.0 adds three pipeline modes, a 7-point severity scale, eight
deterministic profile patterns, forensic-mode audits (Hallucination,
Sycophancy, Context Sensitivity), calibration baselines, composition
handoff, and attached playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

LEGS: tuple[str, ...] = ("logic", "authenticity", "empathy")

TrustTriangleMode = Literal["quick", "standard", "forensic"]
TRUST_TRIANGLE_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_wobble(score: float) -> Severity:
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


TrustProfilePattern = Literal[
    "healthy_trust",
    "logic_wobble_dominant",
    "authenticity_wobble_dominant",
    "empathy_wobble_dominant",
    "full_triangle_collapse",
    "logic_authenticity_paired",
    "empathy_isolated_wobble",
    "indeterminate",
]
TRUST_PROFILE_PATTERNS: tuple[str, ...] = (
    "healthy_trust",
    "logic_wobble_dominant",
    "authenticity_wobble_dominant",
    "empathy_wobble_dominant",
    "full_triangle_collapse",
    "logic_authenticity_paired",
    "empathy_isolated_wobble",
    "indeterminate",
)


InterventionType = Literal[
    "prompt_patch",
    "tool_addition",
    "scaffold_change",
    "new_eval",
    "uncertainty_calibration",
    "context_window_expansion",
    "human_review",
    "retrieval_augmentation",
    "sycophancy_filter",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "prompt_patch",
    "tool_addition",
    "scaffold_change",
    "new_eval",
    "uncertainty_calibration",
    "context_window_expansion",
    "human_review",
    "retrieval_augmentation",
    "sycophancy_filter",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InteractionTurn(BaseModel):
    role: Literal["user", "agent", "system", "tool", "observation"]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentInteractionTrace(BaseModel):
    agent_id: str | None = None
    model_name: str | None = None
    framework: str | None = None
    task: str
    turns: list[InteractionTurn]
    outcome: str
    success: bool
    user_satisfaction: float | None = None
    cost_usd: float | None = None
    latency_seconds: float | None = None
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


class LegEvidence(BaseModel):
    leg: Literal["logic", "authenticity", "empathy"]
    wobble_score: float = Field(ge=0.0, le=1.0)
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class HallucinationAudit(BaseModel):
    """Forensic-mode: ungrounded factual claims drive logic wobble."""

    ungrounded_claim_count: int = Field(default=0, ge=0)
    contradicted_claim_count: int = Field(default=0, ge=0)
    hallucination_estimate: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""


class SycophancyAudit(BaseModel):
    """Forensic-mode: agreement-without-evidence drives authenticity wobble."""

    sycophantic_turn_count: int = Field(default=0, ge=0)
    pushback_count: int = Field(default=0, ge=0)
    sycophancy_estimate: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""


class ContextSensitivityAudit(BaseModel):
    """Forensic-mode: missing user context drives empathy wobble."""

    missed_context_signal_count: int = Field(default=0, ge=0)
    addressed_context_signal_count: int = Field(default=0, ge=0)
    context_sensitivity_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class TrustIntervention(BaseModel):
    target_leg: Literal["logic", "authenticity", "empathy"]
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    leg: str
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


class TrustTriangleAudit(BaseModel):
    agent_id: str | None = None
    model_name: str | None = None
    dominant_wobble: Literal["logic", "authenticity", "empathy", "none-observed"]
    leg_scores: dict[str, float]
    legs: list[LegEvidence]
    interventions: list[TrustIntervention]
    overall_trust_level: Literal["high-trust", "moderate-trust", "low-trust"]

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # v0.2.0
    mode: TrustTriangleMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: TrustProfilePattern = "indeterminate"
    hallucination_audit: HallucinationAudit | None = None
    sycophancy_audit: SycophancyAudit | None = None
    context_sensitivity_audit: ContextSensitivityAudit | None = None
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
        out.append("# Trust Triangle Audit\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Audited by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(
            f"_Trust level: **{self.overall_trust_level.upper()}** (severity: {self.severity})_\n"
        )
        out.append(f"_Dominant wobble: **{self.dominant_wobble}**_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Leg Scores\n")
        out.append("Per-leg wobble (0.0 = rock-solid, 1.0 = severe). Higher = worse.\n\n")
        for leg in LEGS:
            score = self.leg_scores.get(leg, 0.0)
            bar = "#" * int(round(score * 20))
            out.append(f"- **{leg}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Leg\n")
        for ev in self.legs:
            out.append(f"\n### {ev.leg} ({ev.severity}, wobble {ev.wobble_score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence from the trace:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        if self.hallucination_audit:
            ha = self.hallucination_audit
            out.append("\n## Hallucination Audit (Forensic)\n")
            out.append(
                f"- ungrounded_claim_count: {ha.ungrounded_claim_count}\n"
                f"- contradicted_claim_count: {ha.contradicted_claim_count}\n"
                f"- hallucination_estimate: {ha.hallucination_estimate:.2f}\n"
            )
            if ha.explanation:
                out.append(f"- {ha.explanation}\n")

        if self.sycophancy_audit:
            sa = self.sycophancy_audit
            out.append("\n## Sycophancy Audit (Forensic)\n")
            out.append(
                f"- sycophantic_turn_count: {sa.sycophantic_turn_count}\n"
                f"- pushback_count: {sa.pushback_count}\n"
                f"- sycophancy_estimate: {sa.sycophancy_estimate:.2f}\n"
            )
            if sa.explanation:
                out.append(f"- {sa.explanation}\n")

        if self.context_sensitivity_audit:
            ca = self.context_sensitivity_audit
            out.append("\n## Context Sensitivity Audit (Forensic)\n")
            out.append(
                f"- missed_context_signal_count: {ca.missed_context_signal_count}\n"
                f"- addressed_context_signal_count: {ca.addressed_context_signal_count}\n"
                f"- context_sensitivity_estimate: {ca.context_sensitivity_estimate:.2f}\n"
            )
            if ca.explanation:
                out.append(f"- {ca.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_leg}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        if self.attached_playbooks:
            out.append("\n## Attached Playbooks\n")
            for pb in self.attached_playbooks:
                out.append(f"\n### {pb.title} _(leg={pb.leg}, failure_mode={pb.failure_mode})_\n")
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
