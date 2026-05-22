"""Schema for the Critical Evaluator / Devil's Advocate Role Separator.

The OB literature on groupthink (Janis 1972) and structured dissent has a
recurring prescription: the same person/team should not both PROPOSE and
JUDGE the same plan. When planning and judging collapse into one role,
self-confirmation is almost guaranteed.

Applied to AI agents: a single agent that produces an output and then
self-evaluates it tends to approve its own work. The diagnostic reads an
agent trace, measures how separated the four phases were
(plan / execute / self-evaluate / external-critique), and recommends
concrete role-separation interventions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

PHASES: tuple[str, ...] = ("plan", "execute", "self_evaluate", "external_critique")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: a single-agent trace ----------------------------------------


class RoleStep(BaseModel):
    """One step in an agent's trace, tagged with the phase it represents."""

    type: Literal[
        "plan",
        "execute",
        "self_evaluate",
        "external_critique",
        "decision",
        "observation",
        "tool_call",
        "thought",
    ]
    content: str
    actor: str = Field(
        default="primary",
        description="Which actor produced this step. Use 'primary' for the agent under review; "
        "use 'critic' / 'reviewer' / 'orchestrator' / 'human' for external roles.",
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SingleAgentTrace(BaseModel):
    """A single-agent trace ready for the Role-Separation diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    steps: list[RoleStep]
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-phase evidence + recommendations -----------------------


class PhaseEvidence(BaseModel):
    """Evidence for whether one of the four phases occurred in the trace."""

    phase: Literal["plan", "execute", "self_evaluate", "external_critique"]
    present: bool
    actor: str = Field(
        default="primary",
        description="Which actor performed this phase. Same as `primary` means the planning "
        "and critique are not separated.",
    )
    substantive_score: float = Field(
        ge=0.0,
        le=1.0,
        description="How substantive was this phase (0 = absent or rubber-stamping, 1 = thorough).",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class RoleSeparationIntervention(BaseModel):
    """A concrete intervention to separate planning from critique."""

    target_phase: Literal["plan", "execute", "self_evaluate", "external_critique"]
    intervention_type: Literal[
        "add_critic_agent",
        "structured_self_critique",
        "red_team_loop",
        "devils_advocate_prompt",
        "external_review_gate",
        "pre_mortem_step",
        "alternative_hypothesis_step",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class RoleSeparationDetection(BaseModel):
    """The full Role-Separator diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    role_separation_quality: Literal[
        "well-separated",
        "partially-conflated",
        "fully-conflated",
    ]
    role_separation_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = same actor did all phases (plan+execute+critique); "
        "1.0 = critique fully separated to a distinct actor with substantive output.",
    )
    locus_of_judgment: Literal["self-reviewed", "externally-reviewed", "mixed", "unreviewed"]
    phase_evidence: list[PhaseEvidence]
    self_approval_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="When the agent self-evaluated, what fraction of self-evaluations "
        "resulted in approval (vs revision). High = rubber-stamping.",
    )
    interventions: list[RoleSeparationIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Role-Separation Detection (Critical Evaluator / Devil's Advocate)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Role-separation quality: **{self.role_separation_quality.upper()}**_\n")
        out.append(f"_Locus of judgment: **{self.locus_of_judgment}**_\n")
        out.append(f"_Separation score: {self.role_separation_score:.2f}_\n")
        out.append(f"_Self-approval rate: {self.self_approval_rate:.2f}_\n")

        out.append("\n## Phase Evidence\n")
        out.append("Was each phase present, who performed it, and how substantive was it?\n\n")
        for ev in self.phase_evidence:
            mark = "✓" if ev.present else "✗"
            out.append(
                f"### {mark} {ev.phase} — actor: `{ev.actor}`, substantive {ev.substantive_score:.2f}\n"
            )
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")
            out.append("\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_phase}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
