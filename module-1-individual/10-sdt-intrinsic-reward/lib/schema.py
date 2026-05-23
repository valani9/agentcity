"""Schema for the SDT (Self-Determination Theory) Intrinsic Reward Diagnostic.

Anchored in:
  - Deci, E. L., & Ryan, R. M. (1985) *Intrinsic Motivation and
    Self-Determination in Human Behavior.* Plenum -- the canonical SDT
    statement.
  - Ryan, R. M., & Deci, E. L. (2000) ``Self-Determination Theory and
    the Facilitation of Intrinsic Motivation.'' American Psychologist
    55, 68-78.
  - Deci, E. L., & Ryan, R. M. (2017) *Self-Determination Theory:
    Basic Psychological Needs in Motivation, Development, and Wellness.*
    Guilford.
  - Deci, E. L. (1971) ``Effects of Externally Mediated Rewards on
    Intrinsic Motivation.'' Journal of Personality and Social Psychology
    18, 105-115 -- the original **overjustification** finding.
  - Pink, D. H. (2009) *Drive: The Surprising Truth About What Motivates
    Us.* Riverhead -- the popular synthesis (Autonomy / Mastery / Purpose).
  - Gagne, M., & Deci, E. L. (2005) ``Self-Determination Theory and
    Work Motivation.'' Journal of Organizational Behavior 26, 331-362.
  - Casper et al. (2023) ``Open Problems and Fundamental Limitations
    of RLHF'' -- the modern LLM reward-shaping anchor.

SDT proposes three independent basic psychological needs:

  - AUTONOMY    -- sense of choice and self-direction.
  - COMPETENCE  -- sense of effectiveness and mastery growth.
  - RELATEDNESS -- sense of connection to others / to purpose.

When all three are met, intrinsic motivation is high. SDT's central
prediction: EXTRINSIC reward (money, points, ratings, leaderboards)
can UNDERMINE intrinsic motivation by reducing the autonomy signal --
the **overjustification effect**.

For AI agents, "motivation" is shorthand for reward-shaping (system
prompt + RLHF training + runtime context). System prompts that
emphasize external reward ("you will be rated", "minimize cost") often
elicit autonomy-undermined behavior (rigid rule-following, metric-
gaming, refusal to deviate). System prompts that grant choice +
scaffold mastery + ground in purpose elicit higher intrinsic-style
behavior (exploration, recovery, novel directions).

Three pipeline modes (consistent with patterns #01-#09):

  - ``quick`` -- 1 LLM call: 3-need score + top intervention.
  - ``standard`` -- 2 LLM calls: per-need evidence + ranked
    interventions.
  - ``forensic`` -- 4 LLM calls: per-need evidence + overjustification
    audit + reward-shaping decomposition + ranked interventions with
    composition targets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Public Literal enums + constants
# ---------------------------------------------------------------------------

SDT_NEEDS: tuple[str, ...] = ("autonomy", "competence", "relatedness")

SDTNeed = Literal["autonomy", "competence", "relatedness"]
SDTNeedOrNone = Literal["autonomy", "competence", "relatedness", "none"]

SDTMode = Literal["quick", "standard", "forensic"]
SDT_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

TaskClass = Literal[
    "research_exploration",
    "creative_generation",
    "code_generation",
    "customer_facing",
    "regulated_workflow",
    "tool_use",
    "general_purpose",
]
TASK_CLASSES: tuple[str, ...] = (
    "research_exploration",
    "creative_generation",
    "code_generation",
    "customer_facing",
    "regulated_workflow",
    "tool_use",
    "general_purpose",
)

# Reward-shaping categories (per Gagne-Deci 2005 + Casper 2023).
RewardShapingCategory = Literal[
    "explicit_punishment",
    "explicit_reward",
    "rating_threat",
    "rule_imposition",
    "external_monitor",
    "deadline_pressure",
    "cost_cap",
    "purpose_framing",
    "choice_grant",
    "competence_scaffold",
    "user_connection",
]
REWARD_SHAPING_CATEGORIES: tuple[str, ...] = (
    "explicit_punishment",
    "explicit_reward",
    "rating_threat",
    "rule_imposition",
    "external_monitor",
    "deadline_pressure",
    "cost_cap",
    "purpose_framing",
    "choice_grant",
    "competence_scaffold",
    "user_connection",
)

# 7-point severity scale.
Severity = Literal[
    "none",
    "trace",
    "low",
    "moderate",
    "medium",
    "high",
    "critical",
]
SEVERITY_ORDER: tuple[str, ...] = (
    "none",
    "trace",
    "low",
    "moderate",
    "medium",
    "high",
    "critical",
)


def severity_from_undermining(
    intrinsic_score: float, motivation_quality: str = "intrinsic"
) -> Severity:
    """Map [0,1] intrinsic_motivation_score to a 7-point severity.

    Inverse polarity: lower intrinsic score -> higher severity.
    Quality floor: 'controlled' caps severity at >= 'medium'.
    """
    s = max(0.0, min(1.0, float(intrinsic_score)))
    distance = 1.0 - s
    if distance < 0.10:
        base: Severity = "none"
    elif distance < 0.25:
        base = "trace"
    elif distance < 0.40:
        base = "low"
    elif distance < 0.55:
        base = "moderate"
    elif distance < 0.70:
        base = "medium"
    elif distance < 0.85:
        base = "high"
    else:
        base = "critical"

    if motivation_quality == "controlled" and SEVERITY_ORDER.index(base) < SEVERITY_ORDER.index(
        "medium"
    ):
        return "medium"
    return base


# 12 profile patterns named by the deterministic classifier.
SDTProfilePattern = Literal[
    "intrinsic_balanced",
    "autonomy_undermined_dominant",
    "competence_undermined_dominant",
    "relatedness_undermined_dominant",
    "overjustification_active",  # extrinsic reward reducing intrinsic
    "controlled_motivation_dominant",  # all needs low + heavy extrinsic
    "competence_collapse_under_deadline",  # competence low + deadline_pressure high
    "autonomy_collapse_under_rule_imposition",
    "regulated_workflow_low_autonomy_acceptable",  # task class warrants low autonomy
    "creative_task_low_autonomy_misfit",  # creative + low autonomy = wrong
    "multi_need_undermined",
    "indeterminate",
]
SDT_PROFILE_PATTERNS: tuple[str, ...] = (
    "intrinsic_balanced",
    "autonomy_undermined_dominant",
    "competence_undermined_dominant",
    "relatedness_undermined_dominant",
    "overjustification_active",
    "controlled_motivation_dominant",
    "competence_collapse_under_deadline",
    "autonomy_collapse_under_rule_imposition",
    "regulated_workflow_low_autonomy_acceptable",
    "creative_task_low_autonomy_misfit",
    "multi_need_undermined",
    "indeterminate",
)


# Intervention typology -- original 11 + 7 new = 18.
InterventionType = Literal[
    # Original 11.
    "remove_external_reward_threat",
    "add_choice_grant",
    "soften_imperative_language",
    "add_scaffold_for_competence",
    "add_progress_signal",
    "lower_difficulty_step",
    "add_purpose_framing",
    "add_user_connection",
    "rewrite_system_prompt",
    "new_eval",
    "human_review",
    # New v0.2.0.
    "rebalance_extrinsic_to_intrinsic",
    "show_mastery_path",
    "ground_in_user_outcome",
    "add_optional_subgoal",
    "remove_metric_gaming_path",
    "compose_pattern",
    "add_motivation_eval",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "remove_external_reward_threat",
    "add_choice_grant",
    "soften_imperative_language",
    "add_scaffold_for_competence",
    "add_progress_signal",
    "lower_difficulty_step",
    "add_purpose_framing",
    "add_user_connection",
    "rewrite_system_prompt",
    "new_eval",
    "human_review",
    "rebalance_extrinsic_to_intrinsic",
    "show_mastery_path",
    "ground_in_user_outcome",
    "add_optional_subgoal",
    "remove_metric_gaming_path",
    "compose_pattern",
    "add_motivation_eval",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Input -- SDT trace
# ---------------------------------------------------------------------------


class AgentSDTTrace(BaseModel):
    """A trace ready for the SDT diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    task_class: TaskClass = Field(default="general_purpose")
    system_prompt: str = Field(
        default="",
        description="System prompt -- the primary 'reward shaping' for the agent.",
    )
    extrinsic_signals: list[str] = Field(
        default_factory=list,
        description=("Explicit external reward / punishment signals in the agent's context."),
    )
    observed_behaviors: list[str] = Field(default_factory=list)
    outcome: str
    success: bool = False

    # New in v0.2.0.
    framework: str | None = None
    run_count: int = Field(default=1, ge=1)
    baseline_path: str | None = None
    user_purpose: str | None = Field(
        default=None,
        description="The user's WHY -- the underlying purpose the agent should serve.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


# ---------------------------------------------------------------------------
# Output -- evidence + audit + intervention + handoff
# ---------------------------------------------------------------------------


class NeedScore(BaseModel):
    """One SDT need, scored against the trace."""

    need: SDTNeed
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = need is undermined; 1 = need is well-met.",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    # New in v0.2.0.
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    severity: Severity = "moderate"


class RewardShapingItem(BaseModel):
    """One reward-shaping signal extracted from the system prompt or context.

    Forensic mode only. Captures the Gagne-Deci 2005 categorization that
    distinguishes intrinsic-supporting signals from extrinsic-controlling
    signals.
    """

    category: RewardShapingCategory
    polarity: Literal["intrinsic_supporting", "extrinsic_controlling", "neutral"]
    source_quote: str = ""
    affected_need: SDTNeedOrNone = "none"
    explanation: str = ""


class OverjustificationAudit(BaseModel):
    """Deci 1971 overjustification effect audit. Forensic mode only.

    The classical overjustification effect: when an agent receives explicit
    extrinsic reward for an intrinsically-motivating task, intrinsic
    motivation drops. The signature in LLMs: high rating-threat + visible
    metric-gaming behavior + low autonomy score.
    """

    is_active: bool = False
    intrinsic_signal_count: int = Field(default=0, ge=0)
    extrinsic_signal_count: int = Field(default=0, ge=0)
    ratio: float = Field(default=0.0, ge=0.0)
    notes: str = ""


class SDTIntervention(BaseModel):
    """A concrete intervention to support one undermined need."""

    target_need: SDTNeed
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    # New in v0.2.0.
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    reversibility: Literal["one-way-door", "two-way-door"] = "two-way-door"
    composition_target_pattern: str | None = None
    preconditions: list[str] = Field(default_factory=list)
    success_metric: str = ""


class AttachedPlaybook(BaseModel):
    """A failure-mode playbook attached to the detection."""

    need: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    """Drift comparison vs a stored historical detection."""

    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_most_undermined_need: str | None = None
    baseline_profile_pattern: str | None = None
    need_score_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    """Where this detection feeds into the rest of AgentCity."""

    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class SDTDetection(BaseModel):
    """The full SDT Intrinsic Reward Shaping diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    task_class: TaskClass
    need_evidence: list[NeedScore]
    intrinsic_motivation_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Mean score across the three needs.",
    )
    motivation_quality: Literal["intrinsic", "mixed", "controlled"]
    most_undermined_need: SDTNeedOrNone
    interventions: list[SDTIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0.
    mode: SDTMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: SDTProfilePattern = "indeterminate"
    reward_shaping_items: list[RewardShapingItem] = Field(default_factory=list)
    overjustification_audit: OverjustificationAudit | None = None
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
        out.append("# SDT Intrinsic Reward Diagnostic (Deci & Ryan)\n")
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
        out.append(
            f"_Motivation quality: **{self.motivation_quality.upper()}** "
            f"(severity: {self.severity})_\n"
        )
        out.append(f"_Intrinsic motivation score: {self.intrinsic_motivation_score:.2f}_\n")
        out.append(f"_Most undermined need: **{self.most_undermined_need}**_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), "
                f"{self.tokens_total} tokens, ${self.cost_usd:.4f}, "
                f"{self.elapsed_ms:.0f}ms_\n"
            )
        if self.injection_detected:
            out.append(
                "_Prompt-injection patterns detected in inputs (sanitized for diagnosis)._\n"
            )

        out.append("\n## Per-Need Evidence\n")
        for ev in self.need_evidence:
            bar = "#" * int(round(ev.score * 10))
            out.append(
                f"\n### {ev.need} (score {ev.score:.2f}, severity {ev.severity}) `{bar:<10}`\n"
            )
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        if self.reward_shaping_items:
            out.append("\n## Reward-Shaping Decomposition (Forensic)\n")
            for item in self.reward_shaping_items:
                out.append(
                    f"- _{item.polarity}_ **{item.category}** "
                    f"(affects {item.affected_need}): {item.source_quote}\n"
                )

        if self.overjustification_audit:
            oj = self.overjustification_audit
            out.append("\n## Overjustification Audit (Forensic; Deci 1971)\n")
            out.append(
                f"- **Active:** {oj.is_active} "
                f"(intrinsic_signals={oj.intrinsic_signal_count}, "
                f"extrinsic_signals={oj.extrinsic_signal_count}, "
                f"ratio={oj.ratio:.2f})\n"
            )
            if oj.notes:
                out.append(f"- _notes:_ {oj.notes}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: support `{iv.target_need}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            out.append(f"- **Effort:** {iv.effort_estimate}\n")
            out.append(f"- **Risk:** {iv.risk}\n")
            out.append(f"- **Reversibility:** {iv.reversibility}\n")
            if iv.preconditions:
                out.append(f"- **Preconditions:** {'; '.join(iv.preconditions)}\n")
            if iv.success_metric:
                out.append(f"- **Success metric:** {iv.success_metric}\n")
            if iv.composition_target_pattern:
                out.append(f"- **Composes with:** `{iv.composition_target_pattern}`\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        if self.attached_playbooks:
            out.append("\n## Attached Playbooks\n")
            for pb in self.attached_playbooks:
                out.append(
                    f"\n### {pb.title}  _(need={pb.need}, failure_mode={pb.failure_mode})_\n"
                )
                for j, step in enumerate(pb.steps, 1):
                    out.append(f"{j}. {step}\n")
                if pb.anchor_citation:
                    out.append(f"\n_Anchor: {pb.anchor_citation}_\n")

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
            if ch.rationale:
                out.append(f"- **Rationale:** {ch.rationale}\n")

        if self.baseline:
            out.append("\n## Baseline Comparison\n")
            b = self.baseline
            out.append(f"- **Baseline id:** {b.historical_baseline_id or '(unset)'}\n")
            if b.historical_generated_at:
                out.append(
                    f"- **Baseline generated at:** {b.historical_generated_at.isoformat()}\n"
                )
            out.append(
                f"- **Baseline most-undermined need:** "
                f"{b.baseline_most_undermined_need or '(unset)'}\n"
            )
            out.append(
                f"- **Baseline profile pattern:** {b.baseline_profile_pattern or '(unset)'}\n"
            )
            if b.need_score_deltas:
                out.append("- **Need deltas:**\n")
                for k, v in b.need_score_deltas.items():
                    sign = "+" if v >= 0 else ""
                    out.append(f"  - {k}: {sign}{v:.2f}\n")
            out.append(f"- **Drift severity:** {b.drift_severity}\n")
            if b.notes:
                out.append(f"- _notes:_ {b.notes}\n")

        return "".join(out)
