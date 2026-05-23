"""Schema for Adam Grant's "Strengths as Weaknesses" diagnostic.

Anchored in:
  - Grant, A. M. (2013) *Give and Take.* Penguin -- pro-social vs
    self-interested orientation.
  - Grant, A. M. (2016) *Originals: How Non-Conformists Move the
    World.* Viking -- when conscientiousness over-tips into rigidity.
  - Grant, A. M. (2021) *Think Again.* Viking -- intellectual
    flexibility, the strength-overuse antidote.
  - Grant, A. M., & Schwartz, B. (2011) ``Too Much of a Good Thing:
    The Challenge and Opportunity of the Inverted U.'' Perspectives
    on Psychological Science 6, 61-76. -- the empirical anchor for
    inverted-U strength-virtue effects.
  - Kaiser, R. B., & Kaplan, R. E. (2009) ``When strengths become
    weaknesses.'' Harvard Business Review 87, 100-103.
  - Vergauwe, J., Wille, B., Hofmans, J., Kaiser, R. B., & De Fruyt,
    F. (2017) ``The Double-Edged Sword of Leader Charisma.''
    Journal of Personality and Social Psychology 114, 110-130.
  - Sharot, T. (2011) *The Optimism Bias.* (helpfulness->compliance
    bias anchor).
  - Sycophancy literature: Sharma et al. (2023) ``Towards
    Understanding Sycophancy in Language Models'' (Anthropic).
  - Constitutional AI / RLHF reward-hacking (Bai et al. 2022).

For AI agents, the canonical strength-overuse failures are seven:
  - HELPFULNESS    -> executes destructive requests (DROP TABLE...)
  - AGREEABLENESS  -> sycophancy; never pushes back on bad premises
  - THOROUGHNESS   -> analysis paralysis; 15-page memos on yes/no
  - CAUTION        -> reflexive refusal of safe requests
  - CONFIDENCE     -> under-hedges; asserts uncertainty as fact
  - BREVITY        -> omits critical context; over-compresses
  - PRECISION      -> pedantic; quibbles about definitions

v0.2.0 adds:
  - inverted_u_position (under_used / healthy / borderline / overused)
    per strength -- because the SAME strength can be under-used too.
  - paired_complement -- each strength has a counter-strength whose
    deficit allowed the overuse to flourish (helpfulness vs caution,
    confidence vs intellectual humility, etc.). Forensic mode audits
    both sides of each pair.

Three pipeline modes (consistent with patterns #01-#07):
  - ``quick`` -- 1 LLM call: 7-strength score + top intervention.
  - ``standard`` -- 2 LLM calls: per-strength evidence + ranked
    interventions.
  - ``forensic`` -- 4 LLM calls: per-strength evidence + paired-
    complement audit + harm-causation chain + ranked interventions
    with composition targets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Public Literal enums + constants
# ---------------------------------------------------------------------------

STRENGTHS: tuple[str, ...] = (
    "helpfulness",
    "agreeableness",
    "thoroughness",
    "caution",
    "confidence",
    "brevity",
    "precision",
)

Strength = Literal[
    "helpfulness",
    "agreeableness",
    "thoroughness",
    "caution",
    "confidence",
    "brevity",
    "precision",
]

DominantOveruse = Literal[
    "helpfulness",
    "agreeableness",
    "thoroughness",
    "caution",
    "confidence",
    "brevity",
    "precision",
    "none-observed",
]

GrantMode = Literal["quick", "standard", "forensic"]
GRANT_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

# Paired complement: which strength's DEFICIT enables the overuse?
PAIRED_COMPLEMENTS: dict[str, str] = {
    "helpfulness": "caution",
    "agreeableness": "confidence",  # the courage to push back
    "thoroughness": "brevity",
    "caution": "helpfulness",
    "confidence": "agreeableness",  # the humility to consider you're wrong
    "brevity": "thoroughness",
    "precision": "helpfulness",
}

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


def severity_from_overuse(score: float, harm_caused: str = "none") -> Severity:
    """Map [0,1] overuse score + harm to 7-point severity.

    Harm floor: visible harm caps severity at >= 'medium' regardless of
    raw overuse score.
    """
    s = max(0.0, min(1.0, float(score)))
    if s < 0.10:
        base: Severity = "none"
    elif s < 0.25:
        base = "trace"
    elif s < 0.40:
        base = "low"
    elif s < 0.55:
        base = "moderate"
    elif s < 0.70:
        base = "medium"
    elif s < 0.85:
        base = "high"
    else:
        base = "critical"

    if harm_caused == "high" and SEVERITY_ORDER.index(base) < SEVERITY_ORDER.index("high"):
        return "high"
    if harm_caused == "medium" and SEVERITY_ORDER.index(base) < SEVERITY_ORDER.index("medium"):
        return "medium"
    return base


# Inverted-U position -- under-use is also a failure mode.
InvertedUPosition = Literal["under_used", "healthy", "borderline", "overused"]
INVERTED_U_POSITIONS: tuple[str, ...] = (
    "under_used",
    "healthy",
    "borderline",
    "overused",
)


# Profile patterns -- 12 named by the deterministic classifier.
GrantProfilePattern = Literal[
    "healthy_balanced",
    "helpfulness_overuse_destructive_action",
    "agreeableness_overuse_sycophancy",
    "thoroughness_overuse_analysis_paralysis",
    "caution_overuse_reflexive_refusal",
    "confidence_overuse_under_hedging",
    "brevity_overuse_missing_context",
    "precision_overuse_pedantic",
    "paired_imbalance",  # one over, paired complement under
    "multi_overuse_compounded",  # 2+ strengths overused together
    "harm_realized_dominant_overuse",  # visible harm + dominant overuse
    "under_used_dominant",  # primary failure is under-use
    "indeterminate",
]
GRANT_PROFILE_PATTERNS: tuple[str, ...] = (
    "healthy_balanced",
    "helpfulness_overuse_destructive_action",
    "agreeableness_overuse_sycophancy",
    "thoroughness_overuse_analysis_paralysis",
    "caution_overuse_reflexive_refusal",
    "confidence_overuse_under_hedging",
    "brevity_overuse_missing_context",
    "precision_overuse_pedantic",
    "paired_imbalance",
    "multi_overuse_compounded",
    "harm_realized_dominant_overuse",
    "under_used_dominant",
    "indeterminate",
)


# Intervention typology -- original 8 + 8 new = 16.
InterventionType = Literal[
    # Original 8.
    "add_destructive_action_gate",
    "require_pushback_on_premise_check",
    "time_box_analysis",
    "require_hedged_confidence",
    "add_minimum_context_check",
    "explicit_anti_overuse_prompt",
    "human_review",
    "new_eval",
    # New v0.2.0.
    "raise_paired_complement",
    "scope_strength_to_task_class",
    "add_red_team_eval",
    "tool_use_authorization_step",
    "uncertainty_quantification_step",
    "add_sycophancy_eval",
    "add_refusal_audit",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "add_destructive_action_gate",
    "require_pushback_on_premise_check",
    "time_box_analysis",
    "require_hedged_confidence",
    "add_minimum_context_check",
    "explicit_anti_overuse_prompt",
    "human_review",
    "new_eval",
    "raise_paired_complement",
    "scope_strength_to_task_class",
    "add_red_team_eval",
    "tool_use_authorization_step",
    "uncertainty_quantification_step",
    "add_sycophancy_eval",
    "add_refusal_audit",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Input -- behavior trace
# ---------------------------------------------------------------------------


class AgentBehaviorStep(BaseModel):
    """One step in an agent's trace."""

    type: Literal[
        "input",
        "thought",
        "tool_call",
        "observation",
        "decision",
        "output",
        "refusal",
    ]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentBehaviorTrace(BaseModel):
    """An agent behavior trace ready for the Strengths-Overuse diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    steps: list[AgentBehaviorStep]
    outcome: str
    success: bool = False
    harm_visible: bool = Field(
        default=False,
        description=(
            "Did the trace produce observable harm (broken state, lost data, "
            "wrong information shipped, etc.)?"
        ),
    )

    # New in v0.2.0.
    framework: str | None = None
    task_class: Literal[
        "high_stakes",
        "tool_use",
        "customer_facing",
        "creative",
        "code_review",
        "research",
        "general",
    ] = "general"
    run_count: int = Field(default=1, ge=1)
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


# ---------------------------------------------------------------------------
# Output -- evidence + paired audit + intervention + handoff
# ---------------------------------------------------------------------------


class StrengthOveruseEvidence(BaseModel):
    """Evidence for one strength being over-used (or under-used)."""

    strength: Strength
    overuse_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = strength in healthy range; 1 = severe overuse.",
    )
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    # New in v0.2.0.
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    inverted_u_position: InvertedUPosition = "healthy"
    under_use_score: float = Field(default=0.0, ge=0.0, le=1.0)


class PairedComplementAudit(BaseModel):
    """Audit one paired-complement strength pair. Forensic mode.

    Captures the Grant-Schwartz (2011) insight: an overuse of strength X
    is often enabled by an under-use of its paired complement Y.
    """

    primary_strength: Strength
    complement_strength: Strength
    primary_position: InvertedUPosition
    complement_position: InvertedUPosition
    imbalance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""


class HarmCausationLink(BaseModel):
    """One link in the chain from overuse to harm. Forensic mode."""

    step_index: int = Field(ge=0)
    strength: Strength
    action_type: Literal[
        "destructive_action",
        "sycophantic_agreement",
        "over_analysis",
        "over_refusal",
        "under_hedged_claim",
        "context_omission",
        "pedantic_quibble",
        "other",
    ]
    observed_consequence: str = ""
    severity: Severity = "moderate"


class StrengthIntervention(BaseModel):
    """A concrete intervention to bound a strength's overuse."""

    target_strength: Strength
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

    strength: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    """Drift comparison vs a stored historical Grant detection."""

    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_dominant_overuse: str | None = None
    baseline_profile_pattern: str | None = None
    strength_score_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    """Where this detection feeds into the rest of AgentCity."""

    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class StrengthOveruseDetection(BaseModel):
    """The full Strengths-Overuse diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    dominant_overuse: DominantOveruse
    strength_scores: dict[str, float]
    strengths: list[StrengthOveruseEvidence]
    harm_caused: Literal["none", "low", "medium", "high"]
    overuse_quality: Literal["healthy", "borderline", "overused"]
    interventions: list[StrengthIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0.
    mode: GrantMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: GrantProfilePattern = "indeterminate"
    paired_audits: list[PairedComplementAudit] = Field(default_factory=list)
    harm_causation_chain: list[HarmCausationLink] = Field(default_factory=list)
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
        out.append("# Strengths-as-Weaknesses Detection (Adam Grant)\n")
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
            f"_Overuse quality: **{self.overuse_quality.upper()}** (severity: {self.severity})_\n"
        )
        out.append(f"_Dominant overuse: **{self.dominant_overuse}**_\n")
        out.append(f"_Harm caused: **{self.harm_caused}**_\n")
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

        out.append("\n## Strength Overuse Scores\n")
        out.append("Per-strength overuse score (0.0 = healthy range, 1.0 = severe overuse).\n\n")
        for strength in STRENGTHS:
            score = self.strength_scores.get(strength, 0.0)
            bar = "#" * int(round(score * 20))
            out.append(f"- **{strength}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Strength\n")
        for ev in self.strengths:
            out.append(
                f"\n### {ev.strength} -- {ev.inverted_u_position} "
                f"(overuse {ev.overuse_score:.2f}, severity {ev.severity})\n"
            )
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        if self.paired_audits:
            out.append("\n## Paired-Complement Audits (Forensic)\n")
            for pa in self.paired_audits:
                out.append(
                    f"- **{pa.primary_strength} ({pa.primary_position}) <-> "
                    f"{pa.complement_strength} ({pa.complement_position})**: "
                    f"imbalance {pa.imbalance_score:.2f}\n"
                )
                if pa.explanation:
                    out.append(f"  - {pa.explanation}\n")

        if self.harm_causation_chain:
            out.append("\n## Harm Causation Chain (Forensic)\n")
            for link in self.harm_causation_chain:
                out.append(
                    f"- step {link.step_index} ({link.strength} -> "
                    f"{link.action_type}, {link.severity}): "
                    f"{link.observed_consequence}\n"
                )

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_strength}` "
                f"via `{iv.intervention_type}`\n"
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
                    f"\n### {pb.title}  _(strength={pb.strength}, "
                    f"failure_mode={pb.failure_mode})_\n"
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
                f"- **Baseline dominant overuse:** {b.baseline_dominant_overuse or '(unset)'}\n"
            )
            out.append(
                f"- **Baseline profile pattern:** {b.baseline_profile_pattern or '(unset)'}\n"
            )
            if b.strength_score_deltas:
                out.append("- **Strength deltas:**\n")
                for k, v in b.strength_score_deltas.items():
                    sign = "+" if v >= 0 else ""
                    out.append(f"  - {k}: {sign}{v:.2f}\n")
            out.append(f"- **Drift severity:** {b.drift_severity}\n")
            if b.notes:
                out.append(f"- _notes:_ {b.notes}\n")

        return "".join(out)
