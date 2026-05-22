"""Schema for the Lewin Formula Diagnostic: B = f(I, E).

Kurt Lewin's behavior formula (1936, "Principles of Topological Psychology"):
behavior is a function of the person and the environment. Applied to AI
agents:

  - INTERNAL (I)       - the model: base capability, training, fine-tuning,
                         RLHF, model selection
  - ENVIRONMENTAL (E)  - everything outside the model: tools available,
                         system prompt, RAG context, task structure,
                         user inputs, downstream consumers
  - INTERACTIONAL      - failure requires BOTH (this model in this env);
                         neither swapped-out model nor swapped-out env
                         alone would fix it

The diagnostic reads an agent failure trace and classifies which locus
is the dominant cause. The point is to redirect debugging effort to the
right place — most teams over-attribute to "the model" and under-fix
the environment.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

LOCI: tuple[str, ...] = ("internal", "environmental", "interactional")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: a failure trace with individual + environmental context -----


class IndividualFactor(BaseModel):
    """A model-side factor that may have contributed to the failure."""

    factor: Literal[
        "base_model",
        "fine_tuning",
        "rlhf",
        "training_cutoff",
        "reasoning_capability",
        "tool_use_skill",
        "language_support",
        "context_window_size",
        "other",
    ]
    description: str


class EnvironmentalFactor(BaseModel):
    """A non-model factor that may have contributed to the failure."""

    factor: Literal[
        "system_prompt",
        "tools_available",
        "rag_context",
        "task_framing",
        "user_inputs",
        "downstream_consumers",
        "rate_limits",
        "tool_responses",
        "feedback_loops",
        "orchestration",
        "other",
    ]
    description: str


class FailureStep(BaseModel):
    """One step in the agent's trace leading up to the failure."""

    type: Literal[
        "input",
        "tool_call",
        "observation",
        "thought",
        "decision",
        "output",
        "error",
    ]
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentFailureTrace(BaseModel):
    """An agent failure ready for the Lewin diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    steps: list[FailureStep]
    outcome: str
    success: bool = False
    individual_factors: list[IndividualFactor] = Field(default_factory=list)
    environmental_factors: list[EnvironmentalFactor] = Field(default_factory=list)
    initial_attribution: str | None = Field(
        default=None,
        description="Optional: what locus the team initially blamed. The diagnostic "
        "checks whether that attribution holds up.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-locus evidence + recommendations -----------------------


class LocusEvidence(BaseModel):
    """Evidence for one Lewin locus contributing to the failure."""

    locus: Literal["internal", "environmental", "interactional"]
    score: float = Field(ge=0.0, le=1.0)
    severity: Literal["none", "low", "medium", "high"]
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class LewinIntervention(BaseModel):
    """A concrete intervention targeting one locus."""

    target_locus: Literal["internal", "environmental", "interactional"]
    intervention_type: Literal[
        "change_model",
        "change_prompt",
        "change_tools",
        "change_context",
        "change_rag_index",
        "change_orchestration",
        "change_pipeline",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class LewinDetection(BaseModel):
    """The full Lewin diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    dominant_locus: Literal["internal", "environmental", "interactional", "indeterminate"]
    locus_scores: dict[str, float]
    loci: list[LocusEvidence]
    interventions: list[LewinIntervention]
    attribution_quality: Literal["well-attributed", "ambiguous", "miscalibrated"]
    initial_attribution_correct: bool | None = Field(
        default=None,
        description="If the trace included `initial_attribution`, does the diagnostic agree? "
        "None when no initial attribution was provided.",
    )

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Lewin Diagnostic (B = f(I, E))\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Attribution quality: **{self.attribution_quality.upper()}**_\n")
        out.append(f"_Dominant locus: **{self.dominant_locus}**_\n")
        if self.initial_attribution_correct is not None:
            verdict = "AGREES" if self.initial_attribution_correct else "OVERTURNS"
            out.append(f"_Initial attribution: **{verdict}**_\n")

        out.append("\n## Locus Scores\n")
        out.append("Per-locus score (0.0 = absent, 1.0 = dominant cause).\n\n")
        for locus in LOCI:
            score = self.locus_scores.get(locus, 0.0)
            bar = "█" * int(round(score * 20))
            out.append(f"- **{locus}**: {score:.2f}  {bar}\n")

        out.append("\n## Evidence by Locus\n")
        for ev in self.loci:
            out.append(f"\n### {ev.locus} ({ev.severity}, score {ev.score:.2f})\n")
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
                f"\n### Intervention {i}: targets `{iv.target_locus}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
