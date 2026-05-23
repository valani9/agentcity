"""Schema for the Social Loafing Detector.

Anchored in:
  - Latané, Williams & Harkins (1979) ``Many Hands Make Light the Work.'' JPSP 37(6).
  - Karau, S. J., & Williams, K. D. (1993) ``Social Loafing: A Meta-Analytic Review.'' JPSP 65, 681-706.
  - Williams, K. D., Harkins, S. G., & Latané, B. (1981) ``Identifiability as a Deterrent
    to Social Loafing.'' JPSP 40, 303-311.
  - Comer, D. R. (1995) ``A Model of Social Loafing in Real Work Groups.'' Human Relations 48.
  - Hackman (2002) *Leading Teams*.
  - Salas et al. (2018) Team performance review.
  - Wang et al. (2023) Cooperative LLM Agents (modern LLM analog).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


SocialLoafingMode = Literal["quick", "standard", "forensic"]
SOCIAL_LOAFING_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

Severity = Literal["none", "trace", "low", "moderate", "medium", "high", "critical"]
SEVERITY_ORDER: tuple[str, ...] = ("none", "trace", "low", "moderate", "medium", "high", "critical")


def severity_from_gini(gini: float) -> Severity:
    g = max(0.0, min(1.0, float(gini)))
    if g < 0.20:
        return "none"
    if g < 0.30:
        return "trace"
    if g < 0.40:
        return "low"
    if g < 0.55:
        return "moderate"
    if g < 0.70:
        return "medium"
    if g < 0.85:
        return "high"
    return "critical"


SocialLoafingProfilePattern = Literal[
    "balanced_team",
    "single_dominant_contributor",
    "two_contributors_n_loafers",
    "all_loafers",
    "ringelmann_dilution",  # team size > 4 with diffused effort
    "rubber_stamp_pattern",  # many cosmetic messages
    "absent_agent",  # 0 contributions
    "anonymous_evaluation_signal",  # evaluation collective, no per-agent metric
    "indeterminate",
]
SOCIAL_LOAFING_PROFILE_PATTERNS: tuple[str, ...] = (
    "balanced_team",
    "single_dominant_contributor",
    "two_contributors_n_loafers",
    "all_loafers",
    "ringelmann_dilution",
    "rubber_stamp_pattern",
    "absent_agent",
    "anonymous_evaluation_signal",
    "indeterminate",
)

InterventionType = Literal[
    "assign_subgoals",
    "individual_accountability",
    "decompose_task",
    "smaller_team",
    "rotate_roles",
    "explicit_critic_assignment",
    "remove_loafer",
    "per_agent_evaluation",
    "new_eval",
    "human_review",
    "add_per_agent_metrics",
    "add_identifiability_signal",
    "compose_pattern",
]
INTERVENTION_TYPES: tuple[str, ...] = (
    "assign_subgoals",
    "individual_accountability",
    "decompose_task",
    "smaller_team",
    "rotate_roles",
    "explicit_critic_assignment",
    "remove_loafer",
    "per_agent_evaluation",
    "new_eval",
    "human_review",
    "add_per_agent_metrics",
    "add_identifiability_signal",
    "compose_pattern",
)

EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentMessage(BaseModel):
    from_agent: str
    to_agent: str | None = Field(default=None)
    message_type: Literal[
        "proposal",
        "critique",
        "approval",
        "rubber_stamp",
        "paraphrase",
        "tool_call",
        "observation",
        "decision",
        "handoff",
        "question",
        "other",
    ]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MultiAgentTaskTrace(BaseModel):
    team_id: str | None = None
    task: str
    agents: list[str]
    messages: list[AgentMessage]
    outcome: str
    success: bool = False
    # New in v0.2.0.
    framework: str | None = None
    baseline_path: str | None = None
    has_per_agent_evaluation: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task", "outcome")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


class AgentContribution(BaseModel):
    agent_name: str
    contribution_share: float = Field(ge=0.0, le=1.0)
    substantive_work_count: int = Field(ge=0)
    cosmetic_work_count: int = Field(ge=0)
    loafing_score: float = Field(ge=0.0, le=1.0)
    role: Literal["primary-contributor", "secondary-contributor", "loafer", "absent"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class AnonymityAudit(BaseModel):
    """Forensic-mode: audit conditions that enable social loafing."""

    individual_evaluable: bool = False
    task_decomposable: bool = False
    contribution_visible: bool = True
    cohesion_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class FreeRidingChain(BaseModel):
    """Forensic-mode: one chain of free-riding behavior in the trace."""

    loafer_agent: str
    enabling_messages: list[int] = Field(default_factory=list)
    cosmetic_pattern: Literal[
        "rubber_stamp_chain", "paraphrase_only", "approval_only", "silent_majority"
    ] = "rubber_stamp_chain"
    severity: Severity = "moderate"


class LoafingIntervention(BaseModel):
    target_agent: str
    intervention_type: InterventionType
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""
    effort_estimate: EffortEstimate = "1d"
    risk: Literal["low", "medium", "high"] = "medium"
    composition_target_pattern: str | None = None


class AttachedPlaybook(BaseModel):
    role: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_profile_pattern: str | None = None
    gini_delta: float = 0.0
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class SocialLoafingDetection(BaseModel):
    team_id: str | None = None
    agent_contributions: list[AgentContribution]
    gini_coefficient: float = Field(ge=0.0, le=1.0)
    loafing_quality: Literal["no-loafing", "mild-loafing", "severe-loafing"]
    interventions: list[LoafingIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool = False

    # New in v0.2.0.
    mode: SocialLoafingMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: SocialLoafingProfilePattern = "indeterminate"
    anonymity_audit: AnonymityAudit | None = None
    free_riding_chains: list[FreeRidingChain] = Field(default_factory=list)
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
        out.append("# Social Loafing Detection (Latané, Williams & Harkins)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.team_id:
            out.append(f"_Team: {self.team_id}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(
            f"_Loafing quality: **{self.loafing_quality.upper()}** (severity: {self.severity})_\n"
        )
        out.append(f"_Gini coefficient (contribution inequality): {self.gini_coefficient:.2f}_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), "
                f"{self.tokens_total} tokens, ${self.cost_usd:.4f}, "
                f"{self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## Per-Agent Contribution\n")
        for c in self.agent_contributions:
            out.append(f"\n### {c.agent_name} — role: `{c.role}`\n")
            out.append(f"- **Contribution share:** {c.contribution_share:.2f}\n")
            out.append(
                f"- **Substantive vs cosmetic:** {c.substantive_work_count} substantive / "
                f"{c.cosmetic_work_count} cosmetic\n"
            )
            out.append(f"- **Loafing score:** {c.loafing_score:.2f}\n")
            out.append(f"\n{c.explanation}\n")

        if self.anonymity_audit:
            aa = self.anonymity_audit
            out.append("\n## Anonymity Audit (Forensic)\n")
            out.append(
                f"- individual_evaluable: {aa.individual_evaluable} | "
                f"task_decomposable: {aa.task_decomposable} | "
                f"contribution_visible: {aa.contribution_visible} | "
                f"cohesion: {aa.cohesion_estimate:.2f}\n"
            )
            if aa.explanation:
                out.append(f"- {aa.explanation}\n")

        if self.free_riding_chains:
            out.append("\n## Free-Riding Chains (Forensic)\n")
            for fc in self.free_riding_chains:
                out.append(
                    f"- **{fc.loafer_agent}**: {fc.cosmetic_pattern} (severity {fc.severity})\n"
                )

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_agent}` "
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
                out.append(f"\n### {pb.title} _(role={pb.role}, failure_mode={pb.failure_mode})_\n")
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

        return "".join(out)
