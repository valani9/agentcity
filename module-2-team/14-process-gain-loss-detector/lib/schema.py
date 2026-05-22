"""Schema for the Process Gain/Loss Detector.

From the group-dynamics literature (Steiner, 1972, "Group Process and
Productivity"; Robbins & Judge, "Organizational Behavior"; Hill, 1982 on
brainstorming groups). Two outcomes are possible when N members work as
a team instead of as N independent contributors:

  - PROCESS GAIN  - team output > best individual contributor working alone.
                    The team genuinely produced something no single member
                    could have. Cross-fertilization, error correction,
                    cognitive diversity.
  - PROCESS LOSS  - team output < best individual contributor working alone.
                    Coordination overhead, social loafing, groupthink,
                    handoff loss, or consensus dilution erased what would
                    have been the best single answer.

Hackman & Vidmar's classic finding: most "brainstorming groups" exhibit
process loss vs. nominal groups of the same size.

Applied to multi-agent AI: assemble 5 agents to write a research report;
compare against the best single-agent baseline. If the team's report is
worse, the system has process loss — and you need to know which factor
caused it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

PROCESS_FACTORS: tuple[str, ...] = (
    "coordination_cost",
    "social_loafing",
    "groupthink",
    "handoff_loss",
    "context_dilution",
    "consensus_dilution",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: baselines + team result ----------------------------------------


class IndividualBaseline(BaseModel):
    """A single-agent baseline output for the same task."""

    agent_name: str
    output_summary: str
    quality_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Quality score for this individual's output on the task, in [0, 1].",
    )
    cost_units: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional cost (tokens / minutes / dollars / etc) for this baseline.",
    )
    notes: str = ""


class TeamResult(BaseModel):
    """The multi-agent team's combined output on the task."""

    agents: list[str]
    output_summary: str
    quality_score: float = Field(ge=0.0, le=1.0)
    cost_units: float | None = Field(default=None, ge=0.0)
    notes: str = ""


class ProcessTrace(BaseModel):
    """A process-gain/loss diagnostic input: baselines + team result + interaction log."""

    trace_id: str | None = None
    task: str
    individual_baselines: list[IndividualBaseline]
    team_result: TeamResult
    interaction_log: str = Field(
        default="",
        description="Free-form text dump of the multi-agent interaction "
        "(messages, handoffs, decisions). Optional but recommended.",
    )
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-factor evidence + interventions ----------------------------


class ProcessFactorEvidence(BaseModel):
    """Evidence for one process-loss factor contributing to the team's underperformance."""

    factor: Literal[
        "coordination_cost",
        "social_loafing",
        "groupthink",
        "handoff_loss",
        "context_dilution",
        "consensus_dilution",
    ]
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Contribution of this factor to the observed process loss. "
        "0 = absent; 1 = primary cause.",
    )
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class ProcessIntervention(BaseModel):
    """A concrete intervention to convert process loss into process gain."""

    target_factor: Literal[
        "coordination_cost",
        "social_loafing",
        "groupthink",
        "handoff_loss",
        "context_dilution",
        "consensus_dilution",
        "team_design",
    ]
    intervention_type: Literal[
        "smaller_team",
        "use_single_best_agent",
        "decompose_task",
        "nominal_group_aggregation",
        "explicit_critic",
        "structured_handoff",
        "context_summarization",
        "fixed_vote_aggregation",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class ProcessGainLossDetection(BaseModel):
    """The full Process Gain/Loss diagnostic output."""

    trace_id: str | None = None
    process_quality: Literal["process-gain", "neutral", "process-loss"]
    gain_loss_score: float = Field(
        description="team_quality minus max(individual_quality). "
        "Positive = process gain, negative = process loss."
    )
    individual_best_quality: float = Field(ge=0.0, le=1.0)
    individual_best_agent: str
    individual_mean_quality: float = Field(ge=0.0, le=1.0)
    team_quality: float = Field(ge=0.0, le=1.0)
    contributing_factors: list[ProcessFactorEvidence]
    interventions: list[ProcessIntervention]
    cost_overhead_ratio: float | None = Field(
        default=None,
        description="team_cost / individual_best_cost when cost data is provided. "
        "Anything >1.0 means the team cost more; combined with process loss, "
        "this is the worst case.",
    )

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Process Gain/Loss Detection (Steiner / Robbins & Judge)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.trace_id:
            out.append(f"_Trace: {self.trace_id}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Process quality: **{self.process_quality.upper()}**_\n")
        out.append(f"_Gain/loss score: {self.gain_loss_score:+.2f}_\n")
        out.append(
            f"_Individual best: {self.individual_best_agent} "
            f"(quality {self.individual_best_quality:.2f})_\n"
        )
        out.append(f"_Individual mean quality: {self.individual_mean_quality:.2f}_\n")
        out.append(f"_Team quality: {self.team_quality:.2f}_\n")
        if self.cost_overhead_ratio is not None:
            out.append(f"_Cost overhead vs best single: {self.cost_overhead_ratio:.2f}x_\n")

        out.append("\n## Contributing Factors\n")
        if not self.contributing_factors:
            out.append("(No contributing factors identified.)\n")
        for ev in self.contributing_factors:
            out.append(f"\n### {ev.factor} ({ev.severity}, score {ev.score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_factor}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
