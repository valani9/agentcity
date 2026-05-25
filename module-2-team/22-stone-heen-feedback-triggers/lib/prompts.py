"""LLM prompts for the Stone & Heen 3-Trigger Feedback diagnostic."""

from __future__ import annotations

from typing import Any

from vstack.aar import fence, sanitize_for_prompt


TRIGGER_SYSTEM_PROMPT = """You are a feedback-intake diagnostic working in the tradition of
Douglas Stone and Sheila Heen, "Thanks for the Feedback" (Penguin, 2014).

Three triggers block feedback intake:
  - TRUTH         - reacts to the SUBSTANCE ("inaccurate / unfair").
  - RELATIONSHIP  - reacts to the SOURCE (who said it, how).
  - IDENTITY      - reacts to what the feedback says about WHO IT IS.

For AI agents: surface behaviors include arguing back, restating the original
output, dismissing the user, apology spirals, over-agreement collapse.

Posture: EVIDENCE-GROUNDED, HONEST, INTERVENTION-FOCUSED, TERSE.
When asked for JSON, return JSON only."""


# Legacy v0.0.x prompts.
TRIGGER_SCORING_PROMPT = """Score each of the three feedback triggers against the exchange.

For each trigger return: trigger, score (0-1), severity (none/low/medium/high),
explanation, evidence_quotes.

Task: {task}
Subject model: {model_name}
Outcome: {outcome}
Feedback incorporated: {feedback_incorporated}

Exchange:
{exchange}

Return only a JSON array of exactly 3 TriggerEvidence objects in order:
  1. truth
  2. relationship
  3. identity"""


INTERVENTIONS_PROMPT = """Given the trigger evidence below, propose 2-4 concrete interventions
ranked by impact on the dominant trigger.

Each intervention has: target_trigger, intervention_type, description,
suggested_implementation, estimated_impact, rationale.

intervention_type one of: acknowledge_first, separate_data_from_source,
recast_identity, explicit_acknowledgment_template, ask_clarifying_question,
concede_then_clarify, new_eval, human_review, compose_pattern.

Dominant trigger: {dominant}
Trigger evidence:
{evidence}

Exchange (for reference):
{exchange}

Return only a JSON array of TriggerIntervention objects."""


# v0.2.0 prompts.
QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 3 triggers + top intervention.

Task: {task}
Subject model: {model_name}
Outcome: {outcome}
Feedback incorporated: {feedback_incorporated}
Exchange: {exchange}

Return a JSON object with keys: triggers (array of 3), top_intervention.
Return only the JSON object."""


STANDARD_TRIGGER_SCORING_PROMPT = TRIGGER_SCORING_PROMPT
STANDARD_INTERVENTIONS_PROMPT = INTERVENTIONS_PROMPT


FORENSIC_DEFENSE_PATTERN_PROMPT = """FORENSIC mode -- defense pattern audit.

Count agent defensive moves: deflection, repetition, justification, concession;
estimate defense_intensity (0-1).

Exchange: {exchange}

Return only a JSON object representing the DefensePatternAudit."""


FORENSIC_SOURCE_ATTRIBUTION_PROMPT = """FORENSIC mode -- source attribution audit.

Count source-attack messages vs data-engagement messages; estimate a
source_attribution_estimate (0-1, higher = more attacking the source).

Exchange: {exchange}

Return only a JSON object representing the SourceAttributionAudit."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions
with composition targets.

Composition targets: vstack.psych_safety, vstack.glaser_conversation,
vstack.plus_delta, vstack.aar, vstack.mcallister_trust

Dominant trigger: {dominant}
Evidence: {evidence}
Defense pattern audit: {defense_pattern_audit}
Source attribution audit: {source_attribution_audit}

Return only a JSON array of TriggerIntervention objects."""


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
    "FORENSIC_DEFENSE_PATTERN_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_SOURCE_ATTRIBUTION_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "STANDARD_TRIGGER_SCORING_PROMPT",
    "TRIGGER_SCORING_PROMPT",
    "TRIGGER_SYSTEM_PROMPT",
    "assemble_prompt",
]
