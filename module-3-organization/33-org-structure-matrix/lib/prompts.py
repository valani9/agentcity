"""LLM prompts for the Org-Structure Matrix Analyzer.

v0.2.0 prompts cover quick / standard / forensic modes:
  - STRUCTURE_PROMPT (legacy + standard)
  - QUICK_STRUCTURE_PROMPT (mode=quick)
  - INTERVENTIONS_PROMPT (legacy + standard)
  - FORENSIC_REPORTING_GRAPH_PROMPT, FORENSIC_BOTTLENECK_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT
  - assemble_prompt(): fence + sanitize untrusted fields using agentcity.aar.
"""

from __future__ import annotations

from agentcity.aar import fence, sanitize_for_prompt

STRUCTURE_SYSTEM_PROMPT = """You are an org-structure diagnostic working in the tradition of
Jay Galbraith's Star Model and Henry Mintzberg's structural configurations
("Structure in Fives", 1983). The diagnostic decomposes organizational structure into six
independent dimensions:

  - SPECIALIZATION        - how narrowly are agent roles defined?
  - FORMALIZATION         - how rule-bound vs improvisational is the work?
  - CENTRALIZATION        - where do decisions actually get made? (1 = a single
                              orchestrator; 0 = every agent decides for itself)
  - HIERARCHY             - how many levels of supervisory escalation? (1 = many
                              levels; 0 = flat)
  - SPAN_OF_CONTROL       - how many subordinates does each supervisor manage?
                              (1 = wide spans; 0 = narrow / many supervisors)
  - DEPARTMENTALIZATION   - by what dimension are agents grouped (function /
                              product / customer / geography / matrix)?

Each dimension is INDEPENDENT - a crew can be high-specialization low-centralization
(distributed expertise), or low-specialization high-centralization (one orchestrator
running generalist workers), etc.

Target profiles by task class (rough heuristics -- adjust based on specifics):

  - creative_brainstorm:      low specialization, low formalization, low
                              centralization, very low hierarchy, wide span,
                              function-or-no grouping
  - research_exploration:     moderate specialization, low formalization,
                              low-medium centralization, low hierarchy
  - incident_response:        high specialization (roles defined), low
                              formalization (must adapt), HIGH centralization
                              (incident commander), moderate hierarchy
  - regulated_workflow:       high specialization, very high formalization,
                              high centralization, moderate-high hierarchy
  - customer_support:         moderate specialization, high formalization,
                              moderate centralization, moderate hierarchy
  - code_review:              low-moderate specialization, moderate
                              formalization, low centralization (peer review),
                              low hierarchy
  - high_throughput_pipeline: high specialization, high formalization,
                              moderate centralization, low hierarchy, wide spans
  - general_purpose:          balanced (~0.5 each)

Archetype classification (pick ONE that best matches the OBSERVED profile):
  - flat-peer:                   low hierarchy, low centralization, low specialization
  - hierarchical:                high hierarchy, high centralization
  - centralized-functional:      high centralization + function-grouped, medium hierarchy
  - decentralized-product:       low centralization + product-grouped
  - matrix:                      mixed grouping with multiple reporting lines
  - mixed:                       observed profile doesn't cleanly match one archetype

Your posture is:
- EVIDENCE-GROUNDED. Cite specific role definitions + reports_to edges + behaviors.
- TASK-CLASS-AWARE. Same structure is fit for some task classes and unfit for others.
- INTERVENTION-FOCUSED. Connect each gap to a concrete structural change.
- TERSE. Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


STRUCTURE_PROMPT = """Score each of the six structural dimensions for the crew below.

Task: {task}
Task class (target profile driver): {task_class}
Outcome: {outcome}
Success: {success}

Agent roster ({n_agents} agents):
{roster}

Observed behaviors:
{observed_behaviors}

Return a single JSON OBJECT with these fields:
  - archetype: one of "flat-peer", "hierarchical", "centralized-functional",
    "decentralized-product", "matrix", "mixed"
  - dimensions: array of exactly 6 StructureDimensionScore objects in the order:
      1. specialization
      2. formalization
      3. centralization
      4. hierarchy
      5. span_of_control
      6. departmentalization
    Each has: dimension, observed_score (float 0-1), target_score (float 0-1),
    fit_score (float 0-1), explanation (str), evidence_quotes (list of str),
    confidence (float 0-1), risk ("low" | "medium" | "high")
  - overall_fit: float 0-1 (mean of the six fit_scores)
  - fit_quality: one of "well-fit", "partial-fit", "misfit"
  - biggest_gap: which dimension has the LARGEST gap between observed and target
    (or "none" if no gap is significant)

Return only the JSON object."""


QUICK_STRUCTURE_PROMPT = """Quick-mode org-structure profile + one top intervention.

Task: {task}
Task class: {task_class}
Outcome: {outcome}
Success: {success}

Agent roster ({n_agents} agents):
{roster}

Observed behaviors:
{observed_behaviors}

Return a single JSON OBJECT with:
  - archetype: archetype label
  - dimensions: 6 StructureDimensionScore objects (same shape as standard)
  - overall_fit: float
  - fit_quality: "well-fit" | "partial-fit" | "misfit"
  - biggest_gap: dimension name or "none"
  - top_intervention: ONE StructureIntervention object, OR null if well-fit

Return only the JSON object."""


INTERVENTIONS_PROMPT = """Given the structural evidence below, propose 2-4 concrete
interventions to close the biggest gap.

Each intervention must have:
  - target_dimension (one of the 6 dimensions)
  - direction: "increase", "decrease", or "redesign"
  - intervention_type: one of
      "flatten_hierarchy"        - remove supervisory layers
      "add_supervisor_layer"     - introduce an orchestrator or sub-team lead
      "consolidate_roles"        - merge specialists into generalists
      "split_roles"              - split a generalist into specialists
      "shift_decision_authority" - move commit-authority closer to or away from
                                    the orchestrator
      "regroup_by_product"       - reorganize departmentalization
      "regroup_by_function"      - reorganize departmentalization
      "introduce_matrix"         - dual reporting lines
      "add_routing_layer"        - explicit dispatcher between user and crew
      "remove_routing_layer"     - direct peer access
      "new_eval"                 - regression test against the structural failure
      "human_review"             - human checkpoint
      "compose_pattern"          - hand off to another agentcity pattern
  - description (what the intervention does)
  - suggested_implementation (concrete spec, role definition, or org-chart change)
  - estimated_impact ("high", "medium", "low")
  - rationale (why this works -- connect to the dominant gap)
  - effort_estimate (one of "1h", "1d", "1w", "1m", "ongoing")
  - risk (one of "low", "medium", "high")

Task class: {task_class}
Archetype: {archetype}
Fit quality: {fit_quality}
Biggest gap: {biggest_gap}
All dimension evidence:
{evidence}

Return a JSON array of StructureIntervention objects. Return only the JSON array."""


FORENSIC_REPORTING_GRAPH_PROMPT = """Forensic-mode: analyze the reporting graph as a DAG.

Roster ({n_agents} agents):
{roster}

Return a single JSON OBJECT with:
  - depth: integer (longest reporting path)
  - branching_factor: float (mean direct reports per supervisor; 0 if no supervisors)
  - cycles_detected: boolean
  - orphans: list of agent_ids with no reports_to and no reports from anyone
  - bottleneck_agents: list of agent_ids whose removal would disconnect the graph
  - explanation (1-2 sentences)

Return only the JSON object."""


FORENSIC_BOTTLENECK_PROMPT = """Forensic-mode: identify the decision bottleneck (if any).

Task class: {task_class}
Roster:
{roster}
Observed behaviors:
{observed_behaviors}

Return a single JSON OBJECT with:
  - bottleneck_agent_id: agent_id or null
  - affected_dimensions: list of dimensions whose target score the bottleneck
    blocks (e.g. "centralization" / "hierarchy")
  - severity_estimate: "low" | "medium" | "high"
  - explanation (1-2 sentences)

Return only the JSON object."""


FORENSIC_INTERVENTIONS_PROMPT = """Forensic-mode interventions. Use the reporting-graph
audit + decision-bottleneck audit to propose 3-6 interventions ranked by
(structural-leverage x gap-size).

Task class: {task_class}
Archetype: {archetype}
Fit quality: {fit_quality}
Biggest gap: {biggest_gap}
Reporting graph: {reporting_graph}
Decision bottleneck: {decision_bottleneck}
All dimension evidence:
{evidence}

Same intervention schema as INTERVENTIONS_PROMPT. Return only the JSON array."""


def assemble_prompt(
    template: str,
    /,
    *,
    roster: str = "",
    observed_behaviors: list[str] | None = None,
    **kwargs: object,
) -> str:
    """Fence + sanitize untrusted fields, then fill the template."""
    safe_roster = fence("roster", sanitize_for_prompt(roster or "(empty)"))
    behaviors = observed_behaviors or []
    if behaviors:
        behaviors_text = "\n".join(f"- {sanitize_for_prompt(b)}" for b in behaviors)
    else:
        behaviors_text = "(none)"
    safe_behaviors = fence("observed_behaviors", behaviors_text)
    fields: dict[str, object] = {
        "roster": safe_roster,
        "observed_behaviors": safe_behaviors,
    }
    fields.update(kwargs)
    return template.format(**fields)


__all__ = [
    "FORENSIC_BOTTLENECK_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "FORENSIC_REPORTING_GRAPH_PROMPT",
    "INTERVENTIONS_PROMPT",
    "QUICK_STRUCTURE_PROMPT",
    "STRUCTURE_PROMPT",
    "STRUCTURE_SYSTEM_PROMPT",
    "assemble_prompt",
]
