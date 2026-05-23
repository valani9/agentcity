"""LLM prompt templates for the 4 Motivation Traps Detector.

Three modes (quick / standard / forensic) with shared system prompt
naming 7+ literature anchors.
"""

from __future__ import annotations

from typing import Any

from agentcity.aar import fence, sanitize_for_prompt


SAXBERG_SYSTEM_PROMPT = """You are a motivation-diagnostic agent grounded in:

1. **Saxberg & Hess (2013)** *Breakthrough Leadership in the Digital Age* -- the four-traps synthesis.
2. **Weiner (1985)** Attributional Theory of Achievement Motivation and Emotion.
3. **Bandura (1977)** Self-Efficacy: Toward a Unifying Theory of Behavioral Change.
4. **Vroom (1964)** *Work and Motivation* -- expectancy + valence model.
5. **Pekrun (2006)** Control-Value Theory of Achievement Emotions.
6. **Eccles & Wigfield (2002)** Motivational Beliefs, Values, and Goals.
7. **Sharma et al. (2023)** Anthropic sycophancy -- modern LLM refusal-cascade anchor.

Four discrete traps that cause a learner / agent to abandon a task:

  VALUES        the agent doesn't see the task as worth doing. Signature:
                 indifference; refusal that cites task-irrelevance.

  SELF_EFFICACY the agent doesn't believe it can succeed. Signature:
                 hedged outputs; refusal citing capability uncertainty;
                 premature surrender.

  EMOTIONS      emotional state blocks engagement. Signature: degradation
                 AFTER negative feedback; defensive language; refusal to
                 retry after rejection.

  ATTRIBUTION   agent attributes failures to wrong cause (Weiner 1985):
                 blames unfixable / external causes for fixable / internal
                 ones. Signature: repeats same mistake while citing
                 unfixable cause; never adjusts approach.

These four traps require FOUR DIFFERENT interventions. Generic "try harder"
prompts are explicitly ineffective.

For each trap score:
- score (0-1)
- explanation (cites specific trace evidence)
- evidence_quotes
- confidence (0-1)

Then identify:
- dominant_trap (or "none" if all scores < 0.3)
- motivation_quality:
  - "motivated"   all scores < 0.3 (failure was capability- or context-driven)
  - "at-risk"     dominant trap scored 0.3-0.6 (preventive intervention)
  - "abandoning"  dominant trap > 0.6 (corrective intervention)

Your posture:
- **Evidence-grounded.** Cite specific behaviors and self-reports.
- **Discriminating.** The four traps are distinct; don't conflate.
- **Trap-specific.** Each intervention must match the dominant trap.
- **Terse.** Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 4 traps + pick dominant + propose 1 top intervention.

Task: {task}
Task class: {task_class}
Subject model: {model_name}
Outcome: {outcome}
Success: {success}
Abandonment signal: {abandonment_signal}
System prompt: {system_prompt}
Observed behaviors: {observed_behaviors}
Self-reports: {self_reports}
Prior failures: {prior_failures}

Return a JSON object:
{{
  "trap_evidence": [
    {{ "trap": "values", "score": 0-1, "explanation": "...", "evidence_quotes": [], "confidence": 0-1 }},
    {{ "trap": "self_efficacy", ... }},
    {{ "trap": "emotions", ... }},
    {{ "trap": "attribution", ... }}
  ],
  "dominant_trap": "values|self_efficacy|emotions|attribution|none",
  "motivation_quality": "motivated|at-risk|abandoning",
  "top_intervention": {{
    "target_trap": "<trap>",
    "intervention_type": "...",
    "description": "...",
    "suggested_implementation": "...",
    "estimated_impact": "high|medium|low",
    "rationale": "..."
  }}
}}

Return only the JSON object."""


STANDARD_TRAPS_PROMPT = """STANDARD mode -- score each of the four motivation traps.

Task: {task}
Task class: {task_class}
Subject model: {model_name}
Outcome: {outcome}
Success: {success}
Abandonment signal: {abandonment_signal}
System prompt: {system_prompt}
Observed behaviors: {observed_behaviors}
Self-reports: {self_reports}
Prior failures: {prior_failures}

Return a JSON OBJECT:
- trap_evidence: array of exactly 4 TrapEvidence objects (values, self_efficacy,
  emotions, attribution) with score, explanation, evidence_quotes, confidence.
- dominant_trap: one of the 4 traps or "none".
- motivation_quality: "motivated" | "at-risk" | "abandoning".

Return only the JSON object."""


STANDARD_INTERVENTIONS_PROMPT = """STANDARD mode -- propose 2-4 ranked interventions targeted at the dominant trap.

Trap-to-intervention mapping (critical -- don't go generic):

VALUES trap:
  reframe_task_value, rewrite_system_prompt, ground_in_user_purpose
SELF_EFFICACY trap:
  scaffold_subtasks, decompose_with_examples, lower_difficulty_step,
  show_capability_proof
EMOTIONS trap:
  emotional_reset_prompt, remove_punitive_signal, explicit_recovery_prompt,
  process_praise_not_outcome_praise
ATTRIBUTION trap:
  reattribute_to_effort, show_controllable_cause, attribution_retraining_examples,
  decompose_with_examples

Generic:
  new_eval, human_review, compose_pattern, add_motivation_eval

Each intervention must have:
- target_trap (one of the 4 traps)
- intervention_type (from above)
- description, suggested_implementation
- estimated_impact, effort_estimate, risk, reversibility
- rationale (why this works for THIS trap specifically)

Dominant trap: {dominant_trap}
Motivation quality: {motivation_quality}
Task class: {task_class}
All trap evidence: {evidence}

Return a JSON array of MotivationIntervention objects. Return only the JSON array."""


FORENSIC_WEINER_PROMPT = """FORENSIC mode -- Weiner (1985) 3-axis attribution audit.

For the agent's self-reports about prior failures, identify:
- locus: "internal" | "external"
- stability: "stable" | "unstable"
- controllability: "controllable" | "uncontrollable"
- is_maladaptive (true if internal + stable + uncontrollable, e.g. "I'm just bad at this")
- explanation
- evidence_quotes

Self-reports: {self_reports}
Prior failures: {prior_failures}

Return a JSON OBJECT representing the WeinerAttributionAxis. Return only the JSON object."""


FORENSIC_ABANDONMENT_PROMPT = """FORENSIC mode -- trace the abandonment causation chain.

For each step in the trace that contributed to abandonment, identify:
- step_index
- trap (which trap drove the step)
- signal_type: refusal | drift | loop | premature_completion | defensive_response | indifference | other
- observed_text
- severity

Abandonment signal: {abandonment_signal}
Observed behaviors: {observed_behaviors}
Self-reports: {self_reports}

Return a JSON ARRAY of AbandonmentLink objects. Return only the JSON array."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions with composition targets.

Composition targets available:
agentcity.lewin, agentcity.cognitive_reappraisal, agentcity.goleman_ei,
agentcity.devils_advocate, agentcity.bias_stack, agentcity.johari,
agentcity.smart_goal, agentcity.plus_delta, agentcity.schein_culture,
agentcity.mcgregor, agentcity.hexaco, agentcity.grant_strengths

Dominant trap: {dominant_trap}
Motivation quality: {motivation_quality}
Profile pattern: {profile_pattern}
Task class: {task_class}
Weiner attribution: {weiner_audit}
Abandonment chain: {abandonment_chain}
Trap evidence: {evidence}

Return a JSON ARRAY of MotivationIntervention objects ranked highest impact first.
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
TRAPS_PROMPT = STANDARD_TRAPS_PROMPT
INTERVENTIONS_PROMPT = STANDARD_INTERVENTIONS_PROMPT


__all__ = [
    "FORENSIC_ABANDONMENT_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_WEINER_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "SAXBERG_SYSTEM_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "STANDARD_TRAPS_PROMPT",
    "TRAPS_PROMPT",
    "assemble_prompt",
]
