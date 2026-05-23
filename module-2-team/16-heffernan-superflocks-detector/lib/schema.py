"""Schema for the Heffernan Superflocks Detector.

Margaret Heffernan's "Forget the Pecking Order at Work" (TED Talk, 2015;
also "A Bigger Prize", Simon & Schuster, 2014) and the original Purdue
biologist William Muir's chicken-flock experiment (1996-2010s).

The Muir/Heffernan finding: if you select chickens for INDIVIDUAL egg
production over generations and breed only the top performers each
generation, you produce a "superflock" of the most-productive birds.
The expected result was that the superflock would be the most productive
overall. Instead, the superflock cannibalized each other (literally —
pecking each other to death). Only three of the original nine
"superchickens" survived after generations of selection. Productivity
COLLAPSED.

The control flock (where no individual selection happened — all the
chickens were kept) sustained slightly-less-productive but far more
robust laying behavior over the same generations.

Heffernan's organizational reading: when you optimize for *individual*
top performance, you destroy *collective* productivity. The systems that
sustain group output are *cooperation, complementarity, and redundancy*,
not raw individual talent.

Applied to AI agent systems: when an orchestrator always routes to the
"best" single agent, the system becomes fragile. The other agents'
complementary capabilities go unused; redundancy collapses; the system
has no fallback when the top agent fails; and the orchestrator is
optimizing for individual-agent benchmarks at the expense of crew
robustness. The detector measures these patterns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: routing trace + agent roster --------------------------------


class RoutingDecision(BaseModel):
    """One routing decision the orchestrator made."""

    task_id: str = Field(description="Identifier for the task being routed.")
    task_class: str = Field(
        default="",
        description="Optional task class for grouping (research, qa, coding, etc.).",
    )
    routed_to: str
    candidates: list[str] = Field(
        default_factory=list,
        description="Other agents that could have been chosen.",
    )
    reason: str = Field(
        default="",
        description="Why this agent was chosen ('highest score', 'load balancing', etc.).",
    )
    outcome: Literal["success", "failure", "partial", "unknown"] = "unknown"
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentCapability(BaseModel):
    """One agent's per-task-class capability score."""

    agent_name: str
    capability_scores: dict[str, float] = Field(
        default_factory=dict,
        description="task_class -> capability score in [0, 1].",
    )


class RoutingTrace(BaseModel):
    """A trace of orchestrator routing decisions over a window of tasks."""

    trace_id: str | None = None
    window_description: str = Field(
        description="What window of activity this trace covers (e.g. 'last 1000 tasks').",
    )
    agents: list[str]
    capabilities: list[AgentCapability] = Field(default_factory=list)
    routing_decisions: list[RoutingDecision]
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: superflocks-pattern evidence + interventions ---------------


class SuperflocksMetric(BaseModel):
    """One quantitative superflocks-pattern metric."""

    name: Literal[
        "top_agent_share",
        "routing_gini",
        "complementarity_utilization",
        "fallback_coverage",
        "failure_clustering",
    ]
    value: float = Field(ge=0.0, le=1.0)
    explanation: str
    severity: Literal["none", "low", "medium", "high"]


class FragilityIntervention(BaseModel):
    """A concrete intervention to reduce superflocks fragility."""

    intervention_type: Literal[
        "introduce_routing_jitter",
        "require_minimum_agent_diversity",
        "add_capability_complement_check",
        "rotate_lead_agent",
        "load_balancing_floor",
        "redundant_routing",
        "swap_top_agent_offline_drill",
        "human_review",
        "new_eval",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class SuperflocksDetection(BaseModel):
    """The full Heffernan Superflocks diagnostic output."""

    trace_id: str | None = None
    top_agent: str | None = Field(
        default=None,
        description="The agent the orchestrator routes to most often.",
    )
    top_agent_share: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of routing decisions that went to the top agent.",
    )
    routing_gini: float = Field(
        ge=0.0,
        le=1.0,
        description="Gini coefficient over routing share. 0=perfectly equal; "
        "1=top agent gets everything.",
    )
    fragility_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0=robust crew with diverse routing; 1=fragile superflocks pattern.",
    )
    fragility_quality: Literal["robust", "concentrated", "superflocks"]
    metrics: list[SuperflocksMetric]
    interventions: list[FragilityIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Superflocks Detection (Heffernan)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.trace_id:
            out.append(f"_Trace: {self.trace_id}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Fragility quality: **{self.fragility_quality.upper()}**_\n")
        out.append(f"_Fragility score: {self.fragility_score:.2f}_\n")
        if self.top_agent:
            out.append(f"_Top agent: **{self.top_agent}** (share {self.top_agent_share:.2f})_\n")
        out.append(f"_Routing Gini: {self.routing_gini:.2f}_\n")

        out.append("\n## Per-Metric Detail\n")
        for m in self.metrics:
            bar = "█" * int(round(m.value * 20))
            out.append(f"- **{m.name}** ({m.severity}): {m.value:.2f}  {bar}\n")
            out.append(f"  {m.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(f"\n### Intervention {i}: `{iv.intervention_type}`\n")
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
