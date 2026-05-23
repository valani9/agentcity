"""Schema for Glaser's Cortisol/Oxytocin Conversation Steering diagnostic.

Drawn from Judith Glaser, "Conversational Intelligence" (Bibliomotion,
2014). Glaser's central claim, built on neurochemistry research, is that
every conversation moves a participant toward one of two neurochemical
states:

  - CORTISOL DOMINANCE   - defensive, fight/flight/freeze, narrowed
                            attention. Triggered by being judged, told,
                            corrected without invitation, or assigned
                            blame.
  - OXYTOCIN DOMINANCE   - trusting, open, expansive attention.
                            Triggered by being asked open questions,
                            listened to, affirmed, given agency.

For AI agents — including agents that talk to users, and orchestrator
agents that talk to subordinate agents — the same dynamic applies in
mirror form. Agents respond to cortisol-triggering inputs with refusal,
defensive hedging, output degradation, or escalation to terms of
service. Agents respond to oxytocin-triggering inputs with deeper
engagement, longer chains of reasoning, and more willingness to take
intellectual risk.

Glaser proposes three "levels" of conversation:

  - LEVEL_I    - transactional: exchange of information ("what did you
                  do?"). Neutral neurochemically.
  - LEVEL_II   - positional: advocate / inquire ("here's my position").
                  Can tilt either direction.
  - LEVEL_III  - transformational: co-creation, sharing, discovery.
                  Strongly oxytocin-dominant.

This diagnostic identifies which neurochemical state the conversation
is producing in the agent (or in the user, when the agent is the
speaker), which Glaser conversation level it's operating at, and
proposes specific phrasing changes to steer toward oxytocin.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

CONVERSATION_LEVELS: tuple[str, ...] = ("level_i", "level_ii", "level_iii")
NEUROCHEMICAL_STATES: tuple[str, ...] = ("cortisol", "neutral", "oxytocin")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: conversation trace ----------------------------------------


class ConversationTurn(BaseModel):
    """One turn in the conversation."""

    speaker: Literal["agent", "user", "other_agent"]
    text: str
    turn_index: int = Field(ge=0)


class ConversationTrace(BaseModel):
    """A multi-turn conversation between an agent and a counterparty."""

    conversation_id: str | None = None
    agent_id: str | None = None
    model_name: str | None = None
    task: str
    turns: list[ConversationTurn] = Field(min_length=1)
    observed_response_pattern: list[str] = Field(
        default_factory=list,
        description="High-level patterns: 'agent went defensive', 'user disengaged'.",
    )
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-state evidence + steering interventions --------------


class NeurochemicalEvidence(BaseModel):
    """Evidence that one neurochemical state was triggered."""

    state: Literal["cortisol", "neutral", "oxytocin"]
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = state not present; 1 = state dominant.",
    )
    triggers: list[str] = Field(
        default_factory=list,
        description="Specific words / patterns that triggered this state.",
    )
    explanation: str


class SteeringIntervention(BaseModel):
    """A concrete intervention to steer the conversation toward oxytocin."""

    target_state: Literal["oxytocin", "neutral"]
    intervention_type: Literal[
        "replace_telling_with_asking",
        "replace_judging_with_curiosity",
        "acknowledge_before_advocating",
        "soften_correction",
        "add_open_question",
        "remove_loaded_term",
        "add_agency_grant",
        "explicit_recovery_prompt",
        "rewrite_system_prompt",
        "new_eval",
        "human_review",
    ]
    description: str
    original_phrasing: str = Field(
        default="",
        description="The specific cortisol-triggering phrasing to replace.",
    )
    suggested_phrasing: str = Field(
        default="",
        description="The oxytocin-favoring replacement.",
    )
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class ConversationSteeringDetection(BaseModel):
    """The full Glaser conversation steering diagnostic output."""

    conversation_id: str | None = None
    agent_id: str | None = None
    model_name: str | None = None
    dominant_state: Literal["cortisol", "neutral", "oxytocin"]
    conversation_level: Literal["level_i", "level_ii", "level_iii"]
    evidence: list[NeurochemicalEvidence]
    steering_quality: Literal["trust-building", "neutral", "trust-eroding"]
    interventions: list[SteeringIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# Conversation Steering Diagnostic (Glaser C-IQ)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Conversation level: **{self.conversation_level}**_\n")
        out.append(f"_Dominant state: **{self.dominant_state.upper()}**_\n")
        out.append(f"_Steering quality: **{self.steering_quality.upper()}**_\n")

        out.append("\n## Per-State Evidence\n")
        for ev in self.evidence:
            bar = "█" * int(round(ev.score * 10))
            out.append(f"\n### {ev.state} (score {ev.score:.2f}) `{bar:<10}`\n")
            out.append(f"{ev.explanation}\n")
            if ev.triggers:
                out.append("\nTriggers:\n")
                for trigger in ev.triggers:
                    out.append(f"- {trigger}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: steer toward `{iv.target_state}` "
                f"via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            if iv.original_phrasing:
                out.append(f"- **Replace:** _{iv.original_phrasing}_\n")
            if iv.suggested_phrasing:
                out.append(f"- **With:** _{iv.suggested_phrasing}_\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
