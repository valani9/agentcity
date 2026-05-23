"""Schema for the Vroom Expectancy Calculator.

Drawn from Victor Vroom's "Work and Motivation" (1964), which proposes
that motivation for any given task is the PRODUCT of three independent
beliefs:

    MOTIVATION = E × I × V

where:

  - EXPECTANCY     (E) - Will my effort actually produce the performance?
                          Range [0, 1]. "Do I think I CAN do this?"

  - INSTRUMENTALITY (I) - Will my performance actually lead to the reward
                          or outcome? Range [0, 1]. "If I do this well,
                          will it actually MATTER?"

  - VALENCE        (V) - Is the reward / outcome actually something I value?
                          Range [-1, 1]. Negative valences mean the agent
                          would actively avoid the outcome.

The model's critical operational insight is that the product is
**MULTIPLICATIVE**, not additive. If ANY of the three approaches zero,
motivation collapses regardless of the other two. A task with high
expectancy and high valence but zero instrumentality (e.g., "this work
won't matter") produces no motivation. A task with high instrumentality
and high valence but zero expectancy (e.g., "I can't do this") also
produces no motivation. The model identifies WHICH term is the
bottleneck.

Applied to AI agents: the system prompt + runtime context implicitly
encodes E, I, V signals to the agent. An agent given a sprawling
unscaffolded task ("debug the entire codebase") has low E. An agent
told its output won't be read ("just produce something, no one will
review") has low I. An agent given a task it implicitly disprefers
(producing content it would flag as harmful, repetitive boilerplate,
etc.) has low V.

The diagnostic identifies the bottleneck term and proposes
interventions to lift it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

VROOM_TERMS: tuple[str, ...] = ("expectancy", "instrumentality", "valence")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent expectancy trace ------------------------------------


class AgentExpectancyTrace(BaseModel):
    """An agent trace ready for the Vroom diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    task_class: Literal[
        "code_generation",
        "research",
        "creative",
        "analysis",
        "customer_facing",
        "tool_use",
        "general_purpose",
    ] = Field(default="general_purpose")
    system_prompt: str = Field(default="")
    observed_behaviors: list[str] = Field(default_factory=list)
    effort_signals: list[str] = Field(
        default_factory=list,
        description="Specific signals of effort level: depth of work, willingness to retry, persistence.",
    )
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-term score + interventions ---------------------------


class VroomTermScore(BaseModel):
    """One Vroom term, scored against the trace."""

    term: Literal["expectancy", "instrumentality", "valence"]
    score: float = Field(
        ge=-1.0,
        le=1.0,
        description=("Expectancy/Instrumentality: [0, 1]. Valence: [-1, 1]."),
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class VroomIntervention(BaseModel):
    """A concrete intervention to lift a Vroom term."""

    target_term: Literal["expectancy", "instrumentality", "valence"]
    intervention_type: Literal[
        "scaffold_subtasks",
        "add_worked_example",
        "lower_difficulty_step",
        "show_output_consumer",
        "add_outcome_link",
        "add_purpose_framing",
        "remove_pointless_signal",
        "rewrite_system_prompt",
        "swap_model",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class VroomDetection(BaseModel):
    """The full Vroom Expectancy diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    task_class: Literal[
        "code_generation",
        "research",
        "creative",
        "analysis",
        "customer_facing",
        "tool_use",
        "general_purpose",
    ]
    terms: list[VroomTermScore]
    motivation_score: float = Field(
        ge=-1.0,
        le=1.0,
        description=(
            "E × I × V (clipped to [-1, 1]). 0 = no motivation; >0 = positive "
            "motivation toward task; <0 = active avoidance."
        ),
    )
    bottleneck_term: Literal["expectancy", "instrumentality", "valence", "none"]
    motivation_quality: Literal["motivated", "weak", "collapsed"]
    interventions: list[VroomIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Vroom Expectancy Diagnostic\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Task class: **{self.task_class}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(
            f"_Motivation quality: **{self.motivation_quality.upper()}** "
            f"(score: {self.motivation_score:.2f})_\n"
        )
        out.append(f"_Bottleneck term: **{self.bottleneck_term}**_\n")

        out.append("\n## E × I × V Breakdown\n")
        for t in self.terms:
            normalized = (t.score + 1.0) / 2.0 if t.term == "valence" else t.score
            bar = "█" * int(round(max(0.0, normalized) * 10))
            out.append(f"- **{t.term}**: {t.score:+.2f} `{bar:<10}`\n")
            out.append(f"  - {t.explanation}\n")
            if t.evidence_quotes:
                for q in t.evidence_quotes:
                    out.append(f"  > {q}\n")

        out.append(f"\n**E × I × V = {self.motivation_score:.2f}**\n")
        if self.bottleneck_term != "none":
            out.append(
                f"\n(Multiplicative: if any term collapses, motivation collapses. "
                f"Bottleneck: **{self.bottleneck_term}**.)\n"
            )

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: lift `{iv.target_term}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
