"""Schema for the 4 Motivation Traps Detector.

Drawn from Bror Saxberg & Frederick Hess, "Breakthrough Leadership in the
Digital Age" (2013) and Saxberg's subsequent learning-science writing in
HBR and the Kern Foundation curriculum. Saxberg synthesizes the
attribution / expectancy / self-efficacy literatures (Weiner, Bandura,
Vroom) into four discrete reasons a learner / agent abandons a task:

  - VALUES        - the agent doesn't see the task as worth doing
  - SELF_EFFICACY - the agent doesn't believe it can succeed
  - EMOTIONS      - emotional state (anxiety, frustration) blocks engagement
  - ATTRIBUTION   - the agent blames the wrong cause for prior failures
                     (e.g. attributes effort-controllable failures to luck)

The diagnostic identifies which trap is dominant in an agent's
observed task-abandonment pattern and proposes an intervention targeted
to that specific trap. Generic "try harder" interventions are explicitly
ineffective — Saxberg's central thesis is that the four traps need four
different fixes.

Applied to AI agents: the same four traps show up in language-model
behavior. An agent refuses a task because it's "uncertain" (values
trap if uncertainty masks disagreement; self-efficacy trap if
uncertainty reflects capability collapse). An agent loops on retries
without learning (attribution trap — attributing fixable errors to
unfixable causes). An agent's outputs degrade after a single rejection
(emotional trap — the rejection signal cascades).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

MOTIVATION_TRAPS: tuple[str, ...] = (
    "values",
    "self_efficacy",
    "emotions",
    "attribution",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent motivation trace -------------------------------------


class AgentMotivationTrace(BaseModel):
    """A trace ready for the 4 Motivation Traps diagnostic."""

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
    self_reports: list[str] = Field(
        default_factory=list,
        description="Explicit agent statements about confidence / effort / blame.",
    )
    abandonment_signal: str = Field(
        description="What the agent did when it gave up (refused / looped / drifted).",
    )
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: trap evidence + interventions -----------------------------


class TrapEvidence(BaseModel):
    """One motivation trap, scored against the trace."""

    trap: Literal["values", "self_efficacy", "emotions", "attribution"]
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = trap not present; 1 = trap is dominant in the abandonment pattern.",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class MotivationIntervention(BaseModel):
    """A concrete intervention targeted at the dominant trap."""

    target_trap: Literal["values", "self_efficacy", "emotions", "attribution"]
    intervention_type: Literal[
        "reframe_task_value",
        "scaffold_subtasks",
        "decompose_with_examples",
        "lower_difficulty_step",
        "emotional_reset_prompt",
        "remove_punitive_signal",
        "reattribute_to_effort",
        "show_controllable_cause",
        "explicit_recovery_prompt",
        "rewrite_system_prompt",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class MotivationDetection(BaseModel):
    """The full 4 Motivation Traps diagnostic output."""

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
    trap_evidence: list[TrapEvidence]
    dominant_trap: Literal[
        "values",
        "self_efficacy",
        "emotions",
        "attribution",
        "none",
    ]
    motivation_quality: Literal["motivated", "at-risk", "abandoning"]
    interventions: list[MotivationIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# 4 Motivation Traps Diagnostic (Saxberg)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Task class: **{self.task_class}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Motivation quality: **{self.motivation_quality.upper()}**_\n")
        out.append(f"_Dominant trap: **{self.dominant_trap}**_\n")

        out.append("\n## Per-Trap Evidence\n")
        for ev in self.trap_evidence:
            bar = "█" * int(round(ev.score * 10))
            out.append(f"\n### {ev.trap} (score {ev.score:.2f}) `{bar:<10}`\n")
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
                f"\n### Intervention {i}: target `{iv.target_trap}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
