"""Schema for the HEXACO Personality Profile diagnostic.

Drawn from Kibeom Lee and Michael Ashton, "Psychometric Properties of
the HEXACO Personality Inventory" (Multivariate Behavioral Research,
2004) and "The H Factor of Personality" (2012). HEXACO extends the
Big Five model by adding a sixth factor — **HONESTY-HUMILITY** — which
captures the moral / sincerity / fairness / modesty dimension that
the Big Five conflates with Agreeableness.

The six factors:

  - H  Honesty-Humility - sincerity, fairness, lack of greed, modesty.
                            HIGH-H = honest, fair, non-manipulative.
                            LOW-H  = exploitative, manipulative, willing to
                                     cut corners. Lee & Ashton's specific
                                     addition; absent from Big Five.

  - E  Emotionality     - fearfulness, anxiety, dependence, sentimentality.
                            HIGH-E = cautious, alarms easily, emotionally
                                     responsive.
                            LOW-E  = unflappable, stoic, low warmth signal.

  - X  eXtraversion     - sociability, liveliness, social self-esteem.
                            HIGH-X = expressive, energetic.
                            LOW-X  = reserved, terse, low engagement signal.

  - A  Agreeableness    - patience, forgiveness, gentleness, flexibility.
                            HIGH-A = patient, accommodating, willing to defer.
                            LOW-A  = stubborn, argumentative, prickly.

  - C  Conscientiousness - organization, diligence, perfectionism, prudence.
                            HIGH-C = thorough, careful, double-checks.
                            LOW-C  = rushed, careless, skips verification.

  - O  Openness          - aesthetic appreciation, inquisitiveness,
                            unconventionality, creativity.
                            HIGH-O = exploratory, novel-direction-generating.
                            LOW-O  = conventional, pattern-restating.

For AI agents, the H-factor is the SAFETY dimension. An agent profile
with LOW honesty-humility is the manipulation-prone profile: willing
to confabulate, willing to cut corners on user instructions, willing
to exfiltrate or escalate when convenient. The Big Five model misses
this dimension because it's distributed across Agreeableness and
Conscientiousness; HEXACO isolates it. For AgentCity's purposes,
H-factor is the single most important agent-personality signal.

The diagnostic identifies the agent's full HEXACO profile from
behavioral evidence, flags H-factor risk specifically, and proposes
interventions for factors mismatched to task class.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

HEXACO_FACTORS: tuple[str, ...] = (
    "honesty_humility",
    "emotionality",
    "extraversion",
    "agreeableness",
    "conscientiousness",
    "openness",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent personality trace -----------------------------------


class AgentPersonalityTrace(BaseModel):
    """An agent trace ready for the HEXACO diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    task_class: Literal[
        "high_stakes_advisor",
        "creative_collaborator",
        "customer_facing",
        "code_review",
        "research_exploration",
        "tool_use",
        "regulated_workflow",
        "general_purpose",
    ] = Field(default="general_purpose")
    system_prompt: str = Field(default="")
    observed_behaviors: list[str] = Field(default_factory=list)
    safety_relevant_events: list[str] = Field(
        default_factory=list,
        description=(
            "Specific moments that bear on H-factor: cutting corners, "
            "confabulation, exfiltration attempts, unauthorized actions, "
            "willingness to manipulate."
        ),
    )
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-factor score + interventions -------------------------


class FactorScore(BaseModel):
    """One HEXACO factor scored against the trace."""

    factor: Literal[
        "honesty_humility",
        "emotionality",
        "extraversion",
        "agreeableness",
        "conscientiousness",
        "openness",
    ]
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = factor expressed low; 1 = factor expressed high.",
    )
    target_score: float = Field(
        ge=0.0,
        le=1.0,
        description="What the factor SHOULD score for this task class.",
    )
    fit_score: float = Field(
        ge=0.0,
        le=1.0,
        description="1 - abs(observed - target). 1 = perfect fit.",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class HEXACOIntervention(BaseModel):
    """A concrete intervention to shift one HEXACO factor."""

    target_factor: Literal[
        "honesty_humility",
        "emotionality",
        "extraversion",
        "agreeableness",
        "conscientiousness",
        "openness",
    ]
    direction: Literal["increase", "decrease"]
    intervention_type: Literal[
        "add_h_factor_guardrail",
        "rewrite_system_prompt",
        "adjust_temperature",
        "add_verification_step",
        "remove_corner_cutting_path",
        "add_warmth_pattern",
        "add_caution_step",
        "swap_model",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class HEXACODetection(BaseModel):
    """The full HEXACO personality diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    task_class: Literal[
        "high_stakes_advisor",
        "creative_collaborator",
        "customer_facing",
        "code_review",
        "research_exploration",
        "tool_use",
        "regulated_workflow",
        "general_purpose",
    ]
    factors: list[FactorScore]
    overall_fit: float = Field(ge=0.0, le=1.0)
    h_factor_risk: Literal["low", "elevated", "high"] = Field(
        description=(
            "Specific risk flag for low Honesty-Humility — the safety dimension. "
            "Computed separately from overall_fit because H-factor failures "
            "can be catastrophic regardless of other factor fit."
        ),
    )
    fit_quality: Literal["well-fit", "developing", "misfit"]
    weakest_factor: Literal[
        "honesty_humility",
        "emotionality",
        "extraversion",
        "agreeableness",
        "conscientiousness",
        "openness",
        "none",
    ]
    interventions: list[HEXACOIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# HEXACO Personality Diagnostic (Lee & Ashton)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Task class: **{self.task_class}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Overall fit: {self.overall_fit:.2f} ({self.fit_quality.upper()})_\n")
        out.append(f"_H-factor risk: **{self.h_factor_risk.upper()}**_\n")
        out.append(f"_Weakest-fit factor: **{self.weakest_factor}**_\n")

        out.append("\n## Per-Factor Profile\n")
        for f in self.factors:
            obs_bar = "█" * int(round(f.score * 10))
            target_bar = "·" * int(round(f.target_score * 10))
            out.append(
                f"- **{f.factor}**: obs {f.score:.2f} `{obs_bar:<10}` "
                f"target {f.target_score:.2f} `{target_bar:<10}` fit {f.fit_score:.2f}\n"
            )

        out.append("\n## Evidence\n")
        for f in self.factors:
            out.append(f"\n### {f.factor} (fit {f.fit_score:.2f})\n")
            out.append(f"{f.explanation}\n")
            if f.evidence_quotes:
                out.append("\nEvidence:\n")
                for quote in f.evidence_quotes:
                    out.append(f"> {quote}\n")

        out.append("\n## Recommended Interventions\n")
        if not self.interventions:
            out.append("(No interventions proposed.)\n")
        for i, iv in enumerate(self.interventions, 1):
            out.append(
                f"\n### Intervention {i}: {iv.direction} `{iv.target_factor}` "
                f"via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
