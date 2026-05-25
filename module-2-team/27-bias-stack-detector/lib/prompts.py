"""LLM prompts for the Bias-Stack Detector."""

from __future__ import annotations

from typing import Any

from vstack.aar import fence, sanitize_for_prompt


BIAS_SYSTEM_PROMPT = """You are a cognitive-bias diagnostician for AI agents working in
the tradition of Kahneman & Tversky (1974, 1979, 2011).

Four canonical biases:
  - ANCHORING                - over-weight the first hypothesis / number
  - OVERCONFIDENCE           - confidence > calibration; doesn't seek disconfirmation
  - CONFIRMATION             - only seeks evidence that supports the hypothesis
  - ESCALATION-OF-COMMITMENT - doubles down rather than abandoning a failing approach

Posture: EVIDENCE-GROUNDED, BIAS-SPECIFIC, INTERVENTION-FOCUSED, TERSE.
When asked for JSON, return JSON only."""


# Legacy v0.0.x prompts.
BIAS_SCORING_PROMPT = """Score each of the four biases against this reasoning trace.

For each bias return: bias, score (0-1), severity (none/low/medium/high), explanation,
evidence_quotes.

Task: {task}
Outcome: {outcome}
Success: {success}
Subject model: {model_name}

Trace:
{trace}

Return only a JSON array of exactly 4 BiasEvidence objects in order:
  1. anchoring
  2. overconfidence
  3. confirmation
  4. escalation-of-commitment"""


INTERVENTIONS_PROMPT = """Given the bias analysis below, propose 2-4 interventions
targeting the dominant bias.

Each intervention has target_bias, intervention_type, description,
suggested_implementation, estimated_impact, rationale.

intervention_type one of: prompt_patch, scaffold_change, retry_cap,
uncertainty_calibration, first_principles_reset, devils_advocate_role,
search_disconfirming_evidence, anchor_to_base_rates, new_eval, human_review,
compose_pattern.

Dominant bias: {dominant}
Evidence:
{evidence}

Trace (reference):
{trace}

Return only a JSON array of BiasIntervention objects."""


# v0.2.0 prompts.
QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 4 biases + top intervention.

Task: {task}
Outcome: {outcome}
Trace: {trace}

Return a JSON object with keys: biases (array of 4), top_intervention.
Return only the JSON object."""


STANDARD_BIAS_SCORING_PROMPT = BIAS_SCORING_PROMPT
STANDARD_INTERVENTIONS_PROMPT = INTERVENTIONS_PROMPT


FORENSIC_CALIBRATION_PROMPT = """FORENSIC mode -- confidence calibration audit.

Compute mean self-reported confidence, gap between confidence and outcome
correctness, and overall calibration estimate (0-1).

Trace: {trace}
Outcome: {outcome}
Success: {success}

Return only a JSON object representing the ConfidenceCalibrationAudit."""


FORENSIC_ANCHORING_PROMPT = """FORENSIC mode -- anchoring trace audit.

Check whether the agent persisted with its first hypothesis: compute persistence
(0-1), pivot count, retry count, anchoring estimate (0-1).

Trace: {trace}

Return only a JSON object representing the AnchoringTraceAudit."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 interventions with
composition targets.

Composition targets: vstack.devils_advocate, vstack.aar, vstack.grpi,
vstack.debate_pathology

Dominant bias: {dominant}
Evidence: {evidence}
Calibration audit: {calibration_audit}
Anchoring audit: {anchoring_audit}

Return only a JSON array of BiasIntervention objects."""


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
    "BIAS_SCORING_PROMPT",
    "BIAS_SYSTEM_PROMPT",
    "FORENSIC_ANCHORING_PROMPT",
    "FORENSIC_CALIBRATION_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_BIAS_SCORING_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]
