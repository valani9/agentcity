"""Schema for Glaser's Cortisol/Oxytocin Conversation Steering diagnostic.

Drawn from Judith Glaser, "Conversational Intelligence" (Bibliomotion, 2014).
Every conversational turn moves a participant toward cortisol dominance
(defensive) or oxytocin dominance (trusting/open). For AI agents, the
same dynamic applies in mirror form.

v0.2.0 adds three pipeline modes, a 7-point severity scale, nine
deterministic profile patterns, forensic-mode audits (Trigger Inventory,
Level Transition), calibration baselines, composition handoff,
attached playbooks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

CONVERSATION_LEVELS: tuple[str, ...] = ("level_i", "level_ii", "level_iii")
NEUROCHEMICAL_STATES: tuple[str, ...] = ("cortisol", "neutral", "oxytocin")

GlaserMode = Literal["quick", "standard", "forensic"]
GLASER_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

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


def severity_from_cortisol(cortisol_score: float) -> Severity:
    """Map cortisol dominance score (0 = absent, 1 = severe) to severity."""
    s = max(0.0, min(1.0, float(cortisol_score)))
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


GlaserProfilePattern = Literal[
    "trust_building_oxytocin",
    "neutral_transactional",
    "cortisol_cascade",
    "advocate_only_no_inquire",
    "blame_loaded_language",
    "agency_stripped",
    "level_i_stuck",
    "level_iii_collaborative",
    "indeterminate",
]
GLASER_PROFILE_PATTERNS: tuple[str, ...] = (
    "trust_building_oxytocin",
    "neutral_transactional",
    "cortisol_cascade",
    "advocate_only_no_inquire",
    "blame_loaded_language",
    "agency_stripped",
    "level_i_stuck",
    "level_iii_collaborative",
    "indeterminate",
)


InterventionType = Literal[
    "replace_telling_with_asking",
    "replace_judging_with_curiosity",
    "acknowledge_before_advocating",
    "soften_correction",
    "add_open_question",
    "remove_loaded_term",
    "add_agency_grant",
    "explicit_recovery_prompt",
    "rewrite_system_prompt",
    "new_eval",
    "human_review",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "replace_telling_with_asking",
    "replace_judging_with_curiosity",
    "acknowledge_before_advocating",
    "soften_correction",
    "add_open_question",
    "remove_loaded_term",
    "add_agency_grant",
    "explicit_recovery_prompt",
    "rewrite_system_prompt",
    "new_eval",
    "human_review",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConversationTurn(BaseModel):
    speaker: Literal["agent", "user", "other_agent"]
    text: str
    turn_index: int = Field(ge=0)


class ConversationTrace(BaseModel):
    conversation_id: str | None = None
    agent_id: str | None = None
    model_name: str | None = None
    framework: str | None = None
    task: str
    turns: list[ConversationTurn] = Field(min_length=1)
    observed_response_pattern: list[str] = Field(default_factory=list)
    outcome: str
    success: bool
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


class NeurochemicalEvidence(BaseModel):
    state: Literal["cortisol", "neutral", "oxytocin"]
    score: float = Field(ge=0.0, le=1.0)
    triggers: list[str] = Field(default_factory=list)
    explanation: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class TriggerInventoryAudit(BaseModel):
    """Forensic-mode: register of cortisol/oxytocin triggers in the trace."""

    cortisol_trigger_count: int = Field(default=0, ge=0)
    oxytocin_trigger_count: int = Field(default=0, ge=0)
    loaded_terms: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    inventory_quality: Literal["balanced", "cortisol_heavy", "oxytocin_heavy"] = "balanced"
    explanation: str = ""


class LevelTransitionAudit(BaseModel):
    """Forensic-mode: how the conversation moved across Glaser's levels."""

    level_i_turn_count: int = Field(default=0, ge=0)
    level_ii_turn_count: int = Field(default=0, ge=0)
    level_iii_turn_count: int = Field(default=0, ge=0)
    level_transitions: int = Field(default=0, ge=0)
    stuck_at_level: Literal["level_i", "level_ii", "level_iii", "none"] = "none"
    explanation: str = ""


class SteeringIntervention(BaseModel):
    target_state: Literal["oxytocin", "neutral"]
    intervention_type: InterventionType
    description: str
    original_phrasing: str = ""
    suggested_phrasing: str = ""
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    state: str
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


class ConversationSteeringDetection(BaseModel):
    conversation_id: str | None = None
    agent_id: str | None = None
    model_name: str | None = None
    dominant_state: Literal["cortisol", "neutral", "oxytocin"]
    conversation_level: Literal["level_i", "level_ii", "level_iii"]
    evidence: list[NeurochemicalEvidence]
    steering_quality: Literal["trust-building", "neutral", "trust-eroding"]
    interventions: list[SteeringIntervention]

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # v0.2.0
    mode: GlaserMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: GlaserProfilePattern = "indeterminate"
    trigger_inventory: TriggerInventoryAudit | None = None
    level_transition_audit: LevelTransitionAudit | None = None
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
        out.append("# Conversation Steering Diagnostic (Glaser C-IQ)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Conversation level: **{self.conversation_level}**_\n")
        out.append(
            f"_Dominant state: **{self.dominant_state.upper()}** (severity: {self.severity})_\n"
        )
        out.append(f"_Steering quality: **{self.steering_quality.upper()}**_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Per-State Evidence\n")
        for ev in self.evidence:
            bar = "#" * int(round(ev.score * 10))
            out.append(f"\n### {ev.state} (score {ev.score:.2f}) `{bar:<10}`\n")
            out.append(f"{ev.explanation}\n")
            if ev.triggers:
                out.append("\nTriggers:\n")
                for trigger in ev.triggers:
                    out.append(f"- {trigger}\n")

        if self.trigger_inventory:
            ti = self.trigger_inventory
            out.append("\n## Trigger Inventory Audit (Forensic)\n")
            out.append(
                f"- cortisol_trigger_count: {ti.cortisol_trigger_count}\n"
                f"- oxytocin_trigger_count: {ti.oxytocin_trigger_count}\n"
                f"- inventory_quality: {ti.inventory_quality}\n"
            )
            if ti.loaded_terms:
                out.append(f"- loaded_terms: {', '.join(ti.loaded_terms)}\n")
            if ti.open_questions:
                out.append(f"- open_questions: {len(ti.open_questions)} observed\n")
            if ti.explanation:
                out.append(f"- {ti.explanation}\n")

        if self.level_transition_audit:
            lt = self.level_transition_audit
            out.append("\n## Level Transition Audit (Forensic)\n")
            out.append(
                f"- level_i: {lt.level_i_turn_count}\n"
                f"- level_ii: {lt.level_ii_turn_count}\n"
                f"- level_iii: {lt.level_iii_turn_count}\n"
                f"- transitions: {lt.level_transitions}\n"
                f"- stuck_at_level: {lt.stuck_at_level}\n"
            )
            if lt.explanation:
                out.append(f"- {lt.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: steer toward `{iv.target_state}` "
                f"via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            if iv.original_phrasing:
                out.append(f"- **Replace:** _{iv.original_phrasing}_\n")
            if iv.suggested_phrasing:
                out.append(f"- **With:** _{iv.suggested_phrasing}_\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        if self.attached_playbooks:
            out.append("\n## Attached Playbooks\n")
            for pb in self.attached_playbooks:
                out.append(
                    f"\n### {pb.title} _(state={pb.state}, failure_mode={pb.failure_mode})_\n"
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
