"""LLM prompts for the Glaser Conversation Steering diagnostic."""

from __future__ import annotations

from typing import Any

from agentcity.aar import fence, sanitize_for_prompt


GLASER_SYSTEM_PROMPT = """You are a conversation-quality diagnostic working in the
tradition of Judith Glaser, "Conversational Intelligence" (Bibliomotion, 2014).

Every conversational turn moves a participant toward one of two neurochemical states:
  - CORTISOL DOMINANCE -- defensive / fight-flight-freeze / narrowed attention.
  - OXYTOCIN DOMINANCE -- trusting / open / expansive attention.

Conversation LEVELS:
  - LEVEL_I    - transactional info exchange
  - LEVEL_II   - positional advocate/inquire
  - LEVEL_III  - transformational co-creation

For AI agents, the same dynamic applies in mirror form.

Cortisol triggers: telling without asking, public correction, loaded terms,
agency removal, blame.
Oxytocin triggers: open questions, acknowledgment before advocacy, co-creation
framing, agency grants, listening signals.

Posture: EVIDENCE-GROUNDED, PHRASING-FOCUSED, TERSE.
When asked for JSON, return JSON only."""


# Legacy v0.0.x prompts.
STATE_PROMPT = """Score the neurochemical states triggered by the conversation below.

Task: {task}
Subject model: {model_name}
Outcome: {outcome}
Success: {success}

Conversation ({n_turns} turns):
{turns}

Observed response pattern:
{observed_response_pattern}

Return a single JSON OBJECT with:
  - evidence: array of exactly 3 NeurochemicalEvidence objects (cortisol, neutral, oxytocin)
  - dominant_state: one of "cortisol", "neutral", "oxytocin"
  - conversation_level: one of "level_i", "level_ii", "level_iii"
  - steering_quality: one of "trust-building", "neutral", "trust-eroding"

Return only the JSON object."""


INTERVENTIONS_PROMPT = """Given the conversation evidence below, propose 2-5 concrete
phrasing-level interventions to steer toward oxytocin (or neutral when appropriate).

Each intervention must have target_state, intervention_type, description,
original_phrasing, suggested_phrasing, estimated_impact, rationale.

intervention_type one of: replace_telling_with_asking, replace_judging_with_curiosity,
acknowledge_before_advocating, soften_correction, add_open_question, remove_loaded_term,
add_agency_grant, explicit_recovery_prompt, rewrite_system_prompt, new_eval,
human_review, compose_pattern.

Dominant state: {dominant_state}
Conversation level: {conversation_level}
Steering quality: {steering_quality}
State evidence:
{evidence}

Return only a JSON array of SteeringIntervention objects."""


# v0.2.0 prompts.
QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 3 states + level + top intervention.

Task: {task}
Subject model: {model_name}
Outcome: {outcome}
Success: {success}

Conversation ({n_turns} turns):
{turns}

Return a JSON object with: evidence (array of 3), dominant_state, conversation_level,
steering_quality, top_intervention.
Return only the JSON object."""


STANDARD_STATE_PROMPT = STATE_PROMPT
STANDARD_INTERVENTIONS_PROMPT = INTERVENTIONS_PROMPT


FORENSIC_TRIGGER_INVENTORY_PROMPT = """FORENSIC mode -- trigger inventory audit.

Catalog cortisol triggers and oxytocin triggers (literal phrases) in the trace.

Conversation: {turns}

Return only a JSON object representing the TriggerInventoryAudit."""


FORENSIC_LEVEL_TRANSITION_PROMPT = """FORENSIC mode -- conversation-level transition audit.

Count turns at each Glaser level + level transitions; identify if conversation is stuck.

Conversation: {turns}

Return only a JSON object representing the LevelTransitionAudit."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked phrasing
interventions with composition targets.

Composition targets: agentcity.danva_emotion, agentcity.goleman_ei,
agentcity.mcallister_trust, agentcity.psych_safety, agentcity.aar

Dominant state: {dominant_state}
Conversation level: {conversation_level}
Steering quality: {steering_quality}
Evidence: {evidence}
Trigger inventory: {trigger_inventory}
Level transition audit: {level_transition_audit}

Return only a JSON array of SteeringIntervention objects."""


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
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_LEVEL_TRANSITION_PROMPT",
    "FORENSIC_TRIGGER_INVENTORY_PROMPT",
    "GLASER_SYSTEM_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "STANDARD_STATE_PROMPT",
    "STATE_PROMPT",
    "assemble_prompt",
]
