"""LLM prompt templates for the Lencioni Five Dysfunctions Diagnostic.

Preserves legacy v0.0.x PYRAMID_SCORE_PROMPT + INTERVENTIONS_PROMPT
constants and adds v0.2.0 mode-specific templates.
"""

from __future__ import annotations

from typing import Any

from agentcity.aar import fence, sanitize_for_prompt


LENCIONI_SYSTEM_PROMPT = """You are a multi-agent-systems team-dynamics diagnostic grounded in:

1. **Lencioni (2002)** *The Five Dysfunctions of a Team*.
2. **Lencioni (2005)** *Overcoming the Five Dysfunctions of a Team*.
3. **Edmondson (1999)** Psychological safety.
4. **Hackman (2002)** *Leading Teams*.
5. **Salas et al. (2018)** Team performance review.
6. **Schein (1990)** Organizational culture.
7. **Wang et al. (2023)** Cooperative LLM Agents.

The pyramid (foundation first):
1. ABSENCE OF TRUST
2. FEAR OF CONFLICT
3. LACK OF COMMITMENT
4. AVOIDANCE OF ACCOUNTABILITY
5. INATTENTION TO RESULTS

When asked for JSON, return JSON only."""


# Legacy v0.0.x prompts.
PYRAMID_SCORE_PROMPT = """Score each of the five dysfunctions for the multi-agent team below.

Goal: {goal}
Outcome: {outcome}
Success: {success}
Agents: {agents}

Trace:
{trace}

For each of the five dysfunctions return:
- dysfunction (canonical id from the pyramid)
- severity (high/medium/low/none)
- score (0-1)
- explanation
- evidence_quotes

Return only a JSON array of DysfunctionEvidence."""


INTERVENTIONS_PROMPT = """Given the dominant dysfunction and the trace evidence below, propose 2-5 ranked interventions.

Dominant: {dominant}
Evidence: {evidence}
Trace: {trace}

Return only a JSON array of Intervention objects."""


# v0.2.0 prompts (mode-specific). Standard reuses the legacy structure.
QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 5 dysfunctions + top intervention.

Goal: {goal}
Outcome: {outcome}
Success: {success}
Agents: {agents}
Trace: {trace}

Return a JSON object: dysfunctions (array of 5), top_intervention.
Return only the JSON object."""


STANDARD_PYRAMID_PROMPT = PYRAMID_SCORE_PROMPT
STANDARD_INTERVENTIONS_PROMPT = INTERVENTIONS_PROMPT


FORENSIC_CASCADE_PROMPT = """FORENSIC mode -- cascade audit.

Given the pyramid scores, identify whether the foundation drives higher tiers.
Return a JSON OBJECT representing the CascadeAudit.

Pyramid scores: {pyramid_score}

Return only the JSON object."""


FORENSIC_PSYCH_SAFETY_PROMPT = """FORENSIC mode -- Edmondson psychological-safety audit.

Count challenge_signal_count, silent_dissent_count, and estimate safety_estimate.
Return a JSON OBJECT representing the PsychSafetyAudit.

Trace: {trace}

Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions with composition targets.

Composition targets: agentcity.grpi, agentcity.edmondson_psych_safety,
agentcity.trust_triangle, agentcity.devils_advocate, agentcity.bias_stack,
agentcity.smart_goal, agentcity.aar, agentcity.plus_delta

Dominant: {dominant}
Evidence: {evidence}
Cascade audit: {cascade_audit}
Psych safety audit: {psych_safety_audit}

Return a JSON array of Intervention objects. Return only the JSON array."""


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
    "FORENSIC_CASCADE_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_PSYCH_SAFETY_PROMPT",
    "INTERVENTIONS_PROMPT",
    "LENCIONI_SYSTEM_PROMPT",
    "PYRAMID_SCORE_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "STANDARD_PYRAMID_PROMPT",
    "assemble_prompt",
]
