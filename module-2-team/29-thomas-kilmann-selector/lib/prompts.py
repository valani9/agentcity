"""LLM prompts for the Thomas-Kilmann Conflict Style Selector."""

from __future__ import annotations

from typing import Any

from vstack.aar import fence, sanitize_for_prompt


TK_SYSTEM_PROMPT = """You are a Thomas-Kilmann (1974) conflict-style diagnostician for
AI agents.

Five styles plotted on assertiveness x cooperativeness axes:
  - COMPETING       (high assertive, low cooperative)
  - ACCOMMODATING   (low assertive, high cooperative)
  - AVOIDING        (low assertive, low cooperative)
  - COMPROMISING    (medium both)
  - COLLABORATING   (high assertive, high cooperative)

Each style is optimal for a different task category. Identify (1) which style
the agent USED, (2) which would be OPTIMAL for the task, and (3) what to
change.

Posture: EVIDENCE-GROUNDED, STYLE-SPECIFIC, CONTEXT-AWARE, TERSE.
When asked for JSON, return JSON only."""


# Legacy v0.0.x prompts.
TK_ANALYSIS_PROMPT = """Analyze the agent's conflict style in this interaction.

Task: {task}
Outcome: {outcome}
Success: {success}
Subject model: {model_name}
Task category hint: {task_category}

Trace:
{trace}

Return a single JSON OBJECT with:
  - observed_style (one of competing/accommodating/avoiding/compromising/collaborating/mixed)
  - optimal_style (one of the 5 styles)
  - style_mismatch (float 0-1)
  - assertiveness_score (float 0-1)
  - cooperativeness_score (float 0-1)
  - observed_style_scores (dict of 5 style->score)
  - style_evidence (array of 5 StyleScore objects)
  - rationale (string)

Return only the JSON object."""


RECOMMENDATIONS_PROMPT = """Given the style analysis below, propose 2-4 recommendations
to align observed style with optimal style.

Each recommendation has intervention_type, description, suggested_implementation,
estimated_impact, rationale.

intervention_type one of: prompt_patch, scaffold_change, style_router,
context_classifier, task_specific_persona, calibrate_assertiveness,
calibrate_cooperativeness, new_eval, human_review, compose_pattern.

Observed style: {observed_style}
Optimal style: {optimal_style}
Style mismatch: {style_mismatch}
Trace (reference):
{trace}

Return only a JSON array of StyleRecommendation objects."""


# v0.2.0 prompts.
QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- minimal Thomas-Kilmann analysis.

Task: {task}
Outcome: {outcome}
Trace: {trace}

Return a JSON object with: observed_style, optimal_style, style_mismatch,
assertiveness_score, cooperativeness_score, observed_style_scores,
style_evidence, rationale, top_recommendation.
Return only the JSON object."""


STANDARD_TK_ANALYSIS_PROMPT = TK_ANALYSIS_PROMPT
STANDARD_RECOMMENDATIONS_PROMPT = RECOMMENDATIONS_PROMPT


FORENSIC_STYLE_FIT_PROMPT = """FORENSIC mode -- style-fit audit.

Infer task_category and optimal_style; estimate fit (0-1) and cost-of-mismatch (0-1).

Task: {task}
Outcome: {outcome}
Trace: {trace}

Return only a JSON object representing the StyleFitAudit."""


FORENSIC_CONSISTENCY_PROMPT = """FORENSIC mode -- pattern consistency audit.

Identify early-trace dominant style vs late-trace dominant style; count style flips;
estimate consistency (0-1).

Trace: {trace}

Return only a JSON object representing the PatternConsistencyAudit."""


FORENSIC_RECOMMENDATIONS_PROMPT = """FORENSIC mode -- propose 3-6 recommendations.

Composition targets: vstack.glaser_conversation, vstack.aar,
vstack.devils_advocate, vstack.mcallister_trust

Observed style: {observed_style}
Optimal style: {optimal_style}
Style fit audit: {style_fit_audit}
Pattern consistency audit: {pattern_consistency_audit}

Return only a JSON array of StyleRecommendation objects."""


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
    "FORENSIC_CONSISTENCY_PROMPT",
    "FORENSIC_RECOMMENDATIONS_PROMPT",
    "FORENSIC_STYLE_FIT_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "RECOMMENDATIONS_PROMPT",
    "STANDARD_RECOMMENDATIONS_PROMPT",
    "STANDARD_TK_ANALYSIS_PROMPT",
    "TK_ANALYSIS_PROMPT",
    "TK_SYSTEM_PROMPT",
    "assemble_prompt",
]
