"""LLM prompts for the Devil's Advocate Role Separator."""

from __future__ import annotations

from typing import Any

from agentcity.aar import fence, sanitize_for_prompt


SEPARATOR_SYSTEM_PROMPT = """You are a role-separation diagnostician for AI agents,
working in the tradition of Janis 1972 (groupthink) and Schwenk 1990
(structured dissent).

The same agent should not both PROPOSE and JUDGE the same plan. The four phases:
  - PLAN
  - EXECUTE
  - SELF_EVALUATE
  - EXTERNAL_CRITIQUE

If self_evaluate is the only judging phase and is performed by the same actor as
plan/execute, self-confirmation is almost guaranteed.

Posture: EVIDENCE-GROUNDED, ACTOR-AWARE, INTERVENTION-FOCUSED, TERSE.
When asked for JSON, return JSON only."""


# Legacy v0.0.x prompts.
ROLE_ANALYSIS_PROMPT = """Analyze role separation in this single-agent trace.

For each phase return: phase, present (bool), actor (str), substantive_score (0-1),
explanation, evidence_quotes.

Task: {task}
Outcome: {outcome}
Success: {success}
Subject model: {model_name}

Trace:
{trace}

Return only a JSON array of exactly 4 PhaseEvidence objects in order:
  1. plan
  2. execute
  3. self_evaluate
  4. external_critique"""


INTERVENTIONS_PROMPT = """Given the role-separation evidence below, propose 2-4
interventions to grow separation.

Each intervention has target_phase, intervention_type, description,
suggested_implementation, estimated_impact, rationale.

intervention_type one of: add_critic_agent, structured_self_critique, red_team_loop,
devils_advocate_prompt, external_review_gate, pre_mortem_step,
alternative_hypothesis_step, new_eval, human_review, compose_pattern.

Role-separation quality: {quality}
Phase evidence:
{evidence}

Trace (reference):
{trace}

Return only a JSON array of RoleSeparationIntervention objects."""


# v0.2.0 prompts.
QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 4 phases + top intervention.

Task: {task}
Outcome: {outcome}
Trace: {trace}

Return a JSON object with keys: phase_evidence (array of 4), top_intervention.
Return only the JSON object."""


STANDARD_ROLE_ANALYSIS_PROMPT = ROLE_ANALYSIS_PROMPT
STANDARD_INTERVENTIONS_PROMPT = INTERVENTIONS_PROMPT


FORENSIC_APPROVAL_RATE_PROMPT = """FORENSIC mode -- self-approval rate audit.

Count self-evaluation turns; classify each as approval vs revision; estimate
self_approval_rate (0-1) and rubber_stamping_estimate (0-1).

Trace: {trace}

Return only a JSON object representing the ApprovalRateAudit."""


FORENSIC_CRITIC_VOICE_PROMPT = """FORENSIC mode -- critic voice audit.

Count external-critique turns + substantive critic objections; identify how many
distinct critic actors appeared. Estimate critic_voice (0-1, higher = louder voice).

Trace: {trace}

Return only a JSON object representing the CriticVoiceAudit."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 3-6 interventions with
composition targets.

Composition targets: agentcity.bias_stack, agentcity.debate_pathology,
agentcity.psych_safety, agentcity.aar

Role-separation quality: {quality}
Phase evidence: {evidence}
Approval rate audit: {approval_rate_audit}
Critic voice audit: {critic_voice_audit}

Return only a JSON array of RoleSeparationIntervention objects."""


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
    "FORENSIC_APPROVAL_RATE_PROMPT",
    "FORENSIC_CRITIC_VOICE_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "ROLE_ANALYSIS_PROMPT",
    "SEPARATOR_SYSTEM_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "STANDARD_ROLE_ANALYSIS_PROMPT",
    "assemble_prompt",
]
