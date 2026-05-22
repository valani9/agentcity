"""Schema for the Group Decision Models generator.

From the facilitator canon (Marnie Stewart, Sam Kaner's "Facilitator's Guide
to Participatory Decision-Making" 2014, and the broader meeting-design
literature). Five canonical decision-aggregation methods, each with a
specific trade-off:

  - CONCURRING     - one decisive vote; everyone else stays silent or assents.
                     Fast. Good for low-stakes, reversible, time-pressured
                     decisions where a single competent agent can call it.
  - MAJORITY       - >50% required. Clean tally, no veto. Good for moderate
                     stakes where speed beats unanimity and a 49% minority
                     accepts the outcome.
  - CONSENSUS      - everyone must affirm (or at least not block). Slow.
                     Good for high-stakes, irreversible, regulated decisions
                     where buy-in matters more than speed.
  - FIST_TO_FIVE   - graded support per agent (0 = block, 5 = champion).
                     Surfaces lukewarm support that majority voting hides.
                     Good when degree-of-agreement matters, not just yes/no.
  - UNANIMOUS      - everyone must positively vote yes. Strongest barrier.
                     Reserve for high-stakes irreversible regulated decisions
                     and decisions that require visible team alignment.

This is AgentCity's third generative pattern (alongside #13 GRPI and #24
SMART). It takes a decision context and recommends the appropriate model;
optionally takes per-agent votes and runs the local tally.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

DECISION_MODELS: tuple[str, ...] = (
    "concurring",
    "majority",
    "consensus",
    "fist_to_five",
    "unanimous",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: a decision request + optional votes -------------------------


class DecisionOption(BaseModel):
    """One option on the table."""

    option_id: str
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    """A request to recommend a decision-aggregation method (and optionally tally)."""

    decision_id: str | None = None
    title: str
    options: list[DecisionOption]
    agents: list[str]
    stakes: Literal["low", "medium", "high"]
    reversibility: Literal["reversible", "partial", "irreversible"] = "reversible"
    time_pressure: Literal["none", "moderate", "urgent"] = "moderate"
    expertise_asymmetry: Literal["balanced", "moderate", "high"] = "balanced"
    regulatory_exposure: bool = False
    buy_in_required: bool = Field(
        default=False,
        description="Will agents be expected to ACT on this decision after it's made? "
        "If yes, dissent suppression costs you later.",
    )
    forced_model: (
        Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"] | None
    ) = Field(
        default=None,
        description="Optional override: skip recommendation, use this model.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentVote(BaseModel):
    """One agent's vote on the decision."""

    agent_name: str
    option_id: str | None = Field(
        default=None,
        description="The option the agent voted for. None = abstain (concurring/majority/"
        "consensus) or 'no preference' (fist-to-five).",
    )
    score: int | None = Field(
        default=None,
        ge=0,
        le=5,
        description="Fist-to-five score in [0, 5]. 0 = block; 5 = champion. "
        "Required for fist_to_five model; ignored otherwise.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional confidence in [0, 1]. Used for tie-breaks.",
    )
    comment: str = ""


class AggregationResult(BaseModel):
    """The outcome of running the chosen aggregation on a set of votes."""

    method_used: Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"]
    winner: str | None = Field(
        default=None,
        description="The winning option_id, or None if no decision was reached.",
    )
    outcome: Literal[
        "decided",
        "tied",
        "blocked",
        "insufficient_votes",
        "no_quorum",
    ]
    vote_counts: dict[str, int] = Field(default_factory=dict)
    fist_to_five_averages: dict[str, float] = Field(default_factory=dict)
    dissenters: list[str] = Field(
        default_factory=list,
        description="Agents who voted against the winner or blocked it. Important to "
        "surface — even decided outcomes have dissent worth recording.",
    )
    explanation: str = ""


# --- Output: protocol + optional tally ----------------------------------


class DecisionProtocol(BaseModel):
    """The full Group Decision Models output."""

    decision_id: str | None = None
    title: str
    recommended_model: Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"]
    rationale: str = Field(
        description="Why this model fits the decision properties. 1-3 sentences.",
    )
    protocol_steps: list[str] = Field(
        description="The concrete steps the agent team should follow to run this vote.",
    )
    threshold: str = Field(
        description="The pass threshold (e.g. '>50% majority', 'all agents affirm', "
        "'no agent at <=1 fist-to-five').",
    )
    quorum: int | None = Field(
        default=None,
        description="Minimum number of agents whose vote must be recorded. None = all.",
    )
    tie_breaker: str = Field(
        default="",
        description="How ties are broken when they occur.",
    )
    fallback_model: (
        Literal["concurring", "majority", "consensus", "fist_to_five", "unanimous"] | None
    ) = Field(
        default=None,
        description="Fallback model if the primary doesn't converge.",
    )
    tally_result: AggregationResult | None = Field(
        default=None,
        description="When votes are supplied in the request, the local tally is "
        "produced here without a second LLM call.",
    )

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Group Decision Protocol (Stewart / facilitator canon)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Generated by: {self.generator_model}_\n")
        if self.decision_id:
            out.append(f"_Decision: {self.decision_id}_\n")
        out.append(f"\n## Decision\n\n{self.title}\n")
        out.append(f"\n## Recommended Model\n\n**{self.recommended_model}**\n")
        out.append(f"\n{self.rationale}\n")
        out.append(f"\n**Threshold:** {self.threshold}\n")
        if self.quorum is not None:
            out.append(f"\n**Quorum:** {self.quorum} agents required\n")
        if self.tie_breaker:
            out.append(f"\n**Tie-breaker:** {self.tie_breaker}\n")
        if self.fallback_model:
            out.append(f"\n**Fallback model:** {self.fallback_model}\n")

        out.append("\n## Protocol Steps\n")
        for i, step in enumerate(self.protocol_steps, 1):
            out.append(f"{i}. {step}\n")

        if self.tally_result is not None:
            out.append("\n## Tally Result\n")
            out.append(f"- **Method used:** {self.tally_result.method_used}\n")
            out.append(f"- **Outcome:** {self.tally_result.outcome}\n")
            if self.tally_result.winner is not None:
                out.append(f"- **Winner:** `{self.tally_result.winner}`\n")
            if self.tally_result.vote_counts:
                out.append("- **Vote counts:**\n")
                for opt, count in self.tally_result.vote_counts.items():
                    out.append(f"  - `{opt}`: {count}\n")
            if self.tally_result.fist_to_five_averages:
                out.append("- **Fist-to-five averages:**\n")
                for opt, avg in self.tally_result.fist_to_five_averages.items():
                    out.append(f"  - `{opt}`: {avg:.2f}\n")
            if self.tally_result.dissenters:
                out.append(f"- **Dissenters:** {', '.join(self.tally_result.dissenters)}\n")
            if self.tally_result.explanation:
                out.append(f"\n{self.tally_result.explanation}\n")

        return "".join(out)

    def to_orchestrator_preamble(self) -> str:
        """Render a condensed block for prepending to an orchestrator's prompt."""
        lines = [
            "DECISION PROTOCOL:",
            f"Title: {self.title}",
            f"Model: {self.recommended_model}",
            f"Threshold: {self.threshold}",
        ]
        if self.tie_breaker:
            lines.append(f"Tie-breaker: {self.tie_breaker}")
        if self.fallback_model:
            lines.append(f"Fallback if no convergence: {self.fallback_model}")
        lines.append("Protocol steps:")
        for i, step in enumerate(self.protocol_steps, 1):
            lines.append(f"  {i}. {step}")
        return "\n".join(lines)
