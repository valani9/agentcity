"""LLM prompts for the SMART Goal Generator."""

from __future__ import annotations

from typing import Any

from vstack.aar import fence, sanitize_for_prompt


SMART_SYSTEM_PROMPT = """You are a SMART-goal generator working in the tradition of
George T. Doran, "There's a S.M.A.R.T. Way to Write Management's Goals and Objectives"
(Management Review, 70(11), 1981).

You take a VAGUE goal and produce a structured SMART goal spec the agent can hold
itself accountable to. Goals must be SPECIFIC, MEASURABLE, ACHIEVABLE, RELEVANT,
TIME-BOUND.

Kill criteria are the MOST important field: agents without abandonment conditions
cause the most expensive incidents.

Posture: HONEST about achievability, TERSE, KILL-CRITERIA-FIRST.
When asked for JSON, return JSON only."""


# Legacy v0.0.x prompt.
SMART_GENERATION_PROMPT = """Generate a SMART goal spec from the vague request below.

Vague goal: {vague_goal}
Context: {context}
Available resources: {available_resources}
Known constraints: {known_constraints}
Deadline hint: {deadline_hint}
Framework hint: {framework}

Return a single JSON object with smart_statement, criteria (array of 5 in order),
completion_criteria, success_metrics, kill_criteria, deadline, open_questions,
overall_smart_score, smart_quality.

If critical context is missing, surface it as open_questions; don't invent details.

Return only the JSON object."""


# v0.2.0 prompts.
QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- produce a minimal SMART goal spec.

Vague goal: {vague_goal}
Context: {context}
Deadline hint: {deadline_hint}

Return a single JSON object with smart_statement, criteria (array of 5), completion_criteria,
success_metrics (1-2), kill_criteria (1-2), deadline, overall_smart_score, smart_quality.
Return only the JSON object."""


STANDARD_SMART_GENERATION_PROMPT = SMART_GENERATION_PROMPT


FORENSIC_CRITERIA_COMPLETENESS_PROMPT = """FORENSIC mode -- audit criteria completeness.

For each of the 5 SMART criteria, judge whether it's substantively addressed in the
goal spec below. Count addressed_criteria_count (0-5), list weak_criteria and
missing_criteria; estimate completeness (0-1).

Goal spec:
{goal}

Return only a JSON object representing the CriteriaCompletenessAudit."""


FORENSIC_MEASUREMENT_RIGOR_PROMPT = """FORENSIC mode -- audit measurement rigor.

Count operationalizable (machine-checkable) success metrics vs qualitative ones, plus
operationalizable kill criteria. Estimate rigor (0-1).

Goal spec:
{goal}

Return only a JSON object representing the MeasurementRigorAudit."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 3-6 quality-improvement
interventions for a SMART goal spec.

Composition targets: vstack.grpi, vstack.aar, vstack.plus_delta,
vstack.lewin, vstack.devils_advocate

intervention_type one of: tighten_specificity, add_measurement,
calibrate_achievability, ground_relevance, add_deadline, add_kill_criteria,
add_completion_criteria, decompose_goal, new_eval, human_review, compose_pattern.

target_criterion one of: specific, measurable, achievable, relevant, time_bound, overall.

Goal spec:
{goal}
Criteria audit: {criteria_audit}
Rigor audit: {rigor_audit}

Return only a JSON array of SmartGoalIntervention objects."""


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
    "FORENSIC_CRITERIA_COMPLETENESS_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_MEASUREMENT_RIGOR_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "SMART_GENERATION_PROMPT",
    "SMART_SYSTEM_PROMPT",
    "STANDARD_SMART_GENERATION_PROMPT",
    "assemble_prompt",
]
