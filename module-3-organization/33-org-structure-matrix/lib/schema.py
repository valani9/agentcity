"""Schema for the Org-Structure Matrix Analyzer.

Drawn from the org-design literature consolidated in Galbraith's Star
Model, Mintzberg's structural configurations, and Stanford's Designing
Dynamic Organizations curriculum. The matrix scores six structural
dimensions independently:

  - SPECIALIZATION       — how narrowly are agent roles defined?
  - FORMALIZATION        — how rule-bound vs improvisational is the work?
  - CENTRALIZATION       — where do decisions actually get made?
  - HIERARCHY            — how many levels of supervisory escalation?
  - SPAN_OF_CONTROL      — how many subordinates does each supervisor manage?
  - DEPARTMENTALIZATION  — by what dimension are agents grouped (function,
                            product, customer, geography, matrix)?

Where Schein's Iceberg (#31) and Robbins/Judge's 7-Characteristics (#32)
diagnose *culture*, this pattern diagnoses *structure*. Same agent crew
can have well-aligned culture and the wrong structure for the task —
e.g. a hierarchical orchestrator for a flat creative brainstorm, or a
flat peer crew for a high-stakes incident response that needed clear
escalation.

The diagnostic maps each agent crew to an archetype (flat / hierarchical
/ matrix / centralized-functional / decentralized-product) and reports
the fit gap against the task class.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

STRUCTURE_DIMENSIONS: tuple[str, ...] = (
    "specialization",
    "formalization",
    "centralization",
    "hierarchy",
    "span_of_control",
    "departmentalization",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent crew structure trace ---------------------------------


class AgentRole(BaseModel):
    """One agent's role within the crew structure."""

    agent_id: str
    role_name: str = Field(description="e.g. 'orchestrator', 'researcher', 'reviewer'.")
    reports_to: list[str] = Field(
        default_factory=list,
        description="agent_ids that this agent escalates to. Empty = top-level.",
    )
    grouped_by: Literal["function", "product", "customer", "geography", "matrix", "none"] = Field(
        default="none"
    )
    decision_authority: Literal["full", "partial", "advisory", "none"] = Field(
        default="partial",
        description="Can this agent commit work without escalation?",
    )


class CrewStructureTrace(BaseModel):
    """A crew + task class ready for the structural diagnostic."""

    crew_id: str | None = None
    task: str
    task_class: Literal[
        "creative_brainstorm",
        "research_exploration",
        "incident_response",
        "regulated_workflow",
        "customer_support",
        "code_review",
        "high_throughput_pipeline",
        "general_purpose",
    ] = Field(
        default="general_purpose",
        description="The task class drives the target structure profile.",
    )
    agents: list[AgentRole] = Field(min_length=1)
    observed_behaviors: list[str] = Field(default_factory=list)
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-dimension profile + recommendations -------------------


class StructureDimensionScore(BaseModel):
    """One structural dimension, scored against the crew."""

    dimension: Literal[
        "specialization",
        "formalization",
        "centralization",
        "hierarchy",
        "span_of_control",
        "departmentalization",
    ]
    observed_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = absent / flat / informal; 1 = strongly present / steep / rigid.",
    )
    target_score: float = Field(
        ge=0.0,
        le=1.0,
        description="What the score should be for the given task class.",
    )
    fit_score: float = Field(
        ge=0.0,
        le=1.0,
        description="1 - abs(observed - target). 1 = perfect fit; 0 = inverted.",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class StructureIntervention(BaseModel):
    """A concrete intervention to shift one dimension toward the target."""

    target_dimension: Literal[
        "specialization",
        "formalization",
        "centralization",
        "hierarchy",
        "span_of_control",
        "departmentalization",
    ]
    direction: Literal["increase", "decrease", "redesign"]
    intervention_type: Literal[
        "flatten_hierarchy",
        "add_supervisor_layer",
        "consolidate_roles",
        "split_roles",
        "shift_decision_authority",
        "regroup_by_product",
        "regroup_by_function",
        "introduce_matrix",
        "add_routing_layer",
        "remove_routing_layer",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class StructureAnalysis(BaseModel):
    """The full Org-Structure Matrix diagnostic output."""

    crew_id: str | None = None
    task_class: Literal[
        "creative_brainstorm",
        "research_exploration",
        "incident_response",
        "regulated_workflow",
        "customer_support",
        "code_review",
        "high_throughput_pipeline",
        "general_purpose",
    ]
    archetype: Literal[
        "flat-peer",
        "hierarchical",
        "centralized-functional",
        "decentralized-product",
        "matrix",
        "mixed",
    ]
    dimensions: list[StructureDimensionScore]
    overall_fit: float = Field(
        ge=0.0,
        le=1.0,
        description="Mean fit score across the six dimensions.",
    )
    fit_quality: Literal["well-fit", "partial-fit", "misfit"]
    biggest_gap: Literal[
        "specialization",
        "formalization",
        "centralization",
        "hierarchy",
        "span_of_control",
        "departmentalization",
        "none",
    ]
    interventions: list[StructureIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Org-Structure Matrix Analysis\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        out.append(f"_Task class: **{self.task_class}**_\n")
        out.append(f"_Archetype: **{self.archetype}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Fit quality: **{self.fit_quality.upper()}**_\n")
        out.append(f"_Overall fit: {self.overall_fit:.2f}_\n")
        out.append(f"_Biggest gap: **{self.biggest_gap}**_\n")

        out.append("\n## Per-Dimension Profile\n")
        out.append("Each row shows observed structure vs target for this task class.\n\n")
        for d in self.dimensions:
            obs_bar = "█" * int(round(d.observed_score * 10))
            target_bar = "·" * int(round(d.target_score * 10))
            out.append(
                f"- **{d.dimension}**: obs {d.observed_score:.2f} `{obs_bar:<10}` "
                f"target {d.target_score:.2f} `{target_bar:<10}` fit {d.fit_score:.2f}\n"
            )

        out.append("\n## Evidence\n")
        for d in self.dimensions:
            out.append(f"\n### {d.dimension} (fit {d.fit_score:.2f})\n")
            out.append(f"{d.explanation}\n")
            if d.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in d.evidence_quotes:
                    out.append(f"> {quote}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: {iv.direction} `{iv.target_dimension}` "
                f"via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
