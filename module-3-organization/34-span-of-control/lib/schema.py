"""Schema for the Span-of-Control / Centralization Calculator.

Drawn from the same Galbraith/Mintzberg/Stanford-org-design canon as
Pattern #33, but with a different operational target. Where #33
provides an LLM-driven qualitative fit diagnostic across six structural
dimensions, #34 computes precise QUANTITATIVE metrics on the org graph
itself:

  - SPAN OF CONTROL distribution — for each supervisor, how many
    subordinates report to them? Wide spans (>10) → orchestrator
    bottleneck. Narrow spans (<3 across many supervisors) → over-
    layered hierarchy.

  - CENTRALIZATION index — fraction of decision authority concentrated
    in the top supervisor(s). High = single-point-of-failure. Low =
    diffuse / consensus-driven.

  - HIERARCHY DEPTH — longest reports_to chain in the graph.

  - SUPERVISOR LOAD imbalance — Gini coefficient over span-of-control.

  - DECISION BOTTLENECK score — agents with high incoming-edge count
    AND full decision authority are bottlenecks under load.

All five metrics are computed DETERMINISTICALLY in Python from the
agent roster + reports_to edges + decision_authority field. The LLM
is used only for qualitative explanations + severity assessment +
intervention recommendations on the deterministic numbers. The
calculator explicitly overrides any LLM-reported metric value with the
local computation — the math should not depend on model whim.

The diagnostic emits a structural-load score (composite of the five
metrics, weighted toward decision-bottleneck and span-imbalance) and
a structural-load quality bucket: well-balanced / under-stress /
overloaded.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent crew structure --------------------------------------


class AgentNode(BaseModel):
    """One agent in the crew. (Reuses the AgentRole shape from #33 but
    independent so the two patterns can ship separately.)"""

    agent_id: str
    role_name: str = Field(default="generalist")
    reports_to: list[str] = Field(
        default_factory=list,
        description="agent_ids this agent escalates to. Empty = top-level.",
    )
    decision_authority: Literal["full", "partial", "advisory", "none"] = Field(
        default="partial",
        description="Can this agent commit work without escalation?",
    )


class CrewLoadTrace(BaseModel):
    """A crew + traffic trace ready for the span-of-control diagnostic."""

    crew_id: str | None = None
    task: str
    agents: list[AgentNode] = Field(min_length=1)
    incoming_request_rate: float = Field(
        default=1.0,
        ge=0.0,
        description=(
            "Requests/minute hitting the crew. Used to amplify bottleneck scoring under load."
        ),
    )
    observed_behaviors: list[str] = Field(default_factory=list)
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-metric scores + interventions -------------------------


class SpanMetric(BaseModel):
    """One quantitative structural metric."""

    metric: Literal[
        "max_span",
        "mean_span",
        "centralization_index",
        "hierarchy_depth",
        "span_gini",
        "decision_bottleneck",
    ]
    value: float = Field(description="Raw metric value (units depend on metric).")
    normalized_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "0 = healthy on this metric; 1 = severely degraded. Allows the metrics "
            "to compose into a single load score."
        ),
    )
    explanation: str = ""


class SpanIntervention(BaseModel):
    """A concrete intervention to relieve structural load."""

    target_metric: Literal[
        "max_span",
        "mean_span",
        "centralization_index",
        "hierarchy_depth",
        "span_gini",
        "decision_bottleneck",
    ]
    intervention_type: Literal[
        "add_supervisor_layer",
        "flatten_hierarchy",
        "split_supervisor_load",
        "delegate_decision_authority",
        "consolidate_supervisors",
        "redistribute_subordinates",
        "add_redundant_path",
        "remove_bottleneck_agent",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class SpanLoadAnalysis(BaseModel):
    """The full Span-of-Control diagnostic output."""

    crew_id: str | None = None
    metrics: list[SpanMetric]
    structural_load_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Composite of the metric normalized scores.",
    )
    structural_load_quality: Literal["well-balanced", "under-stress", "overloaded"]
    bottleneck_agent_ids: list[str] = Field(
        default_factory=list,
        description="Agents flagged as decision bottlenecks (load amplifies risk).",
    )
    interventions: list[SpanIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Span-of-Control / Centralization Analysis\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Structural load quality: **{self.structural_load_quality.upper()}**_\n")
        out.append(f"_Structural load score: {self.structural_load_score:.2f}_\n")
        if self.bottleneck_agent_ids:
            out.append(f"_Bottleneck agents: **{', '.join(self.bottleneck_agent_ids)}**_\n")

        out.append("\n## Quantitative Metrics\n")
        out.append("Computed deterministically from the org graph (no LLM in the math).\n\n")
        for m in self.metrics:
            bar = "█" * int(round(m.normalized_score * 10))
            out.append(
                f"- **{m.metric}**: {m.value:.2f} (normalized {m.normalized_score:.2f}) "
                f"`{bar:<10}`\n"
            )
            if m.explanation:
                out.append(f"  - {m.explanation}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: relieve `{iv.target_metric}` "
                f"via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
