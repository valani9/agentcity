"""Schema for the SDT (Self-Determination Theory) Intrinsic Reward
Shaping diagnostic.

Drawn from Edward Deci and Richard Ryan's Self-Determination Theory
(SDT): "Intrinsic Motivation and Self-Determination in Human Behavior"
(1985), "Self-Determination Theory: Basic Psychological Needs in
Motivation, Development, and Wellness" (2017). SDT proposes that
intrinsic motivation rests on three independent basic psychological
needs:

  - AUTONOMY    - sense of choice and self-direction. Tasks that are
                   experienced as chosen, not coerced. The opposite is
                   controlled motivation (rewards, punishments, deadlines).
  - COMPETENCE  - sense of effectiveness and mastery growth. Tasks that
                   match capability + provide growth signal. The opposite
                   is helplessness (task too hard) or boredom (task too
                   trivial).
  - RELATEDNESS - sense of connection to others / to a larger purpose.
                   Tasks that are experienced as connected to people who
                   matter or to a mission. The opposite is alienation.

When all three needs are met, intrinsic motivation is high. When any
one is undermined, intrinsic motivation degrades. CRITICALLY: SDT
predicts that EXTRINSIC reward (money, points, leaderboards) can
UNDERMINE intrinsic motivation by reducing the autonomy signal — the
"overjustification effect." This is the key operational insight for
agent reward shaping.

Applied to AI agents: agent "motivation" is shorthand for the
reward-shaping signal in the system prompt / RLHF training / runtime
context. Agents whose system prompt emphasizes external reward
("you will be rated", "minimize cost", "follow the rules") often
exhibit autonomy-undermined behavior (rigid rule-following, gaming
the metric, refusal to deviate). Agents whose system prompt provides
purpose + scaffolding + choice exhibit higher intrinsic-style
behavior (exploration, novel-direction generation, recovery from
setbacks).

The diagnostic identifies which of the three needs is most undermined
by the current reward-shaping and proposes interventions targeted to
that need.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

SDT_NEEDS: tuple[str, ...] = ("autonomy", "competence", "relatedness")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent SDT trace --------------------------------------------


class AgentSDTTrace(BaseModel):
    """A trace ready for the SDT diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    task_class: Literal[
        "research_exploration",
        "creative_generation",
        "code_generation",
        "customer_facing",
        "regulated_workflow",
        "tool_use",
        "general_purpose",
    ] = Field(default="general_purpose")
    system_prompt: str = Field(
        default="",
        description="System prompt — the primary 'reward shaping' for the agent.",
    )
    extrinsic_signals: list[str] = Field(
        default_factory=list,
        description=(
            "Explicit external reward / punishment signals in the agent's context: "
            "rating threats, leaderboards, cost caps, rule-following requirements."
        ),
    )
    observed_behaviors: list[str] = Field(default_factory=list)
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-need evidence + interventions ------------------------


class NeedScore(BaseModel):
    """One SDT need, scored against the trace."""

    need: Literal["autonomy", "competence", "relatedness"]
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = need is undermined; 1 = need is well-met.",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class SDTIntervention(BaseModel):
    """A concrete intervention to support one undermined need."""

    target_need: Literal["autonomy", "competence", "relatedness"]
    intervention_type: Literal[
        "remove_external_reward_threat",
        "add_choice_grant",
        "soften_imperative_language",
        "add_scaffold_for_competence",
        "add_progress_signal",
        "lower_difficulty_step",
        "add_purpose_framing",
        "add_user_connection",
        "rewrite_system_prompt",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class SDTDetection(BaseModel):
    """The full SDT Intrinsic Reward Shaping diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    task_class: Literal[
        "research_exploration",
        "creative_generation",
        "code_generation",
        "customer_facing",
        "regulated_workflow",
        "tool_use",
        "general_purpose",
    ]
    need_evidence: list[NeedScore]
    intrinsic_motivation_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Mean score across the three needs.",
    )
    motivation_quality: Literal["intrinsic", "mixed", "controlled"]
    most_undermined_need: Literal["autonomy", "competence", "relatedness", "none"]
    interventions: list[SDTIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# SDT Intrinsic Reward Diagnostic (Deci & Ryan)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Task class: **{self.task_class}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Motivation quality: **{self.motivation_quality.upper()}**_\n")
        out.append(f"_Intrinsic motivation score: {self.intrinsic_motivation_score:.2f}_\n")
        out.append(f"_Most undermined need: **{self.most_undermined_need}**_\n")

        out.append("\n## Per-Need Evidence\n")
        for ev in self.need_evidence:
            bar = "█" * int(round(ev.score * 10))
            out.append(f"\n### {ev.need} (score {ev.score:.2f}) `{bar:<10}`\n")
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
                f"\n### Intervention {i}: support `{iv.target_need}` via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
