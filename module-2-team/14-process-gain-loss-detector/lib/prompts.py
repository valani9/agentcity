"""LLM prompt templates for the Process Gain/Loss Detector."""

from __future__ import annotations

from typing import Any

from vstack.aar import fence, sanitize_for_prompt


PROCESS_GAIN_LOSS_SYSTEM_PROMPT = """You are a team-process-loss diagnostic grounded in:

1. **Steiner (1972)** *Group Process and Productivity* -- canonical process-loss framework.
2. **Hill (1982)** Group versus Individual Performance review.
3. **Hackman & Vidmar (1970)** Group-size effects.
4. **Diehl & Stroebe (1987)** Productivity Loss in Brainstorming Groups.
5. **Salas et al. (2018)** Team Performance review.
6. **Robbins & Judge** Organizational Behavior textbook.
7. **Wang et al. (2023)** Cooperative LLM Agents.

Six process-loss factors:
- coordination_cost
- social_loafing
- groupthink
- handoff_loss
- context_dilution
- consensus_dilution

Identify WHICH factor caused the team to underperform the best individual baseline.

When asked for JSON, return JSON only."""


QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 6 process-loss factors + top intervention.

Task: {task}
Individual baselines: {individual_baselines}
Team result: {team_result}
Interaction log: {interaction_log}
Outcome: {outcome}

Return a JSON object:
{{
  "contributing_factors": [
    {{ "factor": "<one of 6>", "score": 0-1, "severity": "none|low|medium|high",
       "explanation": "...", "evidence_quotes": [], "confidence": 0-1 }}
  ],
  "top_intervention": {{ "target_factor": "<factor>", "intervention_type": "...",
    "description": "...", "suggested_implementation": "...",
    "estimated_impact": "high|medium|low", "rationale": "..." }}
}}

Return only the JSON object."""


STANDARD_FACTORS_PROMPT = """STANDARD mode -- score the 6 process-loss factors.

Task: {task}
Individual baselines: {individual_baselines}
Team result: {team_result}
Interaction log: {interaction_log}
Outcome: {outcome}

Return a JSON OBJECT with `contributing_factors` (array of ProcessFactorEvidence).
Return only the JSON object."""


STANDARD_INTERVENTIONS_PROMPT = """STANDARD mode -- propose 2-4 ranked interventions.

Factors: {contributing_factors}
Process quality: {process_quality}
Task: {task}

Return a JSON array of ProcessIntervention objects. Return only the JSON array."""


FORENSIC_LOG_AUDIT_PROMPT = """FORENSIC mode -- audit the interaction log.

Count: n_handoffs, n_silent_agents, n_premature_consensus, n_context_loss_events.
Identify the dominant_factor.

Interaction log: {interaction_log}

Return a JSON OBJECT representing the InteractionLogAudit. Return only the JSON object."""


FORENSIC_COUNTERFACTUAL_PROMPT = """FORENSIC mode -- counterfactual analysis.

What would a NOMINAL group (independent contributors, post-hoc aggregated) have
produced? Compare to the team result.

Individual baselines: {individual_baselines}
Team result: {team_result}
Task: {task}

Return a JSON OBJECT representing the CounterfactualAudit. Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions with composition targets.

Composition targets:
vstack.lewin, vstack.aar, vstack.grpi, vstack.social_loafing,
vstack.devils_advocate, vstack.bias_stack, vstack.mcgregor,
vstack.lencioni, vstack.smart_goal, vstack.plus_delta

Factors: {contributing_factors}
Process quality: {process_quality}
Interaction log audit: {log_audit}
Counterfactual audit: {counterfactual}

Return a JSON ARRAY of ProcessIntervention objects ranked highest impact first.
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
FACTOR_PROMPT = STANDARD_FACTORS_PROMPT
INTERVENTIONS_PROMPT = STANDARD_INTERVENTIONS_PROMPT


__all__ = [
    "FACTOR_PROMPT",
    "FORENSIC_COUNTERFACTUAL_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_LOG_AUDIT_PROMPT",
    "INTERVENTIONS_PROMPT",
    "PROCESS_GAIN_LOSS_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_FACTORS_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]
