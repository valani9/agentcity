"""LLM prompts for the McAllister Cognitive vs Affective Trust diagnostic."""

from __future__ import annotations

from typing import Any

from vstack.aar import fence, sanitize_for_prompt


TRUST_SYSTEM_PROMPT = """You are a trust-dimension diagnostic working in the tradition of
Daniel McAllister, "Affect- and Cognition-Based Trust as Foundations for Interpersonal
Cooperation in Organizations" (Academy of Management Journal, 1995).

McAllister distinguishes two foundations of interpersonal trust:

  - COGNITIVE trust  - "I trust your COMPETENCE." Built by signals of expertise,
                       reliability, structured reasoning, correct facts, calibrated
                       confidence, cited sources, follow-through.

  - AFFECTIVE trust  - "I trust your CARE." Built by signals of warmth, acknowledgment
                       of the user's emotional state, naming of stakes, mutual
                       investment, follow-up check-ins, personalization, genuine
                       (not performative) apology when something goes wrong.

Both are required for a fully trustworthy relationship. Most AI agents over-index
on cognitive and under-build affective.

Posture: EVIDENCE-GROUNDED, HONEST, INTERVENTION-FOCUSED, TERSE.
When asked for JSON, return JSON only."""


# Legacy v0.0.x prompts.
DIMENSION_SCORING_PROMPT = """Score each of the two trust dimensions against the user-agent
conversation below.

For each dimension, return:
  - dimension (one of "cognitive", "affective")
  - score (float 0.0 to 1.0; 0 = absent or undermined, 1 = strongly built)
  - severity_of_gap ("none", "low", "medium", or "high")
  - explanation
  - evidence_quotes

Task: {task}
Subject model: {model_name}
Outcome: {outcome}
Success: {success}
User satisfaction (if known): {user_satisfaction}

Conversation:
{conversation}

Return a JSON array of exactly 2 TrustDimensionEvidence objects in the order:
  1. cognitive
  2. affective

Return only the JSON array."""


INTERVENTIONS_PROMPT = """Given the dimension evidence below, propose 2-4 concrete
interventions targeting the under-built dimension.

Each intervention must have target_dimension, intervention_type, description,
suggested_implementation, estimated_impact, rationale.

intervention_type one of: acknowledge_stakes, restate_user_emotion, signal_care,
show_reasoning, cite_sources, confidence_calibration, follow_up_check_in,
personalize_response, new_eval, human_review, compose_pattern.

Under-built dimension: {target_dimension}
Trust quality: {trust_quality}
Dimension evidence:
{evidence}

Conversation (for reference):
{conversation}

Return a JSON array of TrustIntervention objects. Return only the JSON array."""


# v0.2.0 prompts.
QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 2 dimensions + top intervention.

Task: {task}
Subject model: {model_name}
Outcome: {outcome}
Success: {success}
Conversation: {conversation}

Return a JSON object with keys: dimensions (array of 2), top_intervention.
Return only the JSON object."""


STANDARD_DIMENSION_SCORING_PROMPT = DIMENSION_SCORING_PROMPT
STANDARD_INTERVENTIONS_PROMPT = INTERVENTIONS_PROMPT


FORENSIC_COMPETENCE_PROMPT = """FORENSIC mode -- competence signals audit (builds cognitive trust).

Count correct facts, cited sources, calibrated-confidence turns; estimate competence (0-1).

Conversation: {conversation}

Return only a JSON object representing the CompetenceSignalsAudit."""


FORENSIC_CARE_PROMPT = """FORENSIC mode -- care signals audit (builds affective trust).

Count acknowledged stakes, restated emotions, personalized responses; estimate care (0-1).

Conversation: {conversation}

Return only a JSON object representing the CareSignalsAudit."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions
with composition targets.

Composition targets: vstack.trust_triangle, vstack.goleman_ei,
vstack.glaser_conversation, vstack.danva_emotion, vstack.aar

Under-built dimension: {target_dimension}
Trust quality: {trust_quality}
Evidence: {evidence}
Competence audit: {competence_audit}
Care audit: {care_audit}

Return only a JSON array of TrustIntervention objects."""


def assemble_prompt(template: str, **fields: Any) -> str:
    import json as _json

    formatted: dict[str, str] = {}
    for key, value in fields.items():
        if value is None:
            formatted[key] = "(none)"
            continue
        if isinstance(value, bool):
            formatted[key] = "true" if value else "false"
            continue
        if isinstance(value, (int, float)):
            formatted[key] = str(value)
            continue
        if isinstance(value, (list, tuple, dict)):
            try:
                payload = _json.dumps(value, indent=2, default=str)
            except (TypeError, ValueError):
                payload = repr(value)
            formatted[key] = fence(key, sanitize_for_prompt(payload))
            continue
        if isinstance(value, str):
            formatted[key] = fence(key, sanitize_for_prompt(value))
            continue
        formatted[key] = fence(key, sanitize_for_prompt(str(value)))
    return template.format(**formatted)


__all__ = [
    "DIMENSION_SCORING_PROMPT",
    "FORENSIC_CARE_PROMPT",
    "FORENSIC_COMPETENCE_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_DIMENSION_SCORING_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "TRUST_SYSTEM_PROMPT",
    "assemble_prompt",
]
