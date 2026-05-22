"""
Schema for the Lencioni Five Dysfunctions Diagnostic applied to multi-agent
AI systems.

Pyramid (Lencioni 2002, Jossey-Bass):

  5. INATTENTION TO RESULTS         <- top
  4. AVOIDANCE OF ACCOUNTABILITY
  3. LACK OF COMMITMENT
  2. FEAR OF CONFLICT
  1. ABSENCE OF TRUST                <- foundation

Each dysfunction must be addressed in order from the foundation up; a
team cannot fix accountability while still missing trust.

All inputs and outputs are Pydantic models for clean JSON serialization
into observability tools and agent memory systems.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

DYSFUNCTIONS: tuple[str, ...] = (
    "absence-of-trust",
    "fear-of-conflict",
    "lack-of-commitment",
    "avoidance-of-accountability",
    "inattention-to-results",
)


def _utcnow() -> datetime:
    """Timezone-aware UTC now; replaces the deprecated `datetime.utcnow`."""
    return datetime.now(timezone.utc)


# --- Input: a structured multi-agent trace ------------------------------


class AgentMessage(BaseModel):
    """One message exchanged inside a multi-agent system.

    Mirrors common multi-agent framework conventions (CrewAI, AutoGen,
    LangGraph, Microsoft Agent Framework) so trace exports can be ingested
    with minimal transformation.
    """

    timestamp: datetime
    from_agent: str
    to_agent: str | None = None  # None = broadcast to the team
    content: str
    message_type: Literal[
        "task",
        "response",
        "challenge",
        "agreement",
        "question",
        "vote",
        "decision",
        "observation",
        "tool_call",
        "tool_result",
    ]
    metadata: dict[str, Any] = Field(default_factory=dict)


class MultiAgentTrace(BaseModel):
    """A full multi-agent run, ready for the Lencioni diagnostic.

    Minimum useful trace: a stated goal, the team roster, the message log,
    the final outcome, and a success signal. Richer traces (per-agent
    cost, latency, tool counts) produce richer diagnoses.
    """

    team_id: str | None = None
    framework: str | None = None  # e.g. "crewai", "autogen", "langgraph"
    goal: str
    agents: list[str]
    messages: list[AgentMessage]
    outcome: str
    success: bool
    cost_usd: float | None = None
    latency_seconds: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: the Lencioni diagnostic ------------------------------------


class DysfunctionEvidence(BaseModel):
    """Evidence for a single dysfunction observed in the trace.

    Each evidence record names the dysfunction, scores its severity, and
    cites specific message sequences in the trace that demonstrate it.
    """

    dysfunction: Literal[
        "absence-of-trust",
        "fear-of-conflict",
        "lack-of-commitment",
        "avoidance-of-accountability",
        "inattention-to-results",
    ]
    severity: Literal["high", "medium", "low", "none"]
    score: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence_quotes: list[str] = Field(
        default_factory=list,
        description="Specific message excerpts from the trace that illustrate the dysfunction.",
    )


class Intervention(BaseModel):
    """A concrete intervention targeting a specific dysfunction."""

    target_dysfunction: Literal[
        "absence-of-trust",
        "fear-of-conflict",
        "lack-of-commitment",
        "avoidance-of-accountability",
        "inattention-to-results",
    ]
    intervention_type: Literal[
        "scaffold_change",
        "prompt_patch",
        "role_assignment",
        "new_eval",
        "human_review",
        "team_composition_change",
        "communication_protocol",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class LencioniDiagnosis(BaseModel):
    """The full Lencioni diagnostic output for one multi-agent trace."""

    team_id: str | None = None
    dominant_dysfunction: Literal[
        "absence-of-trust",
        "fear-of-conflict",
        "lack-of-commitment",
        "avoidance-of-accountability",
        "inattention-to-results",
        "none-observed",
    ]
    pyramid_score: dict[str, float] = Field(
        description=(
            "Per-dysfunction score in [0.0, 1.0]. Keyed by canonical dysfunction id. "
            "Pyramid order: absence-of-trust first, inattention-to-results last."
        )
    )
    dysfunctions: list[DysfunctionEvidence]
    interventions: list[Intervention]
    overall_team_health: Literal["healthy", "stressed", "dysfunctional"]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        """Render the diagnosis as a markdown report suitable for a team
        dashboard, a Confluence page, or the dashboard of an observability
        tool.
        """
        out: list[str] = []
        out.append("# Lencioni Five Dysfunctions Diagnostic\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Model: {self.generator_model}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Overall team health: **{self.overall_team_health.upper()}**_\n")
        out.append(f"_Dominant dysfunction: **{self.dominant_dysfunction}**_\n")

        out.append("\n## Pyramid Score\n")
        out.append("In pyramid order (foundation first). Higher score = more severe.\n\n")
        for d in DYSFUNCTIONS:
            score = self.pyramid_score.get(d, 0.0)
            bar = "█" * int(round(score * 20))
            out.append(f"- **{d}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Dysfunction\n")
        for ev in self.dysfunctions:
            out.append(f"\n### {ev.dysfunction} ({ev.severity}, score {ev.score:.2f})\n")
            out.append(f"{ev.explanation}\n")
            if ev.evidence_quotes:
                out.append("\nEvidence from the trace:\n")
                for quote in ev.evidence_quotes:
                    out.append(f"> {quote}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_dysfunction}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
