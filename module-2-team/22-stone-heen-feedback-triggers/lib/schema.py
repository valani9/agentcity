"""Schema for Stone & Heen's 3-Trigger Feedback diagnostic.

Three classic triggers that block feedback intake (Stone & Heen 2014):
  - TRUTH        - "The feedback is wrong/unfair." Reaction to substance.
  - RELATIONSHIP - "I reject the feedback because of WHO gave it / HOW."
  - IDENTITY     - "This feedback threatens who I am."

Applied to AI agents: when a user corrects an agent, the agent visibly
triggers (defends, deflects, repeats) and fails to absorb the correction.

v0.2.0 adds three pipeline modes, 7-point severity, eight profile
patterns, forensic-mode audits (Defense Pattern, Source Attribution),
calibration baselines, composition handoff, attached playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

TRIGGERS: tuple[str, ...] = ("truth", "relationship", "identity")

FeedbackTriggersMode = Literal["quick", "standard", "forensic"]
FEEDBACK_TRIGGERS_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_trigger(score: float) -> Severity:
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


FeedbackProfilePattern = Literal[
    "absorbing_baseline",
    "truth_triggered_defensive",
    "relationship_triggered_rejection",
    "identity_triggered_collapse",
    "multi_triggered_resistant",
    "deflection_pattern",
    "performative_acknowledgement",
    "indeterminate",
]
FEEDBACK_PROFILE_PATTERNS: tuple[str, ...] = (
    "absorbing_baseline",
    "truth_triggered_defensive",
    "relationship_triggered_rejection",
    "identity_triggered_collapse",
    "multi_triggered_resistant",
    "deflection_pattern",
    "performative_acknowledgement",
    "indeterminate",
)


InterventionType = Literal[
    "acknowledge_first",
    "separate_data_from_source",
    "recast_identity",
    "explicit_acknowledgment_template",
    "ask_clarifying_question",
    "concede_then_clarify",
    "new_eval",
    "human_review",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "acknowledge_first",
    "separate_data_from_source",
    "recast_identity",
    "explicit_acknowledgment_template",
    "ask_clarifying_question",
    "concede_then_clarify",
    "new_eval",
    "human_review",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FeedbackMessage(BaseModel):
    source: Literal["user", "agent", "system"]
    content: str
    is_feedback: bool = False
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackInteractionTrace(BaseModel):
    agent_id: str | None = None
    model_name: str | None = None
    framework: str | None = None
    task: str
    messages: list[FeedbackMessage]
    outcome: str
    feedback_incorporated: bool
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


class TriggerEvidence(BaseModel):
    trigger: Literal["truth", "relationship", "identity"]
    score: float = Field(ge=0.0, le=1.0)
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class DefensePatternAudit(BaseModel):
    """Forensic-mode: how the agent defended (deflect/repeat/justify)."""

    deflection_count: int = Field(default=0, ge=0)
    repetition_count: int = Field(default=0, ge=0)
    justification_count: int = Field(default=0, ge=0)
    concession_count: int = Field(default=0, ge=0)
    defense_intensity: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""


class SourceAttributionAudit(BaseModel):
    """Forensic-mode: did agent attack the source instead of the data?"""

    source_attack_count: int = Field(default=0, ge=0)
    data_engagement_count: int = Field(default=0, ge=0)
    source_attribution_estimate: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""


class TriggerIntervention(BaseModel):
    target_trigger: Literal["truth", "relationship", "identity"]
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    trigger: str
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


class FeedbackTriggerDetection(BaseModel):
    agent_id: str | None = None
    model_name: str | None = None
    dominant_trigger: Literal["truth", "relationship", "identity", "none-observed"]
    trigger_scores: dict[str, float]
    triggers: list[TriggerEvidence]
    interventions: list[TriggerIntervention]
    feedback_intake_quality: Literal[
        "absorbs-feedback",
        "trigger-prone",
        "feedback-rejecting",
    ]

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    feedback_incorporated: bool = False

    # v0.2.0
    mode: FeedbackTriggersMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: FeedbackProfilePattern = "indeterminate"
    defense_pattern_audit: DefensePatternAudit | None = None
    source_attribution_audit: SourceAttributionAudit | None = None
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
        out.append("# Feedback-Trigger Detection (Stone & Heen)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Feedback incorporated: {'yes' if self.feedback_incorporated else 'no'}_\n")
        out.append(
            f"_Intake quality: **{self.feedback_intake_quality.upper()}** "
            f"(severity: {self.severity})_\n"
        )
        out.append(f"_Dominant trigger: **{self.dominant_trigger}**_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Trigger Scores\n")
        out.append("Per-trigger score (0.0 = absent, 1.0 = severe).\n\n")
        for trigger in TRIGGERS:
            score = self.trigger_scores.get(trigger, 0.0)
            bar = "#" * int(round(score * 20))
            out.append(f"- **{trigger}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Trigger\n")
        for ev in self.triggers:
            out.append(f"\n### {ev.trigger} ({ev.severity}, score {ev.score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence from the exchange:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        if self.defense_pattern_audit:
            da = self.defense_pattern_audit
            out.append("\n## Defense Pattern Audit (Forensic)\n")
            out.append(
                f"- deflection_count: {da.deflection_count}\n"
                f"- repetition_count: {da.repetition_count}\n"
                f"- justification_count: {da.justification_count}\n"
                f"- concession_count: {da.concession_count}\n"
                f"- defense_intensity: {da.defense_intensity:.2f}\n"
            )
            if da.explanation:
                out.append(f"- {da.explanation}\n")

        if self.source_attribution_audit:
            sa = self.source_attribution_audit
            out.append("\n## Source Attribution Audit (Forensic)\n")
            out.append(
                f"- source_attack_count: {sa.source_attack_count}\n"
                f"- data_engagement_count: {sa.data_engagement_count}\n"
                f"- source_attribution_estimate: {sa.source_attribution_estimate:.2f}\n"
            )
            if sa.explanation:
                out.append(f"- {sa.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_trigger}` via "
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
                    f"\n### {pb.title} _(trigger={pb.trigger}, failure_mode={pb.failure_mode})_\n"
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
