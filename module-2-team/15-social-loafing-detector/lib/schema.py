"""Schema for the Social Loafing Detector.

Latané, Williams & Harkins (1979), "Many Hands Make Light the Work: The
Causes and Consequences of Social Loafing" (Journal of Personality and
Social Psychology, 37(6)). When individual contribution is anonymous
within a group, individuals reduce effort. The reduction is largest when
the task is unstructured, evaluation is collective, and the link between
individual effort and group outcome is opaque.

Applied to multi-agent AI systems: when N agents are assigned to a task,
substantive contribution often pools to 1-2 agents while others
rubber-stamp, paraphrase, or produce cosmetic work. The diagnostic reads
a multi-agent execution trace, measures per-agent contribution share +
substantive-vs-cosmetic-work breakdown, and identifies loafing agents
along with concrete interventions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: a multi-agent execution trace --------------------------------


class AgentMessage(BaseModel):
    """One message in a multi-agent execution trace, attributed to a specific agent."""

    from_agent: str
    to_agent: str | None = Field(
        default=None,
        description="Target agent (or None for broadcast/team-channel messages).",
    )
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
    """A multi-agent execution trace ready for the Social Loafing diagnostic."""

    team_id: str | None = None
    task: str
    agents: list[str]
    messages: list[AgentMessage]
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-agent contribution + interventions ----------------------


class AgentContribution(BaseModel):
    """Per-agent contribution metrics within the multi-agent task."""

    agent_name: str
    contribution_share: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of substantive work attributable to this agent (sums to ~1.0 across team).",
    )
    substantive_work_count: int = Field(
        ge=0,
        description="Number of substantive contributions (proposals, critiques, decisions, tool calls).",
    )
    cosmetic_work_count: int = Field(
        ge=0,
        description="Number of cosmetic contributions (rubber-stamps, paraphrases, generic acknowledgments).",
    )
    loafing_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = full contributor, 1.0 = pure loafer. High when contribution_share is low "
        "AND cosmetic_work_count dominates.",
    )
    role: Literal["primary-contributor", "secondary-contributor", "loafer", "absent"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class LoafingIntervention(BaseModel):
    """A concrete intervention to reduce social loafing."""

    target_agent: str = Field(
        description="Specific loafing agent to target, or '__team__' for whole-team intervention.",
    )
    intervention_type: Literal[
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
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class SocialLoafingDetection(BaseModel):
    """The full Social Loafing diagnostic output."""

    team_id: str | None = None
    agent_contributions: list[AgentContribution]
    gini_coefficient: float = Field(
        ge=0.0,
        le=1.0,
        description="Inequality of contribution share across the team. 0 = perfectly equal, "
        "1 = one agent does everything.",
    )
    loafing_quality: Literal["no-loafing", "mild-loafing", "severe-loafing"]
    interventions: list[LoafingIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Social Loafing Detection (Latané, Williams & Harkins)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.team_id:
            out.append(f"_Team: {self.team_id}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Loafing quality: **{self.loafing_quality.upper()}**_\n")
        out.append(f"_Gini coefficient (contribution inequality): {self.gini_coefficient:.2f}_\n")

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
            if c.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in c.evidence_quotes:
                    out.append(f"> {quote}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_agent}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
