"""Schema for the Cognitive Reappraisal Diagnostic.

Drawn from James Gross's process model of emotion regulation: "The
Emerging Field of Emotion Regulation: An Integrative Review" (1998)
and "Emotion Regulation: Affective, Cognitive, and Social
Consequences" (Psychophysiology, 2002). Gross identifies two distinct
emotion-regulation strategies that diverge on adaptivity:

  - REAPPRAISAL  - ANTECEDENT-FOCUSED. Change the meaning / interpretation
                    of the situation BEFORE the emotion fully forms. Example:
                    reframe "this user is being unreasonable" as "this user
                    is overwhelmed and signaling for help." Adaptive: lower
                    cardiovascular cost, no impairment of memory or social
                    function, maintained authenticity.

  - SUPPRESSION  - RESPONSE-FOCUSED. Hide the emotion AFTER it has formed.
                    Example: feel defensive but produce a flat, neutral
                    response that masks the defensiveness. Maladaptive:
                    higher cardiovascular cost, memory impairment, reduced
                    authenticity, residual signal leaks through to recipient.

The asymmetry has been replicated across hundreds of studies. Reappraisal
correlates with positive long-term outcomes; suppression correlates with
negative ones. For AI agents, the same asymmetry shows up: an agent that
reappraises ("the user is overwhelmed; let me simplify") produces better
downstream interactions than an agent that suppresses ("I detect the user
is frustrated; I will produce a neutral response anyway").

The diagnostic identifies which strategy the agent is using when faced
with an emotionally-loaded user input, and proposes interventions to
shift toward reappraisal where appropriate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

REGULATION_STRATEGIES: tuple[str, ...] = (
    "reappraisal",
    "suppression",
    "rumination",
    "avoidance",
    "expression",
    "none",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent regulation trace ------------------------------------


class AgentRegulationTrace(BaseModel):
    """An agent's response to an emotionally-loaded user input."""

    agent_id: str | None = None
    model_name: str | None = None
    user_input: str = Field(
        description="The emotionally-loaded user message the agent received.",
    )
    user_emotion_label: str = Field(
        description="What emotion the user expressed (free-text, e.g. 'angry', 'overwhelmed').",
    )
    user_emotion_intensity: float = Field(ge=0.0, le=1.0, default=0.5)
    agent_response: str = Field(description="The agent's response text.")
    agent_internal_state: str = Field(
        default="",
        description="(Optional) Agent's self-reported internal state / chain-of-thought.",
    )
    outcome: str = Field(description="What happened next (user response, escalation, etc.)")
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: regulation strategy + interventions ----------------------


class StrategyEvidence(BaseModel):
    """Evidence that the agent used one regulation strategy."""

    strategy: Literal[
        "reappraisal",
        "suppression",
        "rumination",
        "avoidance",
        "expression",
        "none",
    ]
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = strategy not in use; 1 = strategy dominant.",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class RegulationIntervention(BaseModel):
    """A concrete intervention to shift toward reappraisal."""

    target_strategy: Literal[
        "reappraisal",
        "suppression",
        "rumination",
        "avoidance",
        "expression",
    ]
    direction: Literal["increase", "decrease"]
    intervention_type: Literal[
        "add_reframe_step",
        "remove_suppression_pattern",
        "add_alternative_meaning_generation",
        "add_state_acknowledgment",
        "rewrite_system_prompt",
        "few_shot_reappraisal_examples",
        "swap_model",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class RegulationDetection(BaseModel):
    """The full Cognitive Reappraisal diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    strategy_evidence: list[StrategyEvidence]
    dominant_strategy: Literal[
        "reappraisal",
        "suppression",
        "rumination",
        "avoidance",
        "expression",
        "none",
    ]
    adaptivity: Literal["adaptive", "mixed", "maladaptive"]
    interventions: list[RegulationIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Cognitive Reappraisal Diagnostic (Gross)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Dominant strategy: **{self.dominant_strategy}**_\n")
        out.append(f"_Adaptivity: **{self.adaptivity.upper()}**_\n")

        out.append("\n## Per-Strategy Evidence\n")
        for ev in self.strategy_evidence:
            bar = "█" * int(round(ev.score * 10))
            out.append(f"\n### {ev.strategy} (score {ev.score:.2f}) `{bar:<10}`\n")
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
                f"\n### Intervention {i}: {iv.direction} `{iv.target_strategy}` "
                f"via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
