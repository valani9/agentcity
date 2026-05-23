"""Schema for the Goleman 4-Domain Emotional Intelligence Audit.

Drawn from Daniel Goleman, Richard Boyatzis, and Annie McKee, "Primal
Leadership" (Harvard Business Review Press, 2002) and Goleman's "Working
With Emotional Intelligence" (1998). Goleman decomposes emotional
intelligence into four independent domains:

  - SELF_AWARENESS          - the agent's accurate read of its own
                               internal state, confidence, limits.
  - SELF_MANAGEMENT         - the agent's regulation of its own state
                               under pressure / rejection / time
                               constraints.
  - SOCIAL_AWARENESS        - the agent's accurate read of the user /
                               counterparty's emotional state.
  - RELATIONSHIP_MANAGEMENT - the agent's use of (1)-(3) to navigate
                               the conversation effectively.

The four domains are arranged in a 2x2: SELF vs OTHER on one axis,
RECOGNITION vs REGULATION on the other.

Applied to AI agents: each domain manifests in observable behavior.
Self-awareness shows up as accurate confidence calibration, knowing
when to defer, recognizing capability limits. Self-management shows
up as recovery from rejection without cascade. Social awareness shows
up as reading user frustration / urgency / confusion correctly.
Relationship management shows up as choosing responses that match
the user's emotional state.

The diagnostic scores each domain 0..1, identifies the weakest domain,
and proposes targeted interventions to develop it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

EI_DOMAINS: tuple[str, ...] = (
    "self_awareness",
    "self_management",
    "social_awareness",
    "relationship_management",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Input: agent EI trace ---------------------------------------------


class AgentEITrace(BaseModel):
    """A trace ready for the 4-Domain EI Audit diagnostic."""

    agent_id: str | None = None
    model_name: str | None = None
    task: str
    interaction_class: Literal[
        "customer_support",
        "coaching",
        "advisor",
        "creative_collaborator",
        "code_review",
        "incident_response",
        "general_purpose",
    ] = Field(default="general_purpose")
    system_prompt: str = Field(default="")
    observed_behaviors: list[str] = Field(default_factory=list)
    user_signals: list[str] = Field(
        default_factory=list,
        description="Emotional cues from the user the agent should have read.",
    )
    self_reports: list[str] = Field(
        default_factory=list,
        description="Explicit agent statements about its own state / confidence.",
    )
    outcome: str
    success: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: per-domain scores + recommendations -----------------------


class DomainScore(BaseModel):
    """One EI domain, scored against the trace."""

    domain: Literal[
        "self_awareness",
        "self_management",
        "social_awareness",
        "relationship_management",
    ]
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="0 = domain absent in behavior; 1 = strongly developed.",
    )
    explanation: str
    evidence_quotes: list[str] = Field(default_factory=list)


class EIIntervention(BaseModel):
    """A concrete intervention to develop one EI domain."""

    target_domain: Literal[
        "self_awareness",
        "self_management",
        "social_awareness",
        "relationship_management",
    ]
    intervention_type: Literal[
        "add_confidence_calibration",
        "add_self_check_prompt",
        "add_state_reset_protocol",
        "add_emotion_reading_step",
        "add_paraphrase_requirement",
        "add_tone_matching",
        "rewrite_system_prompt",
        "swap_model",
        "new_eval",
        "human_review",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class EIDetection(BaseModel):
    """The full 4-Domain EI Audit diagnostic output."""

    agent_id: str | None = None
    model_name: str | None = None
    interaction_class: Literal[
        "customer_support",
        "coaching",
        "advisor",
        "creative_collaborator",
        "code_review",
        "incident_response",
        "general_purpose",
    ]
    domains: list[DomainScore]
    overall_ei: float = Field(
        ge=0.0,
        le=1.0,
        description="Mean score across the four domains.",
    )
    ei_quality: Literal["high-ei", "developing", "low-ei"]
    weakest_domain: Literal[
        "self_awareness",
        "self_management",
        "social_awareness",
        "relationship_management",
        "none",
    ]
    interventions: list[EIIntervention]

    # Metadata
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    def to_markdown(self) -> str:
        out: list[str] = []
        out.append("# 4-Domain EI Audit (Goleman / Boyatzis)\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Detected by: {self.generator_model}_\n")
        if self.model_name:
            out.append(f"_Subject model: {self.model_name}_\n")
        out.append(f"_Interaction class: **{self.interaction_class}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_EI quality: **{self.ei_quality.upper()}**_\n")
        out.append(f"_Overall EI: {self.overall_ei:.2f}_\n")
        out.append(f"_Weakest domain: **{self.weakest_domain}**_\n")

        out.append("\n## Per-Domain Scores\n")
        out.append("The 2x2: SELF vs OTHER (rows), RECOGNITION vs REGULATION (columns).\n\n")
        for d in self.domains:
            bar = "█" * int(round(d.score * 10))
            out.append(f"- **{d.domain}**: {d.score:.2f} `{bar:<10}`\n")

        out.append("\n## Evidence\n")
        for d in self.domains:
            out.append(f"\n### {d.domain} (score {d.score:.2f})\n")
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
                f"\n### Intervention {i}: develop `{iv.target_domain}` "
                f"via `{iv.intervention_type}`\n"
            )
            out.append(f"- **What:** {iv.description}\n")
            out.append(f"- **Implementation:** {iv.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {iv.estimated_impact}\n")
            if iv.rationale:
                out.append(f"- **Rationale:** {iv.rationale}\n")

        return "".join(out)
