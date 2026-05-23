"""LLM prompts for the Groupthink/Polarization/Contagion diagnostic."""

from __future__ import annotations

from typing import Any

from agentcity.aar import fence, sanitize_for_prompt


DEBATE_SYSTEM_PROMPT = """You are a debate-pathology diagnostician for multi-agent systems,
working in the tradition of Janis 1972 (groupthink), Stoner 1968 + Sunstein 2002
(polarization), and Hatfield/Cacioppo/Rapson 1993 (emotional contagion).

Three pathologies:
  - GROUPTHINK   - premature convergence + dissent suppression + illusion of unanimity
  - POLARIZATION - each round pushes positions toward an extreme
  - CONTAGION    - tone propagates across turns; tone dominates content

Posture: EVIDENCE-GROUNDED, PATHOLOGY-SPECIFIC, INTERVENTION-FOCUSED, TERSE.
When asked for JSON, return JSON only."""


# Legacy v0.0.x prompts.
PATHOLOGY_SCORING_PROMPT = """Score each of the three debate pathologies against this trace.

For each pathology return: pathology, score (0-1), severity (none/low/medium/high),
explanation, evidence_quotes.

Task: {task}
Agents: {agents}
Final decision: {final_decision}
Outcome: {outcome}
Success: {success}

Debate:
{trace}

Return only a JSON array of exactly 3 PathologyEvidence objects in order:
  1. groupthink
  2. polarization
  3. contagion"""


INTERVENTIONS_PROMPT = """Given the pathology analysis below, propose 2-4 interventions
targeting the dominant pathology.

Each intervention has target_pathology, intervention_type, description,
suggested_implementation, estimated_impact, rationale.

intervention_type one of: assign_devils_advocate, require_silent_vote,
round_robin_dissent, diverse_seed_positions, anchor_to_base_rates,
tone_normalization, cool_down_pause, external_arbiter, smaller_panel,
secret_ballot, new_eval, human_review, compose_pattern.

Dominant pathology: {dominant}
Debate quality: {quality}
Evidence:
{evidence}

Trace (reference):
{trace}

Return only a JSON array of DebateIntervention objects."""


# v0.2.0 prompts.
QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 3 pathologies + top intervention.

Task: {task}
Final decision: {final_decision}
Debate: {trace}

Return a JSON object with keys: pathologies (array of 3), top_intervention.
Return only the JSON object."""


STANDARD_PATHOLOGY_SCORING_PROMPT = PATHOLOGY_SCORING_PROMPT
STANDARD_INTERVENTIONS_PROMPT = INTERVENTIONS_PROMPT


FORENSIC_CONVERGENCE_TIMELINE_PROMPT = """FORENSIC mode -- convergence timeline audit.

Track per-round position diversity (0=identical, 1=fully diverse); identify
convergence round + whether convergence was abrupt.

Debate: {trace}

Return only a JSON object representing the ConvergenceTimelineAudit."""


FORENSIC_TONE_CASCADE_PROMPT = """FORENSIC mode -- tone cascade audit.

Count heated turns, calm turns, tone flips; identify dominant tone + estimate
cascade strength (0-1).

Debate: {trace}

Return only a JSON object representing the ToneCascadeAudit."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 interventions with
composition targets.

Composition targets: agentcity.devils_advocate, agentcity.bias_stack,
agentcity.psych_safety, agentcity.aar, agentcity.group_decision

Dominant pathology: {dominant}
Quality: {quality}
Evidence: {evidence}
Convergence audit: {convergence_audit}
Tone cascade audit: {tone_cascade_audit}

Return only a JSON array of DebateIntervention objects."""


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
    "DEBATE_SYSTEM_PROMPT",
    "FORENSIC_CONVERGENCE_TIMELINE_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_TONE_CASCADE_PROMPT",
    "INTERVENTIONS_PROMPT",
    "PATHOLOGY_SCORING_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "STANDARD_PATHOLOGY_SCORING_PROMPT",
    "assemble_prompt",
]
