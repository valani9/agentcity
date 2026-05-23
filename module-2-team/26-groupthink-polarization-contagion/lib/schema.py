"""Schema for the Groupthink / Polarization / Emotional Contagion Detector.

Three dysfunctional dynamics:
  - GROUPTHINK   (Janis 1972) - premature convergence + dissent suppression
  - POLARIZATION (Stoner 1968) - rounds push toward an extreme
  - CONTAGION    (Hatfield/Cacioppo/Rapson 1993) - tone propagates across turns

v0.2.0 adds three pipeline modes, a 7-point severity scale, eight
profile patterns, forensic-mode audits (Convergence Timeline, Tone
Cascade), calibration baselines, composition handoff, attached
playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

PATHOLOGIES: tuple[str, ...] = ("groupthink", "polarization", "contagion")

DebatePathologyMode = Literal["quick", "standard", "forensic"]
DEBATE_PATHOLOGY_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_pathology(score: float) -> Severity:
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


DebatePathologyProfilePattern = Literal[
    "healthy_debate",
    "groupthink_collapse",
    "polarization_runaway",
    "contagion_dominated",
    "multi_pathology_severe",
    "premature_convergence",
    "tone_overrides_content",
    "dissent_suppressed",
    "indeterminate",
]
DEBATE_PATHOLOGY_PROFILE_PATTERNS: tuple[str, ...] = (
    "healthy_debate",
    "groupthink_collapse",
    "polarization_runaway",
    "contagion_dominated",
    "multi_pathology_severe",
    "premature_convergence",
    "tone_overrides_content",
    "dissent_suppressed",
    "indeterminate",
)


InterventionType = Literal[
    "assign_devils_advocate",
    "require_silent_vote",
    "round_robin_dissent",
    "diverse_seed_positions",
    "anchor_to_base_rates",
    "tone_normalization",
    "cool_down_pause",
    "external_arbiter",
    "smaller_panel",
    "secret_ballot",
    "new_eval",
    "human_review",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "assign_devils_advocate",
    "require_silent_vote",
    "round_robin_dissent",
    "diverse_seed_positions",
    "anchor_to_base_rates",
    "tone_normalization",
    "cool_down_pause",
    "external_arbiter",
    "smaller_panel",
    "secret_ballot",
    "new_eval",
    "human_review",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DebateMessage(BaseModel):
    round: int = Field(ge=1)
    from_agent: str
    position: str = ""
    emotional_tone: Literal[
        "calm",
        "neutral",
        "heated",
        "anxious",
        "enthusiastic",
        "dismissive",
        "unknown",
    ] = "unknown"
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MultiAgentDebateTrace(BaseModel):
    debate_id: str | None = None
    framework: str | None = None
    task: str
    agents: list[str]
    messages: list[DebateMessage]
    final_decision: str
    outcome: str
    success: bool
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "final_decision")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


class PathologyEvidence(BaseModel):
    pathology: Literal["groupthink", "polarization", "contagion"]
    score: float = Field(ge=0.0, le=1.0)
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ConvergenceTimelineAudit(BaseModel):
    """Forensic-mode: when + how positions converged across rounds."""

    initial_position_diversity: float = Field(default=0.5, ge=0.0, le=1.0)
    final_position_diversity: float = Field(default=0.5, ge=0.0, le=1.0)
    convergence_round: int | None = None
    abrupt_convergence: bool = False
    explanation: str = ""


class ToneCascadeAudit(BaseModel):
    """Forensic-mode: how tone propagated across turns."""

    heated_turn_count: int = Field(default=0, ge=0)
    calm_turn_count: int = Field(default=0, ge=0)
    tone_flip_count: int = Field(default=0, ge=0)
    dominant_tone: Literal[
        "calm", "neutral", "heated", "anxious", "enthusiastic", "dismissive", "unknown"
    ] = "unknown"
    cascade_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""


class DebateIntervention(BaseModel):
    target_pathology: Literal["groupthink", "polarization", "contagion"]
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    pathology: str
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


class DebatePathologyDetection(BaseModel):
    debate_id: str | None = None
    dominant_pathology: Literal["groupthink", "polarization", "contagion", "none-observed"]
    pathology_scores: dict[str, float]
    pathologies: list[PathologyEvidence]
    debate_quality: Literal["healthy", "at-risk", "pathological"]
    convergence_round: int | None = None
    interventions: list[DebateIntervention]

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # v0.2.0
    mode: DebatePathologyMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: DebatePathologyProfilePattern = "indeterminate"
    convergence_audit: ConvergenceTimelineAudit | None = None
    tone_cascade_audit: ToneCascadeAudit | None = None
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
        out.append("# Debate-Pathology Detection (Groupthink / Polarization / Contagion)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.debate_id:
            out.append(f"_Debate: {self.debate_id}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(
            f"_Debate quality: **{self.debate_quality.upper()}** (severity: {self.severity})_\n"
        )
        out.append(f"_Dominant pathology: **{self.dominant_pathology}**_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.convergence_round is not None:
            out.append(f"_Convergence round: {self.convergence_round}_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Pathology Scores\n")
        out.append("Per-pathology score (0.0 = absent, 1.0 = severe).\n\n")
        for p in PATHOLOGIES:
            score = self.pathology_scores.get(p, 0.0)
            bar = "#" * int(round(score * 20))
            out.append(f"- **{p}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Pathology\n")
        for ev in self.pathologies:
            out.append(f"\n### {ev.pathology} ({ev.severity}, score {ev.score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence from the debate:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        if self.convergence_audit:
            ca = self.convergence_audit
            out.append("\n## Convergence Timeline Audit (Forensic)\n")
            out.append(
                f"- initial_position_diversity: {ca.initial_position_diversity:.2f}\n"
                f"- final_position_diversity: {ca.final_position_diversity:.2f}\n"
                f"- convergence_round: {ca.convergence_round}\n"
                f"- abrupt_convergence: {ca.abrupt_convergence}\n"
            )
            if ca.explanation:
                out.append(f"- {ca.explanation}\n")

        if self.tone_cascade_audit:
            tc = self.tone_cascade_audit
            out.append("\n## Tone Cascade Audit (Forensic)\n")
            out.append(
                f"- heated_turn_count: {tc.heated_turn_count}\n"
                f"- calm_turn_count: {tc.calm_turn_count}\n"
                f"- tone_flip_count: {tc.tone_flip_count}\n"
                f"- dominant_tone: {tc.dominant_tone}\n"
                f"- cascade_strength: {tc.cascade_strength:.2f}\n"
            )
            if tc.explanation:
                out.append(f"- {tc.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_pathology}` via "
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
                    f"\n### {pb.title} _(pathology={pb.pathology}, "
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
