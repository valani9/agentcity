"""LLM prompt templates for the Social Loafing Detector."""

from __future__ import annotations

from typing import Any

from vstack.aar import fence, sanitize_for_prompt


SOCIAL_LOAFING_SYSTEM_PROMPT = """You are a social-loafing diagnostic grounded in:

1. **Latané, Williams & Harkins (1979)** "Many Hands Make Light the Work."
2. **Karau & Williams (1993)** Meta-analytic review.
3. **Williams, Harkins & Latané (1981)** Identifiability as deterrent.
4. **Comer (1995)** Model of Social Loafing in Real Work Groups.
5. **Hackman (2002)** *Leading Teams*.
6. **Salas et al. (2018)** Team performance review.
7. **Wang et al. (2023)** Cooperative LLM Agents.

Identify which agents loafed, classify their cosmetic patterns, propose interventions.

When asked for JSON, return JSON only."""


QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- per-agent contributions + top intervention.

Task: {task}
Agents: {agents}
Messages: {messages}
Outcome: {outcome}

Return a JSON object:
{{
  "agent_contributions": [...],
  "gini_coefficient": 0-1,
  "loafing_quality": "no-loafing|mild-loafing|severe-loafing",
  "top_intervention": {{ "target_agent": "<name>", "intervention_type": "...", "description": "...", "suggested_implementation": "...", "estimated_impact": "high|medium|low", "rationale": "..." }}
}}

Return only the JSON object."""


STANDARD_CONTRIBUTION_PROMPT = """STANDARD mode -- score per-agent contributions.

Task: {task}
Agents: {agents}
Messages: {messages}
Outcome: {outcome}

For each agent, identify role (primary-contributor/secondary-contributor/loafer/absent)
and substantive/cosmetic message counts.

Return a JSON OBJECT with agent_contributions, gini_coefficient, loafing_quality.
Return only the JSON object."""


STANDARD_INTERVENTIONS_PROMPT = """STANDARD mode -- propose 2-4 ranked interventions.

Contributions: {agent_contributions}
Loafing quality: {loafing_quality}
Task: {task}

Return a JSON array of LoafingIntervention objects. Return only the JSON array."""


FORENSIC_ANONYMITY_PROMPT = """FORENSIC mode -- anonymity / identifiability audit.

For the trace, identify:
- individual_evaluable: is per-agent output observable?
- task_decomposable: can the task be split into per-agent subtasks?
- contribution_visible: is each agent's contribution traceable?
- cohesion_estimate (0-1)
- explanation

Task: {task}
Agents: {agents}
Has per-agent evaluation: {has_per_agent_evaluation}

Return a JSON OBJECT representing the AnonymityAudit. Return only the JSON object."""


FORENSIC_FREE_RIDING_PROMPT = """FORENSIC mode -- trace free-riding chains.

For each loafer, identify their cosmetic pattern (rubber_stamp_chain /
paraphrase_only / approval_only / silent_majority) and which message indices
enabled their free-riding.

Agent contributions: {agent_contributions}
Messages: {messages}

Return a JSON ARRAY of FreeRidingChain objects. Return only the JSON array."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions with composition targets.

Composition targets:
vstack.grpi, vstack.aar, vstack.lewin, vstack.process_gain_loss,
vstack.mcgregor, vstack.lencioni, vstack.smart_goal, vstack.plus_delta,
vstack.devils_advocate, vstack.bias_stack

Contributions: {agent_contributions}
Anonymity audit: {anonymity_audit}
Free-riding chains: {free_riding_chains}
Loafing quality: {loafing_quality}

Return a JSON ARRAY of LoafingIntervention objects ranked highest impact first.
Return only the JSON array."""


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


# Legacy aliases.
LOAFING_PROMPT = STANDARD_CONTRIBUTION_PROMPT
INTERVENTIONS_PROMPT = STANDARD_INTERVENTIONS_PROMPT


__all__ = [
    "FORENSIC_ANONYMITY_PROMPT",
    "FORENSIC_FREE_RIDING_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "INTERVENTIONS_PROMPT",
    "LOAFING_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "SOCIAL_LOAFING_SYSTEM_PROMPT",
    "STANDARD_CONTRIBUTION_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]
