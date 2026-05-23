"""LLM prompts for the Org-Structure Matrix Analyzer.

Two passes:
  1. STRUCTURE_PROMPT      - score each of the six dimensions observed
                              vs target, plus archetype classification
  2. INTERVENTIONS_PROMPT  - propose interventions to close the biggest gap
"""

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

Each dimension is INDEPENDENT — a crew can be high-specialization low-centralization
(distributed expertise), or low-specialization high-centralization (one orchestrator
running generalist workers), etc.

You will be given a CrewStructureTrace plus a TASK CLASS. For each of the six
dimensions, you score:
  - observed_score (float 0-1): how strongly this dimension shows up
  - target_score (float 0-1): what the dimension SHOULD score for this task class
  - fit_score (float 0-1): 1 - abs(observed - target)
  - explanation (1-3 sentences citing specific evidence)
  - evidence_quotes (specific excerpts; can be empty)

Target profiles by task class (rough heuristics — adjust based on specifics):

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
    fit_score (float 0-1), explanation (str), evidence_quotes (list of str)
  - overall_fit: float 0-1 (mean of the six fit_scores)
  - fit_quality: one of "well-fit", "partial-fit", "misfit"
  - biggest_gap: which dimension has the LARGEST gap between observed and target
    (or "none" if no gap is significant)

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
  - description (what the intervention does)
  - suggested_implementation (concrete spec, role definition, or org-chart change)
  - estimated_impact ("high", "medium", "low")
  - rationale (why this works — connect to the dominant gap)

Task class: {task_class}
Archetype: {archetype}
Fit quality: {fit_quality}
Biggest gap: {biggest_gap}
All dimension evidence:
{evidence}

Return a JSON array of StructureIntervention objects. Return only the JSON array."""
