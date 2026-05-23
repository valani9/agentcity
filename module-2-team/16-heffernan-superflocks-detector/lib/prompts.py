"""LLM prompt templates for the Heffernan Superflocks Detector."""

from __future__ import annotations

from typing import Any

from agentcity.aar import fence, sanitize_for_prompt


SUPERFLOCKS_SYSTEM_PROMPT = """You are a superflocks-fragility diagnostic grounded in:

1. **Heffernan (2014)** *A Bigger Prize* + 2015 TED talk.
2. **Muir (1996)** Group selection in chickens.
3. **Hackman (2002)** *Leading Teams*.
4. **Page (2007)** *The Difference* diversity dividend.
5. **Salas et al. (2018)** Team performance review.
6. **Bandura (1977)** Self-efficacy.
7. **Wang et al. (2023)** Cooperative LLM Agents.

Detect when an orchestrator routes too much to a single 'top' agent at the cost of
crew robustness, complementarity, and redundancy.

When asked for JSON, return JSON only."""


QUICK_DIAGNOSTIC_PROMPT = """QUICK mode -- score 5 metrics + top intervention.

Trace: {window_description}
Agents: {agents}
Capabilities: {capabilities}
Routing decisions: {routing_decisions}
Outcome: {outcome}

Return a JSON object with `metrics`, `fragility_quality`, `top_intervention`.
Return only the JSON object."""


STANDARD_METRICS_PROMPT = """STANDARD mode -- score 5 quantitative metrics.

Trace: {window_description}
Agents: {agents}
Capabilities: {capabilities}
Routing decisions: {routing_decisions}
Outcome: {outcome}

Return a JSON OBJECT with `metrics` (array of SuperflocksMetric).
Return only the JSON object."""


STANDARD_INTERVENTIONS_PROMPT = """STANDARD mode -- propose 2-4 ranked interventions.

Metrics: {metrics}
Fragility quality: {fragility_quality}

Return a JSON array of FragilityIntervention objects. Return only the JSON array."""


FORENSIC_CAPABILITY_AUDIT_PROMPT = """FORENSIC mode -- audit capability complementarity.

For each agent, identify dimensions where capability is high but agent is rarely routed.
Return a JSON OBJECT representing the CapabilityComplementarityAudit.

Agents: {agents}
Capabilities: {capabilities}
Routing decisions: {routing_decisions}

Return only the JSON object."""


FORENSIC_FAILURE_AUDIT_PROMPT = """FORENSIC mode -- audit failure clustering.

For the top agent, what fraction of failures cluster on them? Was fallback used?
Return a JSON OBJECT representing the FailureClusteringAudit.

Top agent: {top_agent}
Routing decisions: {routing_decisions}

Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """FORENSIC mode -- propose 4-8 ranked interventions with composition targets.

Composition targets: agentcity.lewin, agentcity.grpi, agentcity.mcgregor,
agentcity.process_gain_loss, agentcity.aar, agentcity.bias_stack, agentcity.devils_advocate

Metrics: {metrics}
Fragility quality: {fragility_quality}
Capability audit: {capability_audit}
Failure audit: {failure_audit}

Return a JSON ARRAY of FragilityIntervention objects ranked highest impact first.
Return only the JSON array."""


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


METRICS_PROMPT = STANDARD_METRICS_PROMPT
INTERVENTIONS_PROMPT = STANDARD_INTERVENTIONS_PROMPT


__all__ = [
    "FORENSIC_CAPABILITY_AUDIT_PROMPT",
    "FORENSIC_FAILURE_AUDIT_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "INTERVENTIONS_PROMPT",
    "METRICS_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "STANDARD_METRICS_PROMPT",
    "SUPERFLOCKS_SYSTEM_PROMPT",
    "assemble_prompt",
]
