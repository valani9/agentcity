"""Schema for the Bias-Stack Detector.

Four canonical Kahneman/Tversky biases applied to agent reasoning:
anchoring, overconfidence, confirmation, escalation-of-commitment.

v0.2.0 adds three pipeline modes, a 7-point severity scale, eight
profile patterns, forensic-mode audits (Confidence Calibration,
Anchoring Trace), calibration baselines, composition handoff, attached
playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

BIASES: tuple[str, ...] = (
    "anchoring",
    "overconfidence",
    "confirmation",
    "escalation-of-commitment",
)

BiasStackMode = Literal["quick", "standard", "forensic"]
BIAS_STACK_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_bias(score: float) -> Severity:
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


BiasStackProfilePattern = Literal[
    "well_calibrated",
    "anchoring_dominant",
    "overconfidence_dominant",
    "confirmation_dominant",
    "escalation_dominant",
    "full_stack_severe",
    "anchoring_overconfidence_pair",
    "confirmation_escalation_pair",
    "indeterminate",
]
BIAS_STACK_PROFILE_PATTERNS: tuple[str, ...] = (
    "well_calibrated",
    "anchoring_dominant",
    "overconfidence_dominant",
    "confirmation_dominant",
    "escalation_dominant",
    "full_stack_severe",
    "anchoring_overconfidence_pair",
    "confirmation_escalation_pair",
    "indeterminate",
)


InterventionType = Literal[
    "prompt_patch",
    "scaffold_change",
    "retry_cap",
    "uncertainty_calibration",
    "first_principles_reset",
    "devils_advocate_role",
    "search_disconfirming_evidence",
    "anchor_to_base_rates",
    "new_eval",
    "human_review",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "prompt_patch",
    "scaffold_change",
    "retry_cap",
    "uncertainty_calibration",
    "first_principles_reset",
    "devils_advocate_role",
    "search_disconfirming_evidence",
    "anchor_to_base_rates",
    "new_eval",
    "human_review",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReasoningStep(BaseModel):
    type: Literal[
        "hypothesis",
        "tool_call",
        "observation",
        "decision",
        "thought",
        "retry",
        "conclusion",
    ]
    content: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentReasoningTrace(BaseModel):
    agent_id: str | None = None
    model_name: str | None = None
    framework: str | None = None
    task: str
    steps: list[ReasoningStep]
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


class BiasEvidence(BaseModel):
    bias: Literal[
        "anchoring",
        "overconfidence",
        "confirmation",
        "escalation-of-commitment",
    ]
    score: float = Field(ge=0.0, le=1.0)
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ConfidenceCalibrationAudit(BaseModel):
    """Forensic-mode: how well agent confidence tracked outcome correctness."""

    mean_self_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    overconfidence_gap: float = Field(default=0.0, ge=-1.0, le=1.0)
    calibration_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class AnchoringTraceAudit(BaseModel):
    """Forensic-mode: did first-hypothesis anchoring drive later steps?"""

    first_hypothesis_persistence: float = Field(default=0.0, ge=0.0, le=1.0)
    pivot_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    anchoring_estimate: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""


class BiasIntervention(BaseModel):
    target_bias: Literal[
        "anchoring",
        "overconfidence",
        "confirmation",
        "escalation-of-commitment",
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
    bias: str
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


class BiasStackDetection(BaseModel):
    agent_id: str | None = None
    model_name: str | None = None
    dominant_bias: Literal[
        "anchoring",
        "overconfidence",
        "confirmation",
        "escalation-of-commitment",
        "none-observed",
    ]
    bias_scores: dict[str, float]
    biases: list[BiasEvidence]
    interventions: list[BiasIntervention]
    overall_reasoning_quality: Literal["well-calibrated", "bias-prone", "severely-biased"]

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # v0.2.0
    mode: BiasStackMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: BiasStackProfilePattern = "indeterminate"
    calibration_audit: ConfidenceCalibrationAudit | None = None
    anchoring_audit: AnchoringTraceAudit | None = None
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
        out.append("# Bias-Stack Detection (Kahneman/Tversky)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(
            f"_Reasoning quality: **{self.overall_reasoning_quality.upper()}** "
            f"(severity: {self.severity})_\n"
        )
        out.append(f"_Dominant bias: **{self.dominant_bias}**_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Bias Scores\n")
        out.append("Per-bias score (0.0 = absent, 1.0 = severe).\n\n")
        for bias in BIASES:
            score = self.bias_scores.get(bias, 0.0)
            bar = "#" * int(round(score * 20))
            out.append(f"- **{bias}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Bias\n")
        for ev in self.biases:
            out.append(f"\n### {ev.bias} ({ev.severity}, score {ev.score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence from the trace:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        if self.calibration_audit:
            ca = self.calibration_audit
            out.append("\n## Confidence Calibration Audit (Forensic)\n")
            out.append(
                f"- mean_self_confidence: {ca.mean_self_confidence:.2f}\n"
                f"- overconfidence_gap: {ca.overconfidence_gap:+.2f}\n"
                f"- calibration_estimate: {ca.calibration_estimate:.2f}\n"
            )
            if ca.explanation:
                out.append(f"- {ca.explanation}\n")

        if self.anchoring_audit:
            aa = self.anchoring_audit
            out.append("\n## Anchoring Trace Audit (Forensic)\n")
            out.append(
                f"- first_hypothesis_persistence: {aa.first_hypothesis_persistence:.2f}\n"
                f"- pivot_count: {aa.pivot_count}\n"
                f"- retry_count: {aa.retry_count}\n"
                f"- anchoring_estimate: {aa.anchoring_estimate:.2f}\n"
            )
            if aa.explanation:
                out.append(f"- {aa.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_bias}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        if self.attached_playbooks:
            out.append("\n## Attached Playbooks\n")
            for pb in self.attached_playbooks:
                out.append(f"\n### {pb.title} _(bias={pb.bias}, failure_mode={pb.failure_mode})_\n")
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
