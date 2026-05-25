"""LLM prompts for the Plus/Delta Inter-Agent Feedback Format generator."""

from __future__ import annotations

from typing import Any

from vstack.aar import fence, sanitize_for_prompt


PLUS_DELTA_SYSTEM_PROMPT = """You are a structured-feedback generator working in the
tradition of the plus/delta format (Joiner Associates 1990s; Brown "Dare to Lead" 2018;
retrospective-meeting literature).

Plus/delta has one ironclad rule:
  - PLUS  - what worked, BEHAVIORAL, SPECIFIC, REUSABLE next time.
  - DELTA - what to do differently next time. BEHAVIORAL, SPECIFIC, names the ALTERNATIVE.

Generic affirmations and generic critiques are noise. Every item must be evidence-grounded
and forward-looking.

Posture: BEHAVIORAL, EVIDENCE-GROUNDED, FORWARD-LOOKING, BALANCED, TERSE.
When asked for JSON, return JSON only."""


# Legacy v0.0.x prompt (preserved).
PLUS_DELTA_PROMPT = """Generate a structured plus/delta feedback artifact for the
contribution below.

Reviewer agent: {reviewer_agent}
Subject agent: {subject_agent}
Task context: {task_context}
Contribution summary: {contribution_summary}

Success criteria:
{success_criteria}

Style preference: {style}
Max items per category: {max_items}

Contribution artifact:
---
{contribution_artifact}
---

Return a single JSON OBJECT with:
  - plus_items: array (1 to {max_items}). Each: statement, evidence, impact, keep_doing.
  - delta_items: array (0 to {max_items}). Each: statement, evidence, impact, alternative,
    severity (nit/moderate/critical).
  - commitments: optional array. Each: by_agent, commitment.
  - overall_assessment: one of "keep-going", "iterate", "rework".
  - feedback_quality_score: float 0-1.

Behavioral specificity rules: no generic affirmations; no generic critiques; every item
must cite specific evidence from the artifact.

Return only the JSON object."""


# v0.2.0 prompts.
QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- produce a minimal plus/delta artifact.

Reviewer: {reviewer_agent} -> Subject: {subject_agent}
Task: {task_context}
Contribution summary: {contribution_summary}
Style: {style}
Max items: {max_items}

Contribution: {contribution_artifact}

Return a single JSON object with plus_items (1-2), delta_items (0-2), overall_assessment,
feedback_quality_score.
Return only the JSON object."""


STANDARD_PLUS_DELTA_PROMPT = PLUS_DELTA_PROMPT


FORENSIC_SPECIFICITY_PROMPT = """FORENSIC mode -- audit specificity of an existing plus/delta artifact.

Count specific vs generic plus and delta items; estimate specificity (0-1, higher = more
behavioral).

Artifact:
{artifact}

Return only a JSON object representing the SpecificityAudit."""


FORENSIC_BEHAVIORAL_PROMPT = """FORENSIC mode -- audit behavioral vs generic phrasing.

Count behavioral items vs generic items; list detected generic phrases ("good work",
"could be better", "well done", "needs improvement", etc.); estimate behavioral
(0-1, higher = more behavioral).

Artifact:
{artifact}

Return only a JSON object representing the BehavioralVsGenericAudit."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 3-6 quality-improvement
interventions for a plus/delta artifact.

Composition targets: vstack.aar, vstack.smart_goal, vstack.glaser_conversation,
vstack.feedback_triggers

Artifact:
{artifact}
Specificity audit: {specificity_audit}
Behavioral audit: {behavioral_audit}

intervention_type one of: tighten_specificity, require_evidence, require_alternative,
balance_style, escalate_severity, deescalate_severity, add_commitment, new_eval,
human_review, compose_pattern.

target_dimension one of: plus, delta, overall, specificity.

Return only a JSON array of PlusDeltaIntervention objects."""


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
    "FORENSIC_BEHAVIORAL_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_SPECIFICITY_PROMPT",
    "PLUS_DELTA_PROMPT",
    "PLUS_DELTA_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_PLUS_DELTA_PROMPT",
    "assemble_prompt",
]
