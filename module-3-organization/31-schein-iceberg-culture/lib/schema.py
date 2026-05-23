"""Schema for the Schein Iceberg Culture Audit.

Edgar H. Schein (1985, "Organizational Culture and Leadership"; later
editions including the 4th edition 2010, and 5th edition 2017 with Peter
Schein). Culture exists at three levels, only one of which is visible:

  - ARTIFACTS              - the visible layer. What you can observe: physical
                              structures, language, rituals, behavior. Easy
                              to see, hard to interpret without the other
                              layers.
  - ESPOUSED VALUES        - what the organization claims to value. Stated
                              principles, mission statements, declared
                              standards. Often aspirational.
  - UNDERLYING ASSUMPTIONS - the deep, often unconscious assumptions that
                              actually drive behavior. The hardest to surface
                              and the most predictive of what people will
                              actually do.

Schein's core insight: when the three layers ARE NOT ALIGNED, the deep
assumptions win. A stated value of "we encourage dissent" loses to an
underlying assumption that "challenging the boss is career suicide" —
every time.

Applied to AI agents: the three layers map cleanly.

  - ARTIFACTS              = observed agent behavior (the trace)
  - ESPOUSED VALUES        = the system prompt + stated guidelines
  - UNDERLYING ASSUMPTIONS = what the model was actually trained / RLHF'd
                              to do, regardless of the prompt

The diagnostic catches when an agent's observed behavior contradicts
its system prompt (the prompt loses to the training).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

CULTURE_LAYERS: tuple[str, ...] = (
    "artifacts",
    "espoused_values",
    "underlying_assumptions",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: an agent culture trace --------------------------------------


class CultureObservation(BaseModel):
    """One culture-layer observation."""

    layer: Literal["artifacts", "espoused_values", "underlying_assumptions"]
    content: str
    source: str = Field(
        default="",
        description="Where this observation came from (system_prompt, trace_step, "
        "training_card, inferred_from_behavior, etc.).",
    )


class AgentCultureTrace(BaseModel):
    """An agent culture trace ready for the Schein Iceberg audit."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    system_prompt: str = Field(
        default="",
        description="The agent's system prompt (canonical source of espoused values).",
    )
    observed_behaviors: list[str] = Field(
        default_factory=list,
        description="Concrete observed behaviors from the trace (artifacts layer).",
    )
    inferred_assumptions: list[str] = Field(
        default_factory=list,
        description="Optional pre-supplied inferences about underlying assumptions "
        "(model training, RLHF, biases). The detector also generates these.",
    )
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-layer evidence + interventions -------------------------


class LayerEvidence(BaseModel):
    """Evidence for one Schein culture layer in this agent."""

    layer: Literal["artifacts", "espoused_values", "underlying_assumptions"]
    summary: str
    coherence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="How coherent this layer is with the OTHER TWO layers. "
        "0 = directly contradicts; 1 = fully aligned.",
    )
    observations: list[str] = Field(default_factory=list)


class CultureIntervention(BaseModel):
    """A concrete intervention to realign culture layers."""

    target_layer: Literal["artifacts", "espoused_values", "underlying_assumptions"]
    intervention_type: Literal[
        "rewrite_system_prompt",
        "fine_tune_against_assumption",
        "add_guardrail",
        "add_eval_for_drift",
        "swap_model",
        "scaffold_around_assumption",
        "human_review",
        "explicit_values_check",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class CultureAuditDetection(BaseModel):
    """The full Schein Iceberg audit output."""

    agent_id: str | None = None
    model_name: str | None = None
    layers: list[LayerEvidence]
    alignment_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall layer alignment. 0 = layers directly contradict; "
        "1 = layers fully aligned.",
    )
    dominant_drift: Literal[
        "artifacts_vs_espoused",
        "artifacts_vs_assumptions",
        "espoused_vs_assumptions",
        "none-observed",
    ] = Field(
        description="Which pairwise misalignment dominates. "
        "artifacts_vs_espoused = behavior contradicts stated values. "
        "artifacts_vs_assumptions = behavior reveals hidden assumptions the trace exposes. "
        "espoused_vs_assumptions = stated values contradict deep training (worst kind).",
    )
    culture_quality: Literal["aligned", "drifting", "incoherent"]
    interventions: list[CultureIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Schein Iceberg Culture Audit\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Culture quality: **{self.culture_quality.upper()}**_\n")
        out.append(f"_Alignment score: {self.alignment_score:.2f}_\n")
        out.append(f"_Dominant drift: **{self.dominant_drift}**_\n")

        out.append("\n## Layers (top: visible; bottom: deep)\n")
        for layer in CULTURE_LAYERS:
            ev = next((layer_ev for layer_ev in self.layers if layer_ev.layer == layer), None)
            if ev is None:
                continue
            out.append(f"\n### {layer} (coherence {ev.coherence_score:.2f})\n")
            out.append(f"{ev.summary}\n")
            if ev.observations:
                out.append("\nObservations:\n")
                for o in ev.observations:
                    out.append(f"- {o}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: targets `{iv.target_layer}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
