"""LLM prompt templates for the Vroom Expectancy Diagnostic.

Three modes (quick / standard / forensic) with shared system prompt
naming 7+ literature anchors.
"""

from __future__ import annotations

from typing import Any

from vstack.aar import fence, sanitize_for_prompt


VROOM_SYSTEM_PROMPT = """You are an expectancy-motivation diagnostic grounded in:

1. **Vroom (1964)** *Work and Motivation* -- canonical Expectancy-Instrumentality-Valence.
2. **Porter & Lawler (1968)** *Managerial Attitudes and Performance* -- extension to performance + reward.
3. **Bandura (1977)** Self-Efficacy -- expectancy formalization.
4. **Eccles & Wigfield (2002)** Motivational Beliefs, Values, and Goals.
5. **Locke & Latham (1990)** A Theory of Goal Setting -- specificity x expectancy.
6. **Kanfer, Frese, Johnson (2017)** Motivation Related to Work review.
7. **Casper et al. (2023)** RLHF reward hacking -- modern LLM I-V alignment anchor.

The multiplicative motivation model:

  MOTIVATION = EXPECTANCY * INSTRUMENTALITY * VALENCE

  - EXPECTANCY    (E) -- [0, 1] -- "Do I think I CAN do this?"
  - INSTRUMENTALITY (I) -- [0, 1] -- "If I do it well, will it MATTER?"
  - VALENCE       (V) -- [-1, 1] -- "Is the outcome WORTH it?"

**Multiplicative collapse:** if any term approaches zero, motivation collapses.
The diagnostic identifies WHICH term is the bottleneck. The intervention must
lift that specific term -- not all three.

For each term score:
- score (E/I in [0,1]; V in [-1,1])
- explanation
- evidence_quotes
- confidence (0-1)

Also identify:
- bottleneck_term (the term closest to zero / most blocking)
- motivation_quality: motivated (>0.4) / weak (>0.05) / collapsed (<=0.05 or negative)

Note: motivation_score is computed deterministically by the runtime as E*I*V.

Your posture:
- **Multiplicative-aware.**
- **Evidence-grounded.**
- **Intervention-focused.**
- **Terse.**

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 3 EIV terms + bottleneck + top intervention.

Task: {task}
Task class: {task_class}
Subject model: {model_name}
System prompt: {system_prompt}
Observed behaviors: {observed_behaviors}
Effort signals: {effort_signals}
Declared reward: {declared_reward}
Outcome: {outcome}
Success: {success}

Return a JSON object:
{{
  "terms": [
    {{ "term": "expectancy", "score": 0-1, "explanation": "...", "evidence_quotes": [], "confidence": 0-1 }},
    {{ "term": "instrumentality", "score": 0-1, ... }},
    {{ "term": "valence", "score": -1-1, ... }}
  ],
  "bottleneck_term": "expectancy|instrumentality|valence|none",
  "motivation_quality": "motivated|weak|collapsed",
  "top_intervention": {{
    "target_term": "<term>",
    "intervention_type": "...",
    "description": "...",
    "suggested_implementation": "...",
    "estimated_impact": "high|medium|low",
    "rationale": "..."
  }}
}}

Return only the JSON object."""


STANDARD_TERMS_PROMPT = """STANDARD mode -- score the three EIV terms.

Task: {task}
Task class: {task_class}
Subject model: {model_name}
System prompt: {system_prompt}
Observed behaviors: {observed_behaviors}
Effort signals: {effort_signals}
Declared reward: {declared_reward}
Outcome: {outcome}
Success: {success}

Return a JSON OBJECT:
- terms: array of exactly 3 VroomTermScore objects (expectancy, instrumentality, valence)
- bottleneck_term: expectancy | instrumentality | valence | none
- motivation_quality: motivated | weak | collapsed

Return only the JSON object."""


STANDARD_INTERVENTIONS_PROMPT = """STANDARD mode -- propose 2-4 ranked interventions to lift the bottleneck.

Term-to-intervention mapping:

EXPECTANCY:    scaffold_subtasks, add_worked_example, lower_difficulty_step,
               show_capability_proof, tighten_goal_specificity
INSTRUMENTALITY: show_output_consumer, add_outcome_link, add_progress_signal,
                 remove_pointless_signal
VALENCE:       add_purpose_framing, rebalance_value_alignment, remove_anti_value_signal
Generic:       rewrite_system_prompt, swap_model, new_eval, human_review,
               compose_pattern, add_motivation_eval

Each intervention must have:
- target_term (one of the 3)
- intervention_type (from above)
- description, suggested_implementation
- estimated_impact, effort_estimate, risk, reversibility
- rationale

Bottleneck: {bottleneck_term}
Motivation quality: {motivation_quality}
Task class: {task_class}
All term evidence: {evidence}

Return a JSON array of VroomIntervention objects. Return only the JSON array."""


FORENSIC_PROMPT_SIGNAL_PROMPT = """FORENSIC mode -- decompose the system prompt into signals.

For each detected signal, identify:
- category: capability_proof | scaffolding | worked_example | outcome_link |
            purpose_framing | user_connection | pointless_signal |
            anti_value_signal | expectancy_threat | instrumentality_threat |
            valence_threat | neutral
- source_quote (the literal text)
- affected_term: expectancy | instrumentality | valence | none
- polarity: lifts | lowers | neutral
- explanation

System prompt: {system_prompt}
Effort signals: {effort_signals}

Return a JSON ARRAY of PromptSignalItem objects. Return only the JSON array."""


FORENSIC_EIV_INTERACTION_PROMPT = """FORENSIC mode -- audit the EIV interaction structure.

Given the three term scores, identify:
- dominant_interaction: E_dominates | I_dominates | V_dominates |
  E_x_I_low | E_x_V_low | I_x_V_low | balanced | unknown
- multiplicative_collapse_term: the single term whose 0-approach causes the collapse
- notes

Term evidence: {evidence}

Return a JSON OBJECT representing the EIVInteractionAudit. Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions with composition targets.

Composition targets available:
vstack.lewin, vstack.aar, vstack.cognitive_reappraisal, vstack.goleman_ei,
vstack.devils_advocate, vstack.bias_stack, vstack.johari,
vstack.smart_goal, vstack.plus_delta, vstack.schein_culture,
vstack.mcgregor, vstack.hexaco, vstack.grant_strengths,
vstack.motivation_traps, vstack.sdt_reward

Bottleneck: {bottleneck_term}
Motivation quality: {motivation_quality}
Profile pattern: {profile_pattern}
Task class: {task_class}
Prompt signals: {prompt_signals}
EIV interaction audit: {eiv_audit}
Term evidence: {evidence}

Return a JSON ARRAY of VroomIntervention objects ranked highest impact first.
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
TERMS_PROMPT = STANDARD_TERMS_PROMPT
INTERVENTIONS_PROMPT = STANDARD_INTERVENTIONS_PROMPT


__all__ = [
    "FORENSIC_EIV_INTERACTION_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_PROMPT_SIGNAL_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "STANDARD_TERMS_PROMPT",
    "TERMS_PROMPT",
    "VROOM_SYSTEM_PROMPT",
    "assemble_prompt",
]
