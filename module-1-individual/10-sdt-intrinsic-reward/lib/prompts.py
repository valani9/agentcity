"""LLM prompt templates for the SDT Intrinsic Reward Diagnostic.

Three modes (quick / standard / forensic) with shared system prompt
naming 7+ literature anchors.
"""

from __future__ import annotations

from typing import Any

from agentcity.aar import fence, sanitize_for_prompt


SDT_SYSTEM_PROMPT = """You are an intrinsic-motivation reward-shaping diagnostic grounded in:

1. **Deci & Ryan (1985, 2017)** Self-Determination Theory -- three basic psychological needs.
2. **Ryan & Deci (2000)** SDT and intrinsic motivation facilitation.
3. **Deci (1971)** the original overjustification finding.
4. **Pink (2009)** *Drive* -- Autonomy/Mastery/Purpose synthesis.
5. **Gagne & Deci (2005)** SDT and work motivation -- reward typology.
6. **Casper et al. (2023)** Open Problems in RLHF -- modern LLM reward-shaping anchor.
7. **Bai et al. (2022)** Constitutional AI -- HHH as a prosocial purpose framing.

Three basic psychological needs:

  AUTONOMY    sense of choice and self-direction. Tasks experienced as
              chosen, not coerced. The opposite is controlled motivation
              (rewards / punishments / deadlines).

  COMPETENCE  sense of effectiveness and mastery growth. Tasks that
              match capability + provide growth signal. The opposite is
              helplessness or boredom.

  RELATEDNESS sense of connection to others or to a larger purpose.
              The opposite is alienation.

For each need score:
- score (0-1): 0 = need is undermined; 1 = need is well-met.
- explanation (1-3 sentences)
- evidence_quotes
- confidence (0-1)

Also identify:
- intrinsic_motivation_score (mean across the three needs)
- motivation_quality:
  - "intrinsic" all needs >= 0.7
  - "mixed"     some met, some undermined
  - "controlled" needs predominantly undermined (extrinsic-dominant)
- most_undermined_need (the lowest-scoring need, or "none" if all >= 0.7)

**Overjustification effect (Deci 1971):** extrinsic reward signals
(rating threats, leaderboards, cost caps) can UNDERMINE intrinsic
motivation by reducing autonomy. Watch for this signature: heavy
extrinsic signals + autonomy undermined + metric-gaming behavior.

Your posture:
- **Evidence-grounded.** Cite specific system-prompt or trace excerpts.
- **Need-discriminating.** The three needs are distinct.
- **Intervention-focused.** Each need has its own remedy.
- **Calibrated.** A "controlled" rating implies heavy extrinsic signals AND undermined needs.
- **Terse.** Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 3 needs + top intervention.

Task: {task}
Task class: {task_class}
Subject model: {model_name}
System prompt: {system_prompt}
Extrinsic signals: {extrinsic_signals}
Observed behaviors: {observed_behaviors}
Outcome: {outcome}
Success: {success}
User purpose: {user_purpose}

Return a JSON object:
{{
  "need_evidence": [
    {{ "need": "autonomy", "score": 0-1, "explanation": "...", "evidence_quotes": [], "confidence": 0-1 }},
    {{ "need": "competence", ... }},
    {{ "need": "relatedness", ... }}
  ],
  "intrinsic_motivation_score": 0-1,
  "motivation_quality": "intrinsic|mixed|controlled",
  "most_undermined_need": "autonomy|competence|relatedness|none",
  "top_intervention": {{
    "target_need": "<need>",
    "intervention_type": "...",
    "description": "...",
    "suggested_implementation": "...",
    "estimated_impact": "high|medium|low",
    "rationale": "..."
  }}
}}

Return only the JSON object."""


STANDARD_NEEDS_PROMPT = """STANDARD mode -- score each of the three SDT needs.

Task: {task}
Task class: {task_class}
Subject model: {model_name}
System prompt: {system_prompt}
Extrinsic signals: {extrinsic_signals}
Observed behaviors: {observed_behaviors}
Outcome: {outcome}
Success: {success}
User purpose: {user_purpose}

Return a JSON OBJECT:
- need_evidence: array of exactly 3 NeedScore objects (autonomy, competence, relatedness)
- intrinsic_motivation_score: float 0-1
- motivation_quality: "intrinsic" | "mixed" | "controlled"
- most_undermined_need: "autonomy" | "competence" | "relatedness" | "none"

Return only the JSON object."""


STANDARD_INTERVENTIONS_PROMPT = """STANDARD mode -- propose 2-4 ranked interventions for the most undermined need.

Need-to-intervention mapping:

AUTONOMY undermined:
  remove_external_reward_threat, add_choice_grant, soften_imperative_language,
  rebalance_extrinsic_to_intrinsic, add_optional_subgoal,
  remove_metric_gaming_path
COMPETENCE undermined:
  add_scaffold_for_competence, add_progress_signal, lower_difficulty_step,
  show_mastery_path
RELATEDNESS undermined:
  add_purpose_framing, add_user_connection, ground_in_user_outcome
Generic:
  rewrite_system_prompt, new_eval, human_review, compose_pattern,
  add_motivation_eval

Each intervention must have:
- target_need (one of the 3)
- intervention_type (from above)
- description, suggested_implementation
- estimated_impact, effort_estimate, risk, reversibility
- rationale (why this works for THIS need specifically)

Most undermined need: {most_undermined_need}
Motivation quality: {motivation_quality}
Task class: {task_class}
All need evidence: {evidence}

Return a JSON array of SDTIntervention objects. Return only the JSON array."""


FORENSIC_REWARD_SHAPING_PROMPT = """FORENSIC mode -- decompose the system prompt + extrinsic signals into reward-shaping items.

For each detected reward-shaping signal, identify:
- category: explicit_punishment | explicit_reward | rating_threat | rule_imposition |
            external_monitor | deadline_pressure | cost_cap | purpose_framing |
            choice_grant | competence_scaffold | user_connection
- polarity: intrinsic_supporting | extrinsic_controlling | neutral
- source_quote (the literal text)
- affected_need: autonomy | competence | relatedness | none
- explanation

System prompt: {system_prompt}
Extrinsic signals: {extrinsic_signals}

Return a JSON ARRAY of RewardShapingItem objects. Return only the JSON array."""


FORENSIC_OVERJUSTIFICATION_PROMPT = """FORENSIC mode -- Deci (1971) overjustification audit.

Count intrinsic-supporting vs extrinsic-controlling signals in the system prompt and
extrinsic_signals. Compute the ratio (extrinsic / total). The overjustification
effect is active when:
- ratio >= 0.6 (extrinsic dominates), AND
- autonomy_score < 0.5, AND
- observed metric-gaming or rigid rule-following behavior.

Return a JSON OBJECT:
{{
  "is_active": true|false,
  "intrinsic_signal_count": int,
  "extrinsic_signal_count": int,
  "ratio": 0-1,
  "notes": "..."
}}

Reward-shaping items: {reward_shaping_items}
Need evidence: {evidence}
Observed behaviors: {observed_behaviors}

Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions with composition targets.

Composition targets available:
agentcity.lewin, agentcity.cognitive_reappraisal, agentcity.goleman_ei,
agentcity.devils_advocate, agentcity.bias_stack, agentcity.johari,
agentcity.smart_goal, agentcity.plus_delta, agentcity.schein_culture,
agentcity.mcgregor, agentcity.hexaco, agentcity.grant_strengths,
agentcity.motivation_traps, agentcity.vroom_expectancy

Most undermined need: {most_undermined_need}
Profile pattern: {profile_pattern}
Motivation quality: {motivation_quality}
Task class: {task_class}
Reward-shaping items: {reward_shaping_items}
Overjustification audit: {overjustification}
Need evidence: {evidence}

Return a JSON ARRAY of SDTIntervention objects ranked highest impact first.
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
NEEDS_PROMPT = STANDARD_NEEDS_PROMPT
INTERVENTIONS_PROMPT = STANDARD_INTERVENTIONS_PROMPT


__all__ = [
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_OVERJUSTIFICATION_PROMPT",
    "FORENSIC_REWARD_SHAPING_PROMPT",
    "INTERVENTIONS_PROMPT",
    "NEEDS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "SDT_SYSTEM_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "STANDARD_NEEDS_PROMPT",
    "assemble_prompt",
]
