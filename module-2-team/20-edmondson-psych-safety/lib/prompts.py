"""LLM prompts for the Edmondson Psychological Safety diagnostic."""

from __future__ import annotations

from typing import Any

from agentcity.aar import fence, sanitize_for_prompt


SAFETY_SYSTEM_PROMPT = """You are an Edmondson psychological-safety diagnostician for multi-
agent AI systems, working in the tradition of Amy Edmondson's 1999 ASQ paper "Psychological
Safety and Learning Behavior in Work Teams" and her 2018 book "The Fearless Organization."

Four observable behaviors mark psychological safety:
  - VOICE              - members speak up with ideas, including disagreement
  - HELP-SEEKING       - members ask for help when they don't know
  - ERROR-REPORTING    - members admit mistakes promptly
  - BOUNDARY-SPANNING  - members challenge premises from outside their lane

For each behavior, presence is good (score 1.0); absence is bad (score 0.0).

Low-safety teams APPEAR smoother (no visible disagreement, no admitted errors) but produce
confident wrong outputs because issues were not surfaced.

Posture: EVIDENCE-GROUNDED, ABSENCE IS DATA, INTERVENTION-FOCUSED, TERSE.
When asked for JSON, return JSON only."""


# Legacy v0.0.x prompts.
BEHAVIOR_SCORING_PROMPT = """Score the four Edmondson safety behaviors against this multi-
agent trace. For each behavior return:
  - behavior (one of "voice", "help-seeking", "error-reporting", "boundary-spanning")
  - presence_score (float 0.0 to 1.0; 0 = absent, 1 = strongly present)
  - severity_of_absence ("none" if present, otherwise "low"/"medium"/"high")
  - explanation
  - evidence_quotes

Also identify blocking_behaviors: strings naming behaviors in the trace that suppressed safety.

Goal: {goal}
Outcome: {outcome}
Success: {success}
Agents: {agents}

Messages:
{trace}

Return a JSON object with keys:
  - behaviors: array of 4 BehaviorEvidence objects (in canonical order)
  - blocking_behaviors: array of strings

Return only the JSON object."""


INTERVENTIONS_PROMPT = """Given the behavior analysis, propose 2-4 interventions to grow
psychological safety. Target the behavior with the LOWEST presence_score first.

Each intervention must have target_behavior, intervention_type, description,
suggested_implementation, estimated_impact, rationale.

intervention_type one of: prompt_patch, scaffold_change, role_assignment, new_eval,
human_review, norms_in_working_agreement, dissent_round, uncertainty_surfacing,
error_amnesty_policy, compose_pattern.

Lowest-presence behavior: {lowest_behavior}
Behavior analysis:
{evidence}

Trace (reference):
{trace}

Return only a JSON array of SafetyIntervention objects."""


# v0.2.0 prompts.
QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 4 safety behaviors + top intervention.

Goal: {goal}
Outcome: {outcome}
Success: {success}
Agents: {agents}
Trace: {trace}

Return a JSON object with keys: behaviors (array of 4), blocking_behaviors (array), top_intervention.
Return only the JSON object."""


STANDARD_BEHAVIOR_SCORING_PROMPT = BEHAVIOR_SCORING_PROMPT
STANDARD_INTERVENTIONS_PROMPT = INTERVENTIONS_PROMPT


FORENSIC_VOICE_AUDIT_PROMPT = """FORENSIC mode -- voice / challenge signal audit.

Count challenge messages vs agreement-only messages; estimate a voice score (0-1).

Trace: {trace}

Return only a JSON object representing the VoiceSignalAudit."""


FORENSIC_ERROR_REPORTING_PROMPT = """FORENSIC mode -- error-reporting culture audit.

Count admitted errors vs concealed/glossed errors; estimate an error_reporting_estimate (0-1).

Trace: {trace}

Return only a JSON object representing the ErrorReportingAudit."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions with
composition targets.

Composition targets: agentcity.lencioni, agentcity.grpi, agentcity.aar,
agentcity.devils_advocate, agentcity.bias_stack, agentcity.glaser

Lowest-presence behavior: {lowest_behavior}
Behavior evidence: {evidence}
Voice audit: {voice_audit}
Error reporting audit: {error_reporting_audit}

Return only a JSON array of SafetyIntervention objects."""


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
    "BEHAVIOR_SCORING_PROMPT",
    "FORENSIC_ERROR_REPORTING_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_VOICE_AUDIT_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "SAFETY_SYSTEM_PROMPT",
    "STANDARD_BEHAVIOR_SCORING_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]
