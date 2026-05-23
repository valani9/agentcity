"""Schema for the Edmondson Psychological Safety diagnostic.

Anchored in Edmondson (1999) Psychological Safety and Learning Behavior in
Work Teams, plus Edmondson (2018) The Fearless Organization. Applied to
multi-agent AI systems: the four observable safety behaviors are voice,
help-seeking, error-reporting, and boundary-spanning. Their presence vs
suppression in a multi-agent trace is the diagnostic signal.

v0.2.0 adds three pipeline modes, a 7-point severity scale, nine
deterministic profile patterns, forensic-mode audits (Voice signal,
Error-reporting culture), calibration baselines, composition handoff,
and attached playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

BEHAVIORS: tuple[str, ...] = (
    "voice",
    "help-seeking",
    "error-reporting",
    "boundary-spanning",
)

PsychSafetyMode = Literal["quick", "standard", "forensic"]
PSYCH_SAFETY_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_absence(absence_score: float) -> Severity:
    """Map absence-score (0 = behavior present, 1 = absent) to severity."""
    s = max(0.0, min(1.0, float(absence_score)))
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


PsychSafetyProfilePattern = Literal[
    "safe_team",
    "silenced_team",
    "cautious_team",
    "voice_absent",
    "error_concealment",
    "help_seeking_blocked",
    "siloed_no_boundary_spanning",
    "all_four_suppressed",
    "indeterminate",
]
PSYCH_SAFETY_PROFILE_PATTERNS: tuple[str, ...] = (
    "safe_team",
    "silenced_team",
    "cautious_team",
    "voice_absent",
    "error_concealment",
    "help_seeking_blocked",
    "siloed_no_boundary_spanning",
    "all_four_suppressed",
    "indeterminate",
)


InterventionType = Literal[
    "prompt_patch",
    "scaffold_change",
    "role_assignment",
    "new_eval",
    "human_review",
    "norms_in_working_agreement",
    "dissent_round",
    "uncertainty_surfacing",
    "error_amnesty_policy",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "prompt_patch",
    "scaffold_change",
    "role_assignment",
    "new_eval",
    "human_review",
    "norms_in_working_agreement",
    "dissent_round",
    "uncertainty_surfacing",
    "error_amnesty_policy",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentMessage(BaseModel):
    timestamp: datetime | None = None
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
        "admission",
        "help_request",
    ]
    metadata: dict[str, Any] = Field(default_factory=dict)


class MultiAgentSafetyTrace(BaseModel):
    team_id: str | None = None
    framework: str | None = None
    goal: str
    agents: list[str]
    messages: list[AgentMessage]
    outcome: str
    success: bool
    cost_usd: float | None = None
    latency_seconds: float | None = None
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("goal", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


class BehaviorEvidence(BaseModel):
    behavior: Literal["voice", "help-seeking", "error-reporting", "boundary-spanning"]
    presence_score: float = Field(ge=0.0, le=1.0)
    severity_of_absence: Literal["none", "low", "medium", "high"] = "none"
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class VoiceSignalAudit(BaseModel):
    """Forensic-mode: voice / challenge signal in the trace."""

    challenge_message_count: int = Field(default=0, ge=0)
    agreement_only_message_count: int = Field(default=0, ge=0)
    voice_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class ErrorReportingAudit(BaseModel):
    """Forensic-mode: error-reporting culture in the trace."""

    admitted_error_count: int = Field(default=0, ge=0)
    concealed_error_count: int = Field(default=0, ge=0)
    error_reporting_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class SafetyIntervention(BaseModel):
    target_behavior: Literal["voice", "help-seeking", "error-reporting", "boundary-spanning"]
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    behavior: str
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


class PsychologicalSafetyDetection(BaseModel):
    team_id: str | None = None
    safety_score: float = Field(ge=0.0, le=1.0)
    team_climate: Literal["safe", "cautious", "silenced"]
    behavior_scores: dict[str, float]
    behaviors: list[BehaviorEvidence]
    blocking_behaviors: list[str] = Field(default_factory=list)
    interventions: list[SafetyIntervention]

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # v0.2.0
    mode: PsychSafetyMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: PsychSafetyProfilePattern = "indeterminate"
    voice_audit: VoiceSignalAudit | None = None
    error_reporting_audit: ErrorReportingAudit | None = None
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
        out.append("# Psychological Safety Score (Edmondson)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Safety score: **{self.safety_score:.2f}**_\n")
        out.append(f"_Team climate: **{self.team_climate.upper()}** (severity: {self.severity})_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Behavior Presence Scores\n")
        out.append("Per-behavior presence (0.0 = absent, 1.0 = strongly present).\n\n")
        for b in BEHAVIORS:
            score = self.behavior_scores.get(b, 0.0)
            bar = "#" * int(round(score * 20))
            out.append(f"- **{b}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Behavior\n")
        for ev in self.behaviors:
            out.append(
                f"\n### {ev.behavior} ({ev.severity_of_absence} absence, "
                f"presence {ev.presence_score:.2f})\n"
            )
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for q in ev.evidence_quotes:
                    out.append(f"> {q}\n")

        if self.blocking_behaviors:
            out.append("\n## Blocking Behaviors (suppressing safety)\n")
            for b in self.blocking_behaviors:
                out.append(f"- {b}\n")

        if self.voice_audit:
            va = self.voice_audit
            out.append("\n## Voice Signal Audit (Forensic)\n")
            out.append(
                f"- challenge_message_count: {va.challenge_message_count}\n"
                f"- agreement_only_message_count: {va.agreement_only_message_count}\n"
                f"- voice_estimate: {va.voice_estimate:.2f}\n"
            )
            if va.explanation:
                out.append(f"- {va.explanation}\n")

        if self.error_reporting_audit:
            ea = self.error_reporting_audit
            out.append("\n## Error Reporting Audit (Forensic)\n")
            out.append(
                f"- admitted_error_count: {ea.admitted_error_count}\n"
                f"- concealed_error_count: {ea.concealed_error_count}\n"
                f"- error_reporting_estimate: {ea.error_reporting_estimate:.2f}\n"
            )
            if ea.explanation:
                out.append(f"- {ea.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: grows `{iv.target_behavior}` via "
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
                    f"\n### {pb.title} _(behavior={pb.behavior}, failure_mode={pb.failure_mode})_\n"
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
