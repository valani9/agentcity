"""LLM prompts for the Group Decision Models generator."""

from __future__ import annotations

from typing import Any

from vstack.aar import fence, sanitize_for_prompt


DECISION_SYSTEM_PROMPT = """You are a decision-protocol generator working in the
facilitator canon (Sam Kaner, "Facilitator's Guide to Participatory Decision-Making",
Jossey-Bass, 2014).

Five canonical decision-aggregation models:
  - CONCURRING    - single decisive vote
  - MAJORITY      - >50%
  - CONSENSUS     - all affirm or do not block
  - FIST_TO_FIVE  - graded 0-5; 0 blocks
  - UNANIMOUS     - all positively vote yes

Match the model to stakes, reversibility, time pressure, expertise asymmetry,
regulatory exposure, and buy-in needs.

Posture: HONEST about trade-offs, TERSE, KILL-AMBIGUITY-FIRST.
When asked for JSON, return JSON only."""


# Legacy v0.0.x prompt.
DECISION_PROTOCOL_PROMPT = """Generate a decision-aggregation protocol for the request below.

Decision title: {title}
Options:
{options}
Agents: {agents}
Stakes: {stakes}
Reversibility: {reversibility}
Time pressure: {time_pressure}
Expertise asymmetry: {expertise_asymmetry}
Regulatory exposure: {regulatory_exposure}
Buy-in required: {buy_in_required}
Forced model (if any): {forced_model}

Return a single JSON OBJECT with recommended_model (one of: concurring, majority,
consensus, fist_to_five, unanimous), rationale, protocol_steps, threshold, quorum
(int or null), tie_breaker, fallback_model (or null).

Return only the JSON object."""


# v0.2.0 prompts.
QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- minimal decision protocol.

Title: {title}
Stakes: {stakes}
Reversibility: {reversibility}
Buy-in required: {buy_in_required}

Return a JSON object with recommended_model, rationale, threshold, protocol_steps.
Return only the JSON object."""


STANDARD_DECISION_PROTOCOL_PROMPT = DECISION_PROTOCOL_PROMPT


FORENSIC_METHOD_FIT_PROMPT = """FORENSIC mode -- method-fit audit.

Judge whether the recommended model fits the decision properties on each axis
(stakes, reversibility, time_pressure, buy_in, regulatory). Estimate fit (0-1).

Protocol:
{protocol}
Request properties: {properties}

Return only a JSON object representing the MethodFitAudit."""


FORENSIC_TALLY_INTEGRITY_PROMPT = """FORENSIC mode -- tally integrity audit.

Check whether the protocol specifies quorum, tie_breaker, fallback, and dissent
recording. Estimate integrity (0-1).

Protocol:
{protocol}

Return only a JSON object representing the TallyIntegrityAudit."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 3-6 protocol-improvement
interventions.

Composition targets: vstack.devils_advocate, vstack.bias_stack,
vstack.aar, vstack.grpi, vstack.lencioni

intervention_type one of: switch_to_concurring, switch_to_majority,
switch_to_consensus, switch_to_fist_to_five, switch_to_unanimous, add_quorum,
add_tie_breaker, add_fallback, tighten_threshold, new_eval, human_review,
compose_pattern.

target_dimension one of: model, threshold, quorum, tie_breaker, fallback, overall.

Protocol:
{protocol}
Method fit audit: {method_fit_audit}
Tally integrity audit: {tally_integrity_audit}

Return only a JSON array of GroupDecisionIntervention objects."""


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
    "DECISION_PROTOCOL_PROMPT",
    "DECISION_SYSTEM_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_METHOD_FIT_PROMPT",
    "FORENSIC_TALLY_INTEGRITY_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_DECISION_PROTOCOL_PROMPT",
    "assemble_prompt",
]
