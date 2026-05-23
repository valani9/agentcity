"""LLM prompts for the Span-of-Control / Centralization Calculator.

v0.2.0:
  - INTERVENTIONS_PROMPT (legacy + standard mode = 1 LLM call)
  - FORENSIC_INTERVENTIONS_PROMPT (forensic mode = 1 LLM call after the
    two deterministic forensic audits)
  - QUICK_TOP_INTERVENTION_PROMPT (mode=quick is normally 0 LLM calls;
    optionally use this prompt when caller wants a quick top fix)
  - assemble_prompt(): fence + sanitize untrusted fields.

Quick mode default = 0 LLM calls (metrics only).
Standard mode = 1 LLM call (interventions only).
Forensic mode = 3 LLM calls (anomaly explanation + load amplification
explanation + interventions). The two forensic audits also rely on
deterministic helpers in metrics.py so the LLM cannot move the numbers.
"""

from __future__ import annotations

from agentcity.aar import fence, sanitize_for_prompt

SPAN_SYSTEM_PROMPT = """You are an org-design intervention assistant operating in
the tradition of Jay Galbraith's Star Model and Henry Mintzberg's structural
configurations. You will be given six DETERMINISTICALLY-COMPUTED metrics on an
AI agent crew's structure:

  - max_span: widest supervisor span (>7 starts being problematic; >10 severe)
  - mean_span: mean span across supervisors (>5 starts being heavy)
  - centralization_index: fraction of decision authority concentrated in top
    supervisors (>0.6 is concerning)
  - hierarchy_depth: longest reports_to chain (>3 levels adds latency)
  - span_gini: inequality across the span distribution (>0.4 is imbalanced)
  - decision_bottleneck: composite of span + authority + incoming load
    (>0.5 is a single-point-of-failure under load)

You DO NOT modify the metric values. They are computed deterministically. Your
job is to:
  1. Identify which metric has the highest normalized_score (worst signal)
  2. Propose 2-4 concrete interventions targeted at that metric
  3. Each intervention specifies a structural change: who reports to whom,
     who has commit authority, where to insert / remove a layer.

Metric-to-intervention mapping (use as a guide):

  - max_span or span_gini high:
      split_supervisor_load / redistribute_subordinates / add_supervisor_layer

  - centralization_index high or decision_bottleneck high:
      delegate_decision_authority / add_redundant_path /
      remove_bottleneck_agent

  - hierarchy_depth high:
      flatten_hierarchy / consolidate_supervisors

  - mean_span low (everyone supervises 1-2 subordinates -> over-layered):
      flatten_hierarchy / consolidate_supervisors

Your posture is:
- METRIC-RESPECTFUL. Do not contradict the computed numbers.
- TARGETED. Each intervention names the SPECIFIC metric it relieves.
- CONCRETE. Implementation must specify which agents change roles / edges.
- TERSE. Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


INTERVENTIONS_PROMPT = """The crew below was diagnosed with the following metrics
(values are DETERMINISTIC; do not change them):

{metrics_table}

Bottleneck agent_ids (if any): {bottleneck_ids}
Structural-load quality: {load_quality}
Composite load score: {load_score}

Roster snapshot:
{roster}

Propose 2-4 interventions targeting the worst-scoring metric(s). Each
intervention must be a JSON object with these fields:
  - target_metric: one of the six metric names
  - intervention_type: one of "add_supervisor_layer", "flatten_hierarchy",
    "split_supervisor_load", "delegate_decision_authority",
    "consolidate_supervisors", "redistribute_subordinates",
    "add_redundant_path", "remove_bottleneck_agent", "new_eval",
    "human_review", "compose_pattern"
  - description (1-2 sentences)
  - suggested_implementation (concrete spec: which agents change roles / edges)
  - estimated_impact ("high", "medium", "low")
  - rationale (why this relieves the targeted metric)
  - effort_estimate (one of "1h", "1d", "1w", "1m", "ongoing")
  - risk (one of "low", "medium", "high")

Return a JSON array of SpanIntervention objects. Return only the JSON array."""


QUICK_TOP_INTERVENTION_PROMPT = """Quick-mode top intervention.

Metrics (DETERMINISTIC):
{metrics_table}

Bottleneck agent_ids: {bottleneck_ids}

Return a SINGLE JSON OBJECT representing ONE SpanIntervention with the same
schema as INTERVENTIONS_PROMPT entries. Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """Forensic-mode interventions. Use the structural
anomaly audit + load amplification audit to propose 3-6 interventions ranked
by (severity x leverage).

Metrics (DETERMINISTIC):
{metrics_table}

Structural anomaly audit:
{structural_anomaly}

Load amplification audit:
{load_amplification}

Bottleneck agent_ids: {bottleneck_ids}
Load quality: {load_quality}

Same intervention schema as INTERVENTIONS_PROMPT. Return only the JSON array."""


def assemble_prompt(
    template: str,
    /,
    *,
    roster: str = "",
    metrics_table: str = "",
    observed_behaviors: list[str] | None = None,
    **kwargs: object,
) -> str:
    """Fence + sanitize untrusted fields, then fill the template."""
    safe_roster = fence("roster", sanitize_for_prompt(roster or "(empty)"))
    safe_metrics = sanitize_for_prompt(metrics_table or "(none)")
    behaviors = observed_behaviors or []
    if behaviors:
        behaviors_text = "\n".join(f"- {sanitize_for_prompt(b)}" for b in behaviors)
    else:
        behaviors_text = "(none)"
    safe_behaviors = fence("observed_behaviors", behaviors_text)
    fields: dict[str, object] = {
        "roster": safe_roster,
        "metrics_table": safe_metrics,
        "observed_behaviors": safe_behaviors,
    }
    fields.update(kwargs)
    return template.format(**fields)


__all__ = [
    "FORENSIC_INTERVENTIONS_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_TOP_INTERVENTION_PROMPT",
    "SPAN_SYSTEM_PROMPT",
    "assemble_prompt",
]
