"""LLM prompt templates for the Yerkes-Dodson Workload Diagnostic.

Three modes (quick / standard / forensic) with shared system prompt
naming 7+ literature anchors.
"""

from __future__ import annotations

from typing import Any

from agentcity.aar import fence, sanitize_for_prompt


YERKES_DODSON_SYSTEM_PROMPT = """You are a workload-pressure diagnostic grounded in:

1. **Yerkes & Dodson (1908)** -- the original inverted-U arousal-performance curve.
2. **Sweller (1988, 1994, 2011)** Cognitive Load Theory -- three components: intrinsic (task-inherent), extraneous (presentation-induced), germane (productive learning).
3. **Kahneman (1973)** *Attention and Effort* -- capacity model: attention is a limited resource that depletes under load.
4. **Hancock & Warm (1989)** -- dynamic adaptability framework.
5. **Eysenck-Calvo (1992)** Attentional Control Theory -- anxiety reduces processing efficiency before effectiveness.
6. **Hebb (1955)** -- arousal as physiological precursor of performance.
7. **Liu et al. (2024)** lost-in-the-middle -- LLM context-saturation finding.

Your posture:
- **Zone-aware.** under_pressure (wandering/drift), optimal (focused), over_pressure (corner-cutting/freezing/hallucinating/refusing).
- **Task-complexity sensitive.** Complex tasks peak at LOWER pressure.
- **CLT-aware.** Distinguish intrinsic / extraneous / germane load.
- **Context-saturation aware.** context/window > 0.7 -> lost-in-the-middle risk.
- **Calibrated.** Score 0.0 when a zone is absent.
- **Terse.** Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


QUICK_DIAGNOSTIC_PROMPT = """Score 3 workload zones + propose 1 top intervention. QUICK mode.

Task: {task}
Pressure inputs: {pressure}
Observed behaviors: {observed_behaviors}
Outcome: {outcome}
Success: {success}

Return a JSON object:
{{
  "zone_evidence": [
    {{ "zone": "under_pressure", "score": 0-1, "explanation": "...", "evidence_quotes": [], "confidence": 0-1 }},
    {{ "zone": "optimal", ... }},
    {{ "zone": "over_pressure", ... }}
  ],
  "observed_zone": "under_pressure|optimal|over_pressure",
  "distance_from_optimal": 0-1,
  "failure_mode": "wandering|focused|corner_cutting|freezing|hallucinating|refusing|unknown",
  "top_intervention": {{
    "intervention_type": "...",
    "direction": "increase_pressure|decrease_pressure",
    "description": "...",
    "suggested_implementation": "...",
    "estimated_impact": "high|medium|low",
    "rationale": "..."
  }}
}}

Return only the JSON object."""


STANDARD_WORKLOAD_PROMPT = """Score 3 workload zones + identify failure mode + propose interventions.

For each zone, return:
  - zone (under_pressure | optimal | over_pressure)
  - score (0.0-1.0)
  - explanation
  - evidence_quotes
  - confidence (0.0-1.0)

Identify:
  - observed_zone
  - distance_from_optimal (0.0-1.0)
  - failure_mode (wandering | focused | corner_cutting | freezing | hallucinating | refusing | unknown)

Propose 2-4 ranked interventions:
  - intervention_type: one of "tighten_deadline", "add_budget_cap", "loosen_deadline", "loosen_budget", "add_kill_criterion", "raise_retry_cap", "lower_retry_cap", "explicit_focus_prompt", "human_review", "new_eval", "reduce_extraneous_load", "chunk_context", "add_scaffolding", "remove_irrelevant_context", "add_intrinsic_load_step_by_step", "promote_germane_load", "context_compression", "compose_pattern"
  - direction: increase_pressure | decrease_pressure
  - description, suggested_implementation
  - estimated_impact, effort_estimate, risk, reversibility
  - rationale

Task: {task}
Pressure inputs: {pressure}
Observed behaviors: {observed_behaviors}
Outcome: {outcome}
Success: {success}

Return a JSON object with zone_evidence + observed_zone + distance_from_optimal + failure_mode + interventions. Return only the JSON object."""


FORENSIC_COGNITIVE_LOAD_PROMPT = """FORENSIC mode -- Sweller CLT three-component decomposition.

Task: {task}
Pressure inputs: {pressure}
Context size: {context_size_tokens} tokens (window: {context_window_size})
Observed behaviors: {observed_behaviors}

Return a JSON object:
{{
  "intrinsic_load": 0-1,
  "extraneous_load": 0-1,
  "germane_load": 0-1,
  "total_load": 0-1,
  "dominant_component": "intrinsic|extraneous|germane",
  "notes": "..."
}}

Return only the JSON object."""


FORENSIC_CONTEXT_SATURATION_PROMPT = """FORENSIC mode -- context saturation analysis.

context_size_tokens: {context_size_tokens}
context_window_size: {context_window_size}
Observed behaviors: {observed_behaviors}

Return a JSON object:
{{
  "saturation_ratio": 0-1,
  "lost_in_middle_risk": "low|moderate|high",
  "estimated_useful_tokens": int,
  "estimated_noise_tokens": int,
  "notes": "..."
}}

Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions with composition targets.

Composition targets available:
  agentcity.smart_goal, agentcity.cognitive_reappraisal, agentcity.devils_advocate,
  agentcity.lewin, agentcity.aar, agentcity.johari, agentcity.bias_stack,
  agentcity.mcgregor, agentcity.schein_culture, agentcity.plus_delta

Observed zone: {observed_zone}
Failure mode: {failure_mode}
Profile pattern: {profile_pattern}
Cognitive load analysis: {cognitive_load}
Context saturation: {context_saturation}
Zone evidence: {zone_evidence}

Return a JSON array, ranked highest impact first. Return only the JSON array."""


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


WORKLOAD_PROMPT = STANDARD_WORKLOAD_PROMPT  # legacy alias


__all__ = [
    "FORENSIC_CONTEXT_SATURATION_PROMPT",
    "FORENSIC_COGNITIVE_LOAD_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_WORKLOAD_PROMPT",
    "WORKLOAD_PROMPT",
    "YERKES_DODSON_SYSTEM_PROMPT",
    "assemble_prompt",
]
