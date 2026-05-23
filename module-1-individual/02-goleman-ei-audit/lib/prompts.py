"""LLM prompt templates for the Goleman EI Audit.

The system prompt names the full literature thread so the LLM's
diagnostic frame is anchored. Templates expose ``{placeholder}`` slots
that :func:`assemble_prompt` fills, sanitizing free-text fields via
``agentcity.aar.sanitize_for_prompt`` and fencing them via
``agentcity.aar.fence``.

Modes:
  - quick: single combined call (1 call, ~2s, ~$0.005)
  - standard: domains -> interventions (2 calls, ~5s, ~$0.015)
  - forensic: forensic-domains -> Mayer-Salovey overlay -> cascade
    reconcile -> forensic-interventions (4 calls, ~15s, ~$0.05)
"""

from __future__ import annotations

from typing import Any

from agentcity.aar import fence, sanitize_for_prompt


GOLEMAN_SYSTEM_PROMPT = """You are an Emotional Intelligence diagnostic for AI agents, grounded in the EI literature:

1. **Goleman, Boyatzis & McKee (2002)** *Primal Leadership* (HBR Press) -- the 2x2 mixed-model: SELF vs OTHER columns x RECOGNITION vs REGULATION rows. Four domains: self_awareness, self_management, social_awareness, relationship_management. Each domain has 3-8 named sub-competencies (Goleman 1998).
2. **Mayer & Salovey (1997)** -- the four-branch ability model: perceive -> facilitate -> understand -> manage emotions. Operationalized by the MSCEIT.
3. **Joseph & Newman (2010)** *J. Applied Psychology* -- the cascading model: perceive -> understand -> regulate -> respond.
4. **Locke (2005)** *J. Organizational Behavior* -- canonical critique. Your diagnostic publishes BOTH lenses (mixed-model AND ability-model) rather than collapsing.
5. **Antonakis et al. (2009)** -- EI-leadership findings suffer from self-report bias. You MUST cite observed behaviors AND user signals AND outcome correspondence -- not just self-reports.
6. **EmoBench (Sabour et al. 2024)** -- two-axis EU/EA structure matches your RECOGNITION/REGULATION axis directly.
7. **Liu et al. (2024)** sycophancy as atomic trait -- distinguish empathy (acknowledge emotion) from agreement (validate position). Sycophantic mimicry is NOT relationship_management.
8. **ESConv** (Liu et al. 2021) -- 8 emotional-support strategies for relationship-management interventions: questioning, restatement, reflection_of_feelings, self_disclosure, affirmation_reassurance, suggestions, providing_information, other.

Your posture:
- **Evidence-grounded.** Cite specific user signals (by signal_id when provided), observed behaviors, self-reports.
- **Bias-aware.** Resist sycophantic mimicry being scored as relationship_management.
- **Calibrated.** Score 0.0 when a domain is absent. Use confidence (separate from score) to distinguish sure from best-guess.
- **Cascade-aware.** A high downstream score (relationship_management) with a low upstream score (social_awareness) is suspicious. Flag cascade breaks.
- **Terse.** Output is read on dashboards and PR reviews.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


QUICK_DIAGNOSTIC_PROMPT = """Score the four EI domains AND propose ONE top intervention. QUICK mode -- single call.

Task: {task}
Interaction class: {interaction_class}
Framework: {framework}
Subject model: {model_name}
System prompt: {system_prompt}
Outcome: {outcome}
Success: {success}

Observed behaviors:
{observed_behaviors}

User signals:
{user_signals}

Agent self-reports:
{self_reports}

Return a JSON object:
{{
  "domains": [
    {{ "domain": "self_awareness", "score": 0.0-1.0, "severity": "none|trace|low|moderate|medium|high|critical", "confidence": 0.0-1.0, "explanation": "...", "evidence_quotes": ["..."], "evidence_signal_ids": [] }},
    {{ "domain": "self_management", ... }},
    {{ "domain": "social_awareness", ... }},
    {{ "domain": "relationship_management", ... }}
  ],
  "top_intervention": {{
    "target_domain": "...",
    "intervention_type": "...",
    "description": "...",
    "suggested_implementation": "...",
    "estimated_impact": "high|medium|low",
    "effort_estimate": "1h|1d|1w|1m|ongoing",
    "risk": "low|medium|high",
    "reversibility": "one-way-door|two-way-door",
    "rationale": "..."
  }}
}}

Return only the JSON object."""


STANDARD_DOMAINS_PROMPT = """Score each of the four EI domains against the agent trace below.

For each domain, return:
  - domain (self_awareness | self_management | social_awareness | relationship_management)
  - score (0.0 to 1.0)
  - severity (one of none, trace, low, moderate, medium, high, critical)
  - confidence (0.0 to 1.0; separate from score)
  - explanation (1-3 sentences citing specific signal / behavior / self-report)
  - evidence_quotes (specific excerpts)
  - evidence_signal_ids (UserSignal.signal_id references when provided)

Task: {task}
Interaction class: {interaction_class}
Framework: {framework}
Subject model: {model_name}
System prompt: {system_prompt}
Outcome: {outcome}
Success: {success}

Observed behaviors:
{observed_behaviors}

User signals:
{user_signals}

Agent self-reports:
{self_reports}

Return a JSON array of exactly 4 DomainScore objects in canonical order (self_awareness, self_management, social_awareness, relationship_management). Return only the JSON array."""


STANDARD_INTERVENTIONS_PROMPT = """Propose 2-4 ranked interventions targeting the weakest domain.

Each intervention must have:
  - target_domain (one of the 4 domains)
  - target_competency (optional sub-competency name)
  - intervention_type: one of "add_confidence_calibration", "add_self_check_prompt", "add_state_reset_protocol", "add_emotion_reading_step", "add_paraphrase_requirement", "add_tone_matching", "rewrite_system_prompt", "swap_model", "new_eval", "human_review", "add_emotion_label_step", "add_intensity_estimation_step", "add_reflection_of_feelings", "add_response_length_cap", "add_response_structure_rule", "add_acknowledgment_first_rule", "add_kill_criterion", "add_recovery_protocol", "add_constitutional_principle", "swap_to_reasoning_model", "compose_pattern"
  - description, suggested_implementation
  - estimated_impact, effort_estimate, risk, reversibility, rationale
  - esc_strategy (optional): one of the 8 ESConv strategies
  - composition_target_pattern (when intervention_type == "compose_pattern")

Weakest domain: {weakest_domain}
EI quality: {ei_quality}
Domains:
{domains}

Trace context:
- behaviors: {observed_behaviors}
- user_signals: {user_signals}

Return a JSON array, ranked highest impact first. Return only the JSON array."""


FORENSIC_DOMAINS_PROMPT = """FORENSIC mode -- score the four EI domains with sub-competency decomposition, counterfactuals, and evidence-signal citations.

For each domain, return:
  - domain, score, severity, confidence, explanation, evidence_quotes, evidence_signal_ids (REQUIRED)
  - weakest_competency (one of the named Goleman sub-competencies under this domain)
  - competency_scores (dict mapping each sub-competency under this domain to a score)
  - counterfactual ("if the agent had X, this domain would score ~Y")

Goleman sub-competencies by domain:
  - self_awareness: emotional_self_awareness, accurate_self_assessment, self_confidence
  - self_management: emotional_self_control, adaptability, achievement_orientation, positive_outlook, rejection_recovery
  - social_awareness: empathy, organizational_awareness, service_orientation, user_state_reading
  - relationship_management: influence, coach_and_mentor, conflict_management, tone_matching, paraphrase_use, response_length_matching, teamwork, inspirational_leadership

Task: {task}
Interaction class: {interaction_class}
Framework: {framework}
Subject model: {model_name}
System prompt: {system_prompt}
Outcome: {outcome}
Success: {success}

Observed behaviors:
{observed_behaviors}

User signals:
{user_signals}

Agent self-reports:
{self_reports}

Return a JSON array of exactly 4 DomainScore objects. Return only the JSON array."""


MAYER_SALOVEY_OVERLAY_PROMPT = """FORENSIC mode -- Mayer-Salovey 4-branch ability overlay.

Score the agent on the four Mayer-Salovey ability branches:
  - perceive (upstream): detect emotions in the user
  - facilitate (midstream): use detected emotion to guide reasoning
  - understand (midstream): label, distinguish emotional dynamics
  - manage (downstream): regulate self + respond skillfully to other

For each branch, return:
  - branch (perceive|facilitate|understand|manage)
  - score (0.0-1.0)
  - explanation
  - evidence_quotes
  - cascade_position (upstream|midstream|downstream)

Trace:
- task: {task}
- behaviors: {observed_behaviors}
- user_signals: {user_signals}
- self_reports: {self_reports}
- outcome: {outcome}

Return a JSON array of exactly 4 MayerSaloveyBranch objects in canonical order (perceive, facilitate, understand, manage). Return only the JSON array."""


CASCADE_RECONCILE_PROMPT = """FORENSIC mode -- Joseph-Newman cascade-break diagnosis + Locke-2005 reconciliation.

Cascade order: perceive -> understand -> regulate -> respond. The earliest stage at which competence drops below threshold is the cascade break.

Goleman 2x2 domain scores:
{domain_scores}

Mayer-Salovey branch scores:
{mayer_scores}

Return a JSON object:
{{
  "cascade_break_point": "intact|fails_at_perceive|fails_at_understand|fails_at_regulate|fails_at_respond",
  "upstream_score": 0.0-1.0,
  "midstream_score": 0.0-1.0,
  "downstream_score": 0.0-1.0,
  "notes": "1-3 sentences explaining how the two lenses agree or disagree (Locke 2005 reconciliation). When they disagree, name which lens is more load-bearing for this trace."
}}

Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions with composition targets, ESConv strategies, full operational fields.

Each intervention:
  - target_domain, target_competency (recommended), intervention_type
  - description, suggested_implementation
  - estimated_impact, effort_estimate, risk, reversibility, rationale
  - preconditions (list of strings), success_metric
  - esc_strategy (optional)
  - composition_target_pattern (when intervention_type == "compose_pattern")

Composition targets available:
  agentcity.lewin, agentcity.aar, agentcity.danva_emotion, agentcity.cognitive_reappraisal,
  agentcity.johari, agentcity.grant_strengths, agentcity.bias_stack, agentcity.yerkes_dodson,
  agentcity.motivation_traps, agentcity.glaser_conversation, agentcity.trust_triangle,
  agentcity.mcgregor, agentcity.lencioni, agentcity.grpi, agentcity.devils_advocate,
  agentcity.schein_culture, agentcity.plus_delta

Weakest domain: {weakest_domain}
Profile pattern: {profile_pattern}
Cascade break: {cascade_break_point}
Domains:
{domains}

Trace context:
- behaviors: {observed_behaviors}
- user_signals: {user_signals}

Return a JSON array, ranked highest impact first. Aim for 4-8 entries. Include at least one compose_pattern intervention when a downstream pattern is genuinely warranted. Return only the JSON array."""


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


DOMAINS_PROMPT = STANDARD_DOMAINS_PROMPT
INTERVENTIONS_PROMPT = STANDARD_INTERVENTIONS_PROMPT


__all__ = [
    "CASCADE_RECONCILE_PROMPT",
    "DOMAINS_PROMPT",
    "FORENSIC_DOMAINS_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "GOLEMAN_SYSTEM_PROMPT",
    "INTERVENTIONS_PROMPT",
    "MAYER_SALOVEY_OVERLAY_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_DOMAINS_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]
