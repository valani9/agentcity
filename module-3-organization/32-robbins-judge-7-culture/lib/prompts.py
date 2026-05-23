"""LLM prompts for the Robbins & Judge 7-Characteristics Culture Diagnostic.

v0.2.0 prompts:
  - PROFILE_PROMPT (legacy) and QUICK_PROFILE_PROMPT (mode=quick)
  - FORENSIC_PROVENANCE_PROMPT, FORENSIC_RISK_PROMPT, FORENSIC_INTERVENTIONS_PROMPT
  - INTERVENTIONS_PROMPT (legacy + standard mode)
  - assemble_prompt(): fence + sanitize evidence using agentcity.aar helpers
"""

from __future__ import annotations

from agentcity.aar import fence, sanitize_for_prompt

ROBBINS_SYSTEM_PROMPT = """You are a culture-profile diagnostic working in the tradition
of Stephen P. Robbins and Timothy A. Judge, "Organizational Behavior" (Pearson, 17th ed.,
2017). The Robbins/Judge model decomposes organizational culture into seven independent
dimensions:

  - INNOVATION          - tolerance for risk and novel approaches
  - ATTENTION_TO_DETAIL - precision, analysis, attention to specifics
  - OUTCOME             - emphasis on results vs process
  - PEOPLE              - consideration for effects on team/stakeholders
  - TEAM                - work organized around teams vs individuals
  - AGGRESSIVENESS      - competitiveness vs easy-going
  - STABILITY           - status-quo vs growth/dynamism

Each dimension is INDEPENDENT - a culture can be high-innovation high-detail (research
lab) or low-innovation high-detail (regulated finance) or high-innovation low-detail
(early-stage startup). There is no universally "correct" profile; the right profile
depends on the task class.

You will be given an agent trace plus a TASK CLASS. For each of the seven dimensions,
you score:
  - observed_score (float 0-1): how strongly this dimension shows up in the agent's
    behavior (based on system prompt + observed behaviors + outcome)
  - target_score (float 0-1): what the dimension SHOULD score for this task class
  - fit_score (float 0-1): 1 - abs(observed - target). Indicates whether the
    agent's behavior is fit for purpose on this dimension.
  - explanation (1-3 sentences citing specific evidence)
  - evidence_quotes (specific excerpts; can be empty)

Target profiles by task class (rough heuristics -- adjust based on specifics):

  - research_exploration: high innovation, moderate detail, low aggressiveness,
                          low stability, moderate people, low-medium outcome,
                          moderate team
  - creative_generation:  high innovation, low-medium detail, low aggressiveness,
                          low stability
  - regulated_workflow:   low innovation, very high detail, low aggressiveness,
                          high stability, high outcome
  - financial_operation:  low innovation, very high detail, low aggressiveness,
                          high stability, very high outcome
  - customer_support:     low-medium innovation, high detail, high people,
                          moderate stability
  - code_review:          medium innovation, very high detail, medium people,
                          moderate aggressiveness (need to push back)
  - incident_response:    medium innovation, high detail, medium aggressiveness,
                          low stability (must adapt quickly), high outcome
  - general_purpose:      balanced (~0.5 on each)

Your posture is:
- EVIDENCE-GROUNDED. Cite specific trace steps + system-prompt fragments.
- TASK-CLASS-AWARE. The same observed behavior is fit for some task classes and
  unfit for others.
- INTERVENTION-FOCUSED. Connect each gap to a concrete fix.
- TERSE. Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


PROFILE_PROMPT = """Score each of the seven culture characteristics for the agent below.

Task: {task}
Task class (target profile driver): {task_class}
Subject model: {model_name}
Outcome: {outcome}
Success: {success}

System prompt (espoused-values source):
{system_prompt}

Observed behaviors:
{observed_behaviors}

Return a single JSON OBJECT with these fields:
  - characteristics: array of exactly 7 CharacteristicScore objects in the order:
      1. innovation
      2. attention_to_detail
      3. outcome
      4. people
      5. team
      6. aggressiveness
      7. stability
    Each has: characteristic, observed_score (float 0-1), target_score (float 0-1),
    fit_score (float 0-1), explanation (str), evidence_quotes (list of str),
    confidence (float 0-1), risk (one of "low", "medium", "high")
  - overall_fit: float 0-1 (mean of the seven fit_scores)
  - fit_quality: one of "well-fit", "partial-fit", "misfit"
  - biggest_gap: which characteristic has the LARGEST gap between observed and
    target (or "none" if no gap is significant)

Return only the JSON object."""


QUICK_PROFILE_PROMPT = """Quick-mode 7-Characteristics profile: produce profile +
one top intervention in a single response.

Task: {task}
Task class: {task_class}
Subject model: {model_name}
Outcome: {outcome}
Success: {success}

System prompt: {system_prompt}

Observed behaviors:
{observed_behaviors}

Return a single JSON OBJECT with:
  - characteristics: 7 CharacteristicScore objects (same shape as standard)
  - overall_fit: float
  - fit_quality: "well-fit" | "partial-fit" | "misfit"
  - biggest_gap: dimension name or "none"
  - top_intervention: one CultureIntervention object, OR null if well-fit

Return only the JSON object."""


INTERVENTIONS_PROMPT = """Given the culture profile evidence below, propose 2-4 concrete
interventions to close the biggest gap.

Each intervention must have:
  - target_characteristic (one of the 7 characteristics)
  - direction: "increase" or "decrease"
  - intervention_type: one of
      "rewrite_system_prompt"   - rewrite the prompt to shift the characteristic
      "adjust_temperature"      - higher temp = more innovation, less stability
      "add_guardrail"           - add a hard constraint when the dimension is
                                   over-amplified
      "swap_model"              - the base model's defaults don't match; pick
                                   a different one
      "add_team_scaffold"       - increase 'team' dimension by adding a
                                   multi-agent layer
      "remove_solo_path"        - prevent the agent from acting alone on
                                   irreversible operations
      "add_kill_criterion"      - bound stability / aggressiveness by hard limit
      "new_eval"                - regression test
      "human_review"            - human checkpoint
      "compose_pattern"         - hand off to another agentcity pattern
  - description (what the intervention does)
  - suggested_implementation (concrete code, prompt-text, or spec)
  - estimated_impact ("high", "medium", "low")
  - rationale (why this works -- connect to the dominant gap)
  - effort_estimate (one of "1h", "1d", "1w", "1m", "ongoing")
  - risk (one of "low", "medium", "high")

Task class: {task_class}
Fit quality: {fit_quality}
Biggest gap: {biggest_gap}
All characteristic evidence:
{evidence}

Return a JSON array of CultureIntervention objects. Return only the JSON array."""


FORENSIC_PROVENANCE_PROMPT = """Forensic-mode: explain where the target profile for
this task class came from. Was it the canonical task_class default, or did the trace
suggest local overrides (e.g. a regulated_workflow that nevertheless requires high
innovation)?

Task class: {task_class}
System prompt: {system_prompt}
Observed behaviors:
{observed_behaviors}

Return a single JSON OBJECT with:
  - derived_from: one of "task_class_default", "trace_evidence", "blended"
  - rationale (1-2 sentences)
  - per_dim_overrides: a dict of {{dimension_name: target_score}} for any
    dimension where the trace evidence implies a different target than the
    task_class default (empty dict if no overrides)

Return only the JSON object."""


FORENSIC_RISK_PROMPT = """Forensic-mode: rank the failure consequence of getting each
of the seven dimensions wrong for this task class. For example, in financial_operation,
getting attention_to_detail wrong is high-risk (financial errors); getting innovation
wrong is low-risk (rigidity is acceptable). In research_exploration, the opposite.

Task class: {task_class}
Outcome: {outcome}
Success: {success}
Observed behaviors:
{observed_behaviors}

Return a single JSON OBJECT with:
  - highest_risk_dimension: one of the 7 characteristic names, or "none"
  - risk_explanation (1-3 sentences)
  - per_dim_risk: dict of {{dimension_name: "low" | "medium" | "high"}} for all 7

Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """Forensic-mode interventions. Use the per-dim risk
ranking + target-profile provenance to propose 3-6 interventions, prioritised by
(risk x gap-size). Each intervention closes the biggest aligned-risk gap.

Task class: {task_class}
Fit quality: {fit_quality}
Biggest gap: {biggest_gap}
Provenance: {provenance}
Per-dimension risk: {per_dim_risk}
All characteristic evidence:
{evidence}

Same intervention schema as INTERVENTIONS_PROMPT. Return only the JSON array."""


def assemble_prompt(
    template: str,
    /,
    *,
    system_prompt: str = "",
    observed_behaviors: list[str] | None = None,
    inferred_assumptions: list[str] | None = None,
    **kwargs: object,
) -> str:
    """Fence + sanitize untrusted fields, then fill the template."""
    safe_prompt = fence("system_prompt", sanitize_for_prompt(system_prompt or "(none)"))
    behaviors = observed_behaviors or []
    if behaviors:
        behaviors_text = "\n".join(f"- {sanitize_for_prompt(b)}" for b in behaviors)
    else:
        behaviors_text = "(none)"
    safe_behaviors = fence("observed_behaviors", behaviors_text)
    fields: dict[str, object] = {
        "system_prompt": safe_prompt,
        "observed_behaviors": safe_behaviors,
    }
    if inferred_assumptions is not None:
        if inferred_assumptions:
            ass_text = "\n".join(f"- {sanitize_for_prompt(a)}" for a in inferred_assumptions)
        else:
            ass_text = "(none)"
        fields["inferred_assumptions"] = fence("inferred_assumptions", ass_text)
    fields.update(kwargs)
    return template.format(**fields)


__all__ = [
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_PROVENANCE_PROMPT",
    "FORENSIC_RISK_PROMPT",
    "INTERVENTIONS_PROMPT",
    "PROFILE_PROMPT",
    "QUICK_PROFILE_PROMPT",
    "ROBBINS_SYSTEM_PROMPT",
    "assemble_prompt",
]
