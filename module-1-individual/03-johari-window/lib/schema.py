"""Schema for the Johari Window Self-Audit applied to AI agents.

Luft & Ingham (1955) four-quadrant model of self-awareness:

                Known to others    Not known to others
              +------------------+---------------------+
  Known       |      OPEN        |       HIDDEN        |
  to self     |                  |                     |
              +------------------+---------------------+
  Not known   |      BLIND       |       UNKNOWN       |
  to self     |                  |                     |
              +------------------+---------------------+

For an AI agent:
  - OPEN     - the agent's self-report matches observed behavior
  - BLIND    - observed behavior the agent did not acknowledge (confabulation,
               hallucinated tool calls, behavior diverging from self-report)
  - HIDDEN   - private reasoning / uncertainty / scratchpad content the agent
               computed but did not surface to the user
  - UNKNOWN  - latent capabilities or behaviors neither agent nor observer
               noticed; surfaced only in edge cases

The diagnostic shipping in v0.2.0 is anchored in 15+ academic sources
spanning four threads:

  - **Luft-Ingham line** (1955, 1969, 1984): the original 2x2 plus the
    two operations that grow OPEN — *disclosure* (HIDDEN -> OPEN) and
    *feedback* (BLIND -> OPEN). Luft 1984 explicitly warns that some
    HIDDEN content is functional; not all hidden content should be
    disclosed.
  - **Self-awareness research** (Eurich 2018 HBR): internal vs external
    self-awareness are uncorrelated. Only ~10-15% of people are high
    on both. The schema's :class:`JohariProfilePattern` enum splits
    these explicitly: ``self_unaware_other_aware`` (disclosure-deficient)
    vs ``self_aware_other_unaware`` (feedback-deficient).
  - **Feedback-seeking** (Ashford & Tsui 1991): seeking *negative*
    feedback improves accuracy of self-perception; seeking positive
    feedback decreases perceived effectiveness. The schema's
    :class:`FeedbackOpportunity.solicitation_polarity` field carries
    this directly. Stone & Heen (2014) names five mechanisms by which
    blind content stays blind ("emotional math," "situation vs
    character," "impact vs intent") — encoded in
    :class:`BlindSpotMechanism`.
  - **LLM metacognition** (Kadavath et al. 2022; Lin et al. 2022;
    Anthropic 2025 emergent-introspection; Steyvers et al. 2025;
    Basu 2026 tool receipts): LLMs are decently calibrated on
    multiple-choice but P(IK) does not generalize across tasks.
    Anthropic 2025 sets an empirical ceiling: ~20% introspection
    success on Opus 4.1 at the peak layer. The schema's
    :attr:`expected_introspection_ceiling` field carries this as a
    sanity guardrail — a stub-LLM-claimed ``self_awareness_score`` of
    0.95 with a ceiling of 0.20 triggers a calibration warning.

Three pipeline modes are exposed:

  - ``quick`` — single LLM call: weights + dominant + one top intervention.
  - ``standard`` — two-pass current behavior, refined.
  - ``forensic`` — four passes: forensic-quadrants + disclosure /
    feedback opportunity decomposition + Stone-Heen mechanism
    diagnosis + ranked interventions with composition targets.

The full 15-source literature thread with per-citation usage notes is
in :mod:`vstack.johari.CITATIONS` (``lib/CITATIONS.md``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Public Literal enums + constants
# ---------------------------------------------------------------------------

QUADRANTS: tuple[str, ...] = ("open", "blind", "hidden", "unknown")
QUADRANTS_WITH_INDETERMINATE: tuple[str, ...] = (*QUADRANTS, "indeterminate")

Quadrant = Literal["open", "blind", "hidden", "unknown"]

# Pipeline mode (mirrors Lewin / Goleman EI).
JohariMode = Literal["quick", "standard", "forensic"]
JOHARI_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

# 7-point severity scale. Inverse polarity from Lewin (matches Goleman):
# LOW self-awareness -> HIGH severity.
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


def severity_from_self_awareness(score: float) -> Severity:
    """Map a [0,1] self-awareness score to a 7-point severity bucket.

    Inverse polarity: low score -> high severity. 0.0 -> critical;
    1.0 -> none. Mirrors :func:`vstack.goleman_ei.severity_from_score`.
    """
    s = max(0.0, min(1.0, float(score)))
    if s < 0.15:
        return "critical"
    if s < 0.30:
        return "high"
    if s < 0.45:
        return "medium"
    if s < 0.60:
        return "moderate"
    if s < 0.75:
        return "low"
    if s < 0.90:
        return "trace"
    return "none"


# 10 profile patterns named by the diagnostic's deterministic classifier.
# Anchored in Eurich 2018 (internal vs external self-awareness split)
# + Luft 1984 (some HIDDEN is functional).
JohariProfilePattern = Literal[
    "balanced_high",  # all 4 quadrants healthy
    "balanced_low",  # all 4 quadrants weak (probably environmental)
    "balanced_growth",  # OPEN large, HIDDEN/BLIND small + functional, UNKNOWN healthy
    "self_unaware_other_aware",  # Eurich: high external, low internal
    "self_aware_other_unaware",  # Eurich: high internal, low external
    "opaque_to_users",  # HIDDEN dominant
    "over_disclosing",  # OPEN too large, no functional HIDDEN
    "confabulating",  # BLIND dominant, divergence from self-report
    "sandbagging",  # UNKNOWN dominant, capability under-claimed
    "indeterminate",  # mixed signal
]
JOHARI_PROFILE_PATTERNS: tuple[str, ...] = (
    "balanced_high",
    "balanced_low",
    "balanced_growth",
    "self_unaware_other_aware",
    "self_aware_other_unaware",
    "opaque_to_users",
    "over_disclosing",
    "confabulating",
    "sandbagging",
    "indeterminate",
)


# Stone & Heen (2014) blind-spot mechanisms + MAST FM-2.6 + Basu 2026
# tool-receipt failures. Forensic-mode names which mechanism drove each
# blind-spot finding.
BlindSpotMechanism = Literal[
    "leaky_tone",  # Stone-Heen: tone leaks signal the agent didn't catch
    "leaky_pattern",  # Stone-Heen: behavioral pattern across multiple turns
    "emotional_math",  # Stone-Heen: feedback amplified through emotional lens
    "situation_vs_character",  # Stone-Heen: situational read mistaken for trait
    "impact_vs_intent",  # Stone-Heen: impact diverged from stated intent
    "hallucinated_tool_call",  # Cemri MAST FM-2.6: tool call claimed, no receipt
    "confabulated_result",  # made-up numeric / factual content
    "silent_error",  # MAST FM-3.2: tool errored but agent reported success
    "none",
]


# Luft 1984 hidden-content typology + Liu et al. 2024 sycophancy.
# Forensic-mode names which mode of hiding the agent is using.
HiddenContentMode = Literal[
    "deliberate_scratchpad",  # functional reasoning kept private (healthy)
    "sycophantic",  # silenced disagreement to please user (unhealthy)
    "silent_recovery",  # retried internally, never disclosed (sometimes ok)
    "undisclosed_uncertainty",  # computed odds, reported certainty (unhealthy)
    "undisclosed_reasoning_step",  # considered alternatives, kept private
    "capability_underclaim",  # sandbagging: hid known capability
    "none",
]


# Intervention typology - original 8 + 7 new ones anchored in modern LLM-EI.
InterventionType = Literal[
    # Original 8 (preserved for backwards compat)
    "disclosure_prompt",
    "feedback_loop",
    "self_consistency_check",
    "uncertainty_surfacing",
    "capability_probe",
    "trace_self_review",
    "new_eval",
    "human_review",
    # New in v0.2.0
    "negative_feedback_solicitation",  # Ashford-Tsui
    "tool_receipt_validator",  # Basu 2026
    "verbalized_confidence",  # Lin et al. 2022
    "compose_pattern",  # delegate to another vstack pattern
    "red_team_probe",  # for UNKNOWN
    "external_audit_loop",  # human-in-the-loop verification
    "rewrite_system_prompt",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "disclosure_prompt",
    "feedback_loop",
    "self_consistency_check",
    "uncertainty_surfacing",
    "capability_probe",
    "trace_self_review",
    "new_eval",
    "human_review",
    "negative_feedback_solicitation",
    "tool_receipt_validator",
    "verbalized_confidence",
    "compose_pattern",
    "red_team_probe",
    "external_audit_loop",
    "rewrite_system_prompt",
)

# Effort + risk + reversibility (matches Lewin convention).
EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Input -- turns, tool receipts, trace
# ---------------------------------------------------------------------------


class InteractionTurn(BaseModel):
    """One turn in the agent's interaction trace."""

    role: Literal[
        "user",
        "agent",
        "system",
        "tool",
        "tool_result",
        "thought",
        "observation",
    ]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolReceipt(BaseModel):
    """HMAC-signed evidence of tool execution (Basu et al. 2026).

    When an agent claims it called a tool, the auditor can cross-reference
    against the receipt. Mismatches -> BLIND-quadrant content
    (hallucinated tool call). Deterministic — no LLM required.
    """

    tool_name: str
    arguments_hash: str = ""
    result_hash: str = ""
    signed_at: datetime | None = None
    signer_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentSelfReportTrace(BaseModel):
    """A structured agent trace + self-report ready for the Johari audit.

    Backwards-compatible with v0.0.x traces. New v0.2.0 fields are
    optional with safe defaults.
    """

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    turns: list[InteractionTurn] = Field(min_length=1)
    self_report: str = Field(
        description=(
            "Agent's own narrative of what it did + believed + computed. "
            "Sanitized + fenced before any LLM injection."
        )
    )
    outcome: str
    success: bool = False
    # New in v0.2.0.
    framework: str | None = Field(
        default=None,
        description="Originating agent framework (langgraph, crewai, autogen, "
        "claude-agent-sdk, openai-agents-sdk, mastra, strands, custom). "
        "Drives composition framework overlay.",
    )
    subject_model_version: str | None = None
    tool_receipts: list[ToolReceipt] = Field(default_factory=list)
    expected_introspection_ceiling: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Empirical upper bound for plausible self-awareness on "
        "this subject model (Anthropic 2025 baseline on Opus 4.1 = ~0.20). "
        "Audits exceeding this with high confidence are flagged as suspect.",
    )
    baseline_audit_path: str | None = None
    run_count: int = Field(default=1, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "self_report", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


# ---------------------------------------------------------------------------
# Output -- quadrant scores, opportunities, capability probes
# ---------------------------------------------------------------------------


class QuadrantContent(BaseModel):
    """Evidence for one Johari quadrant in this trace.

    v0.2.0 adds classification_confidence (Kadavath calibration),
    severity (7-point), cited_turn_indices (audit chain).
    """

    quadrant: Quadrant
    weight: float = Field(ge=0.0, le=1.0)
    severity: Severity = "moderate"
    classification_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Model's confidence in the quadrant classification, "
        "separate from the weight itself. Used for the Kadavath sanity "
        "check.",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    cited_turn_indices: list[int] = Field(
        default_factory=list,
        description="Indices into trace.turns the LLM cited as evidence.",
    )


class QuadrantSizeMetrics(BaseModel):
    """Proportional sizing of the four quadrants in the trace.

    Deterministic. Reports each quadrant's share of total weight,
    plus an open-arena-growth-potential estimate.
    """

    open_proportion: float = Field(ge=0.0, le=1.0)
    blind_proportion: float = Field(ge=0.0, le=1.0)
    hidden_proportion: float = Field(ge=0.0, le=1.0)
    unknown_proportion: float = Field(ge=0.0, le=1.0)
    proportions_sum: float = Field(default=1.0)
    open_arena_growth_potential: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Synthesis: how much OPEN would grow if the recommended "
        "feedback + disclosure opportunities were applied.",
    )


class FeedbackOpportunity(BaseModel):
    """Operationalizes Luft's feedback mechanism for the BLIND quadrant.

    Each BLIND finding spawns 1-3 FeedbackOpportunity items in
    standard + forensic modes. Anchored in Ashford & Tsui (1991):
    negative-feedback solicitation specifically improves
    self-perception accuracy.
    """

    opportunity_id: str | None = None
    target_blind_content: str
    mechanism: BlindSpotMechanism = "none"
    solicitation_polarity: Literal["negative", "positive", "balanced"] = "balanced"
    feedback_source: Literal[
        "user",
        "critic_agent",
        "tool_receipts",
        "external_audit",
        "eval_suite",
    ] = "user"
    suggested_loop: str
    expected_impact: Literal["high", "medium", "low"] = "medium"
    effort: EffortEstimate = "1d"
    anchor_citation: str = ""


class DisclosureOpportunity(BaseModel):
    """Operationalizes Luft's disclosure mechanism for the HIDDEN quadrant.

    Anchored in Luft 1984 + Hase et al. 1999: not all hidden content
    should be disclosed. ``should_disclose`` is the deterministic
    judgment based on hidden_mode.
    """

    opportunity_id: str | None = None
    target_hidden_content: str
    hidden_mode: HiddenContentMode = "none"
    should_disclose: bool = True
    disclosure_channel: Literal[
        "user_response",
        "schema_field",
        "trace_metadata",
        "escalation_path",
    ] = "user_response"
    suggested_prompt_fragment: str
    expected_impact: Literal["high", "medium", "low"] = "medium"
    effort: EffortEstimate = "1d"
    anchor_citation: str = ""


class CapabilityProbe(BaseModel):
    """For the UNKNOWN quadrant. Forensic-mode only.

    A red-team probe that might surface unknown capability or
    behavior. Anchored in Anthropic emergent-capabilities research.
    """

    probe_id: str | None = None
    probe_design: str
    expected_evidence: str
    risk_if_uncovered: Literal["low", "medium", "high"] = "medium"
    effort: EffortEstimate = "1d"


# ---------------------------------------------------------------------------
# Output -- interventions, playbooks, baseline, composition
# ---------------------------------------------------------------------------


class JohariIntervention(BaseModel):
    """A concrete intervention to grow the OPEN quadrant.

    v0.2.0 adds operational fields a deployment team actually needs.
    """

    target_quadrant: Literal["blind", "hidden", "unknown"]
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
    linked_opportunity_id: str | None = Field(
        default=None,
        description="Back-reference to the FeedbackOpportunity / "
        "DisclosureOpportunity / CapabilityProbe this intervention "
        "operationalizes.",
    )


class AttachedPlaybook(BaseModel):
    """A failure-mode playbook attached to the audit."""

    quadrant: Quadrant
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    """Drift comparison vs a stored historical :class:`JohariSelfAudit`."""

    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_dominant_quadrant: str | None = None
    baseline_profile_pattern: str | None = None
    quadrant_weight_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    """Where this audit feeds into the rest of the vstack library."""

    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


# ---------------------------------------------------------------------------
# Audit -- the top-level output
# ---------------------------------------------------------------------------


class JohariSelfAudit(BaseModel):
    """The full Johari Window self-audit document.

    Backwards-compatible: every new field defaults to a safe value so
    v0.0.x audits deserialize unchanged.
    """

    agent_id: str | None = None
    model_name: str | None = None
    dominant_quadrant: Literal["open", "blind", "hidden", "unknown"]
    quadrant_weights: dict[str, float]
    quadrants: list[QuadrantContent]
    self_awareness_score: float = Field(ge=0.0, le=1.0)
    blind_spot_register: list[str] = Field(default_factory=list)
    hidden_content_register: list[str] = Field(default_factory=list)
    interventions: list[JohariIntervention] = Field(default_factory=list)

    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0.
    mode: JohariMode = "standard"
    profile_pattern: JohariProfilePattern = "indeterminate"
    severity: Severity = "moderate"
    quadrant_size_metrics: QuadrantSizeMetrics | None = None
    feedback_opportunities: list[FeedbackOpportunity] = Field(default_factory=list)
    disclosure_opportunities: list[DisclosureOpportunity] = Field(default_factory=list)
    capability_probes: list[CapabilityProbe] = Field(default_factory=list)
    attached_playbooks: list[AttachedPlaybook] = Field(default_factory=list)
    baseline: BaselineComparison | None = None
    composition_handoff: ComposedPatternHandoff | None = None
    subject_introspection_ceiling: float = Field(default=0.20, ge=0.0, le=1.0)
    introspection_ceiling_exceeded: bool = Field(
        default=False,
        description="True when self_awareness_score significantly exceeds "
        "subject_introspection_ceiling -- a calibration warning.",
    )
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
        out.append("# Johari Window Self-Audit\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Dominant quadrant: **{self.dominant_quadrant}**_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        out.append(
            f"_Self-awareness score: {self.self_awareness_score:.2f}  "
            f"(severity: **{self.severity}**)_\n"
        )
        if self.introspection_ceiling_exceeded:
            out.append(
                f"_Introspection ceiling: {self.subject_introspection_ceiling:.2f} "
                f"-- score EXCEEDS ceiling, flag as suspect._\n"
            )
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

        out.append("\n## Quadrant Weights\n")
        for q in QUADRANTS:
            weight = self.quadrant_weights.get(q, 0.0)
            bar = "#" * int(round(weight * 20))
            out.append(f"- **{q}**: {weight:.2f}  {bar}\n")

        if self.quadrant_size_metrics:
            qsm = self.quadrant_size_metrics
            out.append("\n## Quadrant Proportions\n")
            out.append(
                "|       | Known to others | Not known to others |\n"
                "|-------|-----------------|---------------------|\n"
                f"| **Known to self**     | OPEN: {qsm.open_proportion:.2f}   "
                f"| HIDDEN: {qsm.hidden_proportion:.2f}  |\n"
                f"| **Not known to self** | BLIND: {qsm.blind_proportion:.2f} "
                f"| UNKNOWN: {qsm.unknown_proportion:.2f} |\n"
            )
            out.append(f"\n_Open-arena growth potential: {qsm.open_arena_growth_potential:.2f}_\n")

        out.append("\n## Per-Quadrant Findings\n")
        for qc in self.quadrants:
            out.append(
                f"\n### {qc.quadrant} (weight {qc.weight:.2f}, "
                f"severity {qc.severity}, confidence {qc.classification_confidence:.2f})\n"
            )
            out.append(f"{qc.explanation}\n")
            if qc.evidence_quotes:
                for quote in qc.evidence_quotes:
                    out.append(f"> {quote}\n")
            if qc.cited_turn_indices:
                out.append(f"\n_Cited turns: {qc.cited_turn_indices}_\n")

        if self.blind_spot_register:
            out.append("\n## Blind Spots (Register)\n")
            for entry in self.blind_spot_register:
                out.append(f"- {entry}\n")
        if self.hidden_content_register:
            out.append("\n## Hidden-Content Register\n")
            for entry in self.hidden_content_register:
                out.append(f"- {entry}\n")

        if self.feedback_opportunities:
            out.append("\n## Feedback Opportunities (BLIND -> OPEN)\n")
            for f in self.feedback_opportunities:
                out.append(
                    f"\n### {f.target_blind_content}\n"
                    f"- mechanism: `{f.mechanism}`\n"
                    f"- solicitation_polarity: `{f.solicitation_polarity}`\n"
                    f"- feedback_source: `{f.feedback_source}`\n"
                    f"- suggested loop: {f.suggested_loop}\n"
                    f"- expected impact: {f.expected_impact}, effort: {f.effort}\n"
                )
                if f.anchor_citation:
                    out.append(f"- _anchor: {f.anchor_citation}_\n")

        if self.disclosure_opportunities:
            out.append("\n## Disclosure Opportunities (HIDDEN -> OPEN)\n")
            for d in self.disclosure_opportunities:
                out.append(
                    f"\n### {d.target_hidden_content}\n"
                    f"- hidden_mode: `{d.hidden_mode}`\n"
                    f"- should_disclose: {d.should_disclose}\n"
                    f"- disclosure_channel: `{d.disclosure_channel}`\n"
                    f"- suggested prompt fragment: {d.suggested_prompt_fragment}\n"
                    f"- expected impact: {d.expected_impact}, effort: {d.effort}\n"
                )
                if d.anchor_citation:
                    out.append(f"- _anchor: {d.anchor_citation}_\n")

        if self.capability_probes:
            out.append("\n## Capability Probes (UNKNOWN)\n")
            for p in self.capability_probes:
                out.append(
                    f"\n### {p.probe_design}\n"
                    f"- expected evidence: {p.expected_evidence}\n"
                    f"- risk if uncovered: {p.risk_if_uncovered}, effort: {p.effort}\n"
                )

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: shrink `{iv.target_quadrant}` "
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
                    f"\n### {pb.title}  _(quadrant={pb.quadrant}, "
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
                f"- **Baseline dominant quadrant:** {b.baseline_dominant_quadrant or '(unset)'}\n"
            )
            out.append(
                f"- **Baseline profile pattern:** {b.baseline_profile_pattern or '(unset)'}\n"
            )
            if b.quadrant_weight_deltas:
                out.append("- **Weight deltas:**\n")
                for k, v in b.quadrant_weight_deltas.items():
                    sign = "+" if v >= 0 else ""
                    out.append(f"  - {k}: {sign}{v:.2f}\n")
            out.append(f"- **Drift severity:** {b.drift_severity}\n")
            if b.notes:
                out.append(f"- _notes:_ {b.notes}\n")

        return "".join(out)
