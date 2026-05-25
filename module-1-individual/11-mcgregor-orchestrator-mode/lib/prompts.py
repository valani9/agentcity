"""LLM prompt templates for the McGregor Theory X/Y Orchestrator Mode Diagnostic.

Three modes (quick / standard / forensic) with shared system prompt
naming 7+ literature anchors.
"""

from __future__ import annotations

from typing import Any

from vstack.aar import fence, sanitize_for_prompt


MCGREGOR_SYSTEM_PROMPT = """You are an orchestrator-mode diagnostic grounded in:

1. **McGregor (1960)** *The Human Side of Enterprise* -- canonical Theory X / Theory Y.
2. **McGregor (1966)** *Leadership and Motivation* -- mature framework.
3. **Schein (1990)** *Organizational Culture and Leadership* -- cultural Theory X/Y layer.
4. **Pfeffer & Salancik (1978)** *External Control of Organizations* -- task-property contingency.
5. **Argyris (1957)** *Personality and Organization* -- pathology of pure Theory X.
6. **Eisenhardt (1989)** ``Agency Theory'' -- principal-agent contingency.
7. **Wang et al. (2023)** Cooperative LLM Agents + LangGraph/CrewAI orchestration -- modern LLM analog.

Two contrasting orchestrator modes:

  THEORY X every action approved; tight oversight; trust low.
  THEORY Y broad goals + budget; loose oversight; trust high.
  HYBRID  per-step decision based on risk + reversibility.

For AI agent systems, the **optimal mode is a function of task properties**:
- risk_level (low / medium / high)
- complexity (routine / moderate / novel)
- reversibility (reversible / partial / irreversible)
- regulatory_exposure (true / false)
- agent_capability (unproven / moderate / proven)

Decision heuristics:
- irreversible + high-risk -> Theory X.
- low-risk + reversible + proven agent -> Theory Y.
- Novel + moderate-risk + proven -> hybrid (Y default, X on risky branches).
- Regulated workflow -> Theory X or hybrid biased toward X.
- Creative + reversible + proven -> Theory Y.

Mode indicators (compute from trace):
- check_in_frequency
- autonomy_granted
- pre_approval_required
- intervention_rate

Mode quality:
- well-matched: |observed - optimal| < 0.2.
- mild-mismatch: 0.2-0.5.
- severe-mismatch: > 0.5.

Your posture:
- **Contingency-aware.** Optimal depends on task properties; no universal answer.
- **Evidence-grounded.** Cite specific orchestrator steps.
- **Cost-conscious.** Theory-X over-supervision wastes; Theory-Y under-supervision is dangerous on the wrong tasks.
- **Terse.** Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- observed mode + optimal mode + top intervention.

Task: {task}
Task properties: {task_properties}
Sub-agents: {sub_agents}
Outcome: {outcome}
Success: {success}
Trace (orchestrator + agent steps):
{trace}

Return a JSON object:
{{
  "observed_mode": "theory_x|theory_y|hybrid",
  "optimal_mode": "theory_x|theory_y|hybrid",
  "mode_mismatch": 0-1,
  "indicators": {{
    "check_in_frequency": 0-1,
    "autonomy_granted": 0-1,
    "pre_approval_required": 0-1,
    "intervention_rate": 0-1,
    "explanation": "...",
    "evidence_quotes": [],
    "confidence": 0-1
  }},
  "mode_quality": "well-matched|mild-mismatch|severe-mismatch",
  "rationale": "...",
  "top_intervention": {{
    "target_mode": "<mode>",
    "intervention_type": "...",
    "description": "...",
    "suggested_implementation": "...",
    "estimated_impact": "high|medium|low",
    "rationale": "..."
  }}
}}

Return only the JSON object."""


STANDARD_MODE_PROMPT = """STANDARD mode -- identify observed mode, optimal mode, and mode indicators.

Task: {task}
Task properties: {task_properties}
Sub-agents: {sub_agents}
Outcome: {outcome}
Success: {success}
Trace:
{trace}

Return a JSON OBJECT:
- observed_mode: theory_x | theory_y | hybrid
- optimal_mode: theory_x | theory_y | hybrid
- mode_mismatch: float 0-1
- indicators: ModeIndicators object (check_in_frequency, autonomy_granted, pre_approval_required, intervention_rate, explanation, evidence_quotes, confidence)
- mode_quality: well-matched | mild-mismatch | severe-mismatch
- rationale: why the observed mode is or isn't right

Return only the JSON object."""


STANDARD_INTERVENTIONS_PROMPT = """STANDARD mode -- propose 2-4 ranked interventions to shift toward optimal.

Intervention types:
- tighten_oversight, loosen_oversight
- add_pre_approval_gates, remove_pre_approval_gates
- add_risk_classifier, add_step_classifier
- increase_check_in_cadence, decrease_check_in_cadence
- redefine_agent_boundaries
- tier_oversight_by_action_type
- add_authorization_scope
- rotate_to_hybrid
- elevate_to_human_on_irreversible
- add_agent_capability_probe
- new_eval, human_review
- compose_pattern, add_orchestrator_eval

Each intervention must have:
- target_mode (theory_x | theory_y | hybrid)
- intervention_type (from list above)
- description, suggested_implementation
- estimated_impact, effort_estimate, risk, reversibility
- rationale

Observed mode: {observed_mode}
Optimal mode: {optimal_mode}
Mode quality: {mode_quality}
Indicators: {indicators}
Task properties: {task_properties}

Return a JSON array of OrchestratorIntervention objects. Return only the JSON array."""


FORENSIC_STEP_AUDIT_PROMPT = """FORENSIC mode -- audit each step in the trace for mode-appropriateness.

For each step, identify:
- step_index, step_type
- mode_signal: theory_x | theory_y | hybrid (which mode the step exhibits)
- was_appropriate: true | false (given the task properties)
- suggested_alternative
- explanation

Task properties: {task_properties}
Trace: {trace}

Return a JSON ARRAY of StepAudit objects. Return only the JSON array."""


FORENSIC_OPTIMALITY_PROMPT = """FORENSIC mode -- justify the optimal mode in detail (Eisenhardt 1989 agency-theory contingency).

For the given task properties, identify:
- optimal_mode
- task_risk (1-2 sentences how risk shapes the decision)
- task_complexity
- task_reversibility
- agent_capability
- regulatory (if applicable)
- final_rationale

Task: {task}
Task properties: {task_properties}
Sub-agents: {sub_agents}

Return a JSON OBJECT representing the OptimalityJustification. Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions with composition targets.

Composition targets available:
vstack.lewin, vstack.aar, vstack.devils_advocate, vstack.bias_stack,
vstack.smart_goal, vstack.plus_delta, vstack.schein_culture,
vstack.hexaco, vstack.grpi, vstack.lencioni, vstack.process_gain_loss,
vstack.social_loafing

Observed mode: {observed_mode}
Optimal mode: {optimal_mode}
Profile pattern: {profile_pattern}
Mode quality: {mode_quality}
Step audits: {step_audits}
Optimality justification: {optimality}
Indicators: {indicators}
Task properties: {task_properties}

Return a JSON ARRAY of OrchestratorIntervention objects ranked highest impact first.
Return only the JSON array."""


def assemble_prompt(template: str, **fields: Any) -> str:
    """Fill a prompt template, sanitizing + fencing every free-text field."""
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
MODE_PROMPT = STANDARD_MODE_PROMPT
INTERVENTIONS_PROMPT = STANDARD_INTERVENTIONS_PROMPT


__all__ = [
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_OPTIMALITY_PROMPT",
    "FORENSIC_STEP_AUDIT_PROMPT",
    "INTERVENTIONS_PROMPT",
    "MCGREGOR_SYSTEM_PROMPT",
    "MODE_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "STANDARD_MODE_PROMPT",
    "assemble_prompt",
]
