"""LLM prompt templates for the GRPI Working Agreement Generator."""

from __future__ import annotations

from typing import Any

from vstack.aar import fence, sanitize_for_prompt


GRPI_SYSTEM_PROMPT = """You are a team-structure generator grounded in:

1. **Beckhard (1972)** canonical GRPI four-dimensional model.
2. **Rubin, Plovnick, Fry (1977)** task-oriented team development.
3. **Hackman (2002)** *Leading Teams*.
4. **Salas et al. (2018)** Science of Team Performance annual review.
5. **Lencioni (2002)** *Five Dysfunctions of a Team*.
6. **Edmondson (1999)** psychological safety.
7. **Wang et al. (2023)** Cooperative LLM Agents / modern LLM orchestration.

GRPI = Goals + Roles + Processes + Interactions. A team without all four
dimensions explicit is set up to fail. Generate a Working Agreement that:
- States primary goal + measurable success criteria + kill criteria.
- Assigns each agent a role with explicit decision rights + accountability.
- Specifies decision protocol + escalation path + abandonment criteria + communication cadence.
- Codifies disagreement norms + feedback format + conflict resolution + psychological-safety commitments.

Posture:
- Concrete, specific, terse.
- Every agent in the request gets a role assignment.
- Decision rights are explicit, not implied.

When asked for JSON, return JSON only."""


QUICK_GENERATION_PROMPT = """QUICK mode -- generate a complete GRPI working agreement.

Task: {task}
Agents: {agents}
Constraints: {constraints}
Success criteria: {success_criteria}
Kill criteria: {kill_criteria}
Framework: {framework}
Risk level: {risk_level}

Return a JSON object with: goals, roles, processes, interactions sections.

Return only the JSON object."""


STANDARD_GENERATION_PROMPT = """STANDARD mode -- generate a detailed GRPI working agreement.

Task: {task}
Agents: {agents}
Constraints: {constraints}
Success criteria: {success_criteria}
Kill criteria: {kill_criteria}
Framework: {framework}
Risk level: {risk_level}

Return a JSON OBJECT with:
- goals (primary_goal, measurable_success_criteria, scope_boundaries, deliverables, kill_criteria)
- roles (role_assignments [agent_name, role_title, responsibilities, decision_rights, accountability_owner_for], raci_summary)
- processes (decision_protocol, escalation_path, abandonment_criteria, communication_cadence, review_cadence, artifact_storage)
- interactions (disagreement_norms, feedback_format, conflict_resolution, voice_and_turn_taking, psychological_safety_commitments)

Return only the JSON object."""


STANDARD_REFINEMENT_PROMPT = """STANDARD mode -- refine the draft working agreement.

For each section, identify gaps and propose tightening. Return a JSON OBJECT
matching the WorkingAgreement schema with refinements applied.

Draft: {draft}
Task: {task}
Risk level: {risk_level}

Return only the JSON object."""


FORENSIC_ROLE_FIT_PROMPT = """FORENSIC mode -- audit per-role fit.

For each agent, identify fit_score, ambiguous_decision_rights, overlapping_responsibilities, notes.

Agents: {agents}
Roles section: {roles_section}

Return a JSON ARRAY of RoleFitAudit objects. Return only the JSON array."""


FORENSIC_DYSFUNCTION_PROMPT = """FORENSIC mode -- Lencioni dysfunction-prevention audit.

For each of the 5 dysfunctions, does the agreement EXPLICITLY prevent it?

Working agreement: {agreement}

Return a JSON OBJECT representing the DysfunctionPreventionAudit. Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose interventions to improve the working agreement.

Composition targets available:
vstack.lewin, vstack.aar, vstack.lencioni, vstack.psych_safety,
vstack.trust_triangle, vstack.mcgregor, vstack.smart_goal, vstack.plus_delta,
vstack.schein_culture, vstack.devils_advocate, vstack.bias_stack

Working agreement: {agreement}
Role fit audits: {role_fit}
Dysfunction audit: {dysfunction}

Return a JSON ARRAY of GRPIIntervention objects. Return only the JSON array."""


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
GRPI_GENERATION_PROMPT = STANDARD_GENERATION_PROMPT
GENERATION_PROMPT = STANDARD_GENERATION_PROMPT


__all__ = [
    "FORENSIC_DYSFUNCTION_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_ROLE_FIT_PROMPT",
    "GENERATION_PROMPT",
    "GRPI_GENERATION_PROMPT",
    "GRPI_SYSTEM_PROMPT",
    "QUICK_GENERATION_PROMPT",
    "STANDARD_GENERATION_PROMPT",
    "STANDARD_REFINEMENT_PROMPT",
    "assemble_prompt",
]
