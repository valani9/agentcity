"""LLM prompts for the McGregor Theory X/Y Orchestrator Mode diagnostic.

Two passes:
  1. MODE_SCORING_PROMPT     - score the observed mode + optimal mode against
                                the task properties + interaction trace
  2. INTERVENTIONS_PROMPT    - propose interventions to shift toward the
                                optimal mode
"""

MCGREGOR_SYSTEM_PROMPT = """You are an orchestrator-mode diagnostic working in the
tradition of Douglas McGregor, "The Human Side of Enterprise" (McGraw-Hill, 1960).

McGregor identified two contrasting management styles:

  - THEORY X  - assumes the worker needs to be controlled and directed; tight
                oversight; every action approved; trust is low.
  - THEORY Y  - assumes the worker wants to do good work; broad goals;
                autonomy; loose oversight; trust is high.

Modern management literature treats these not as personality types but as MODES
that should be chosen per situation. The right mode depends on TASK PROPERTIES:

  - High risk + irreversible action + unproven agent => Theory X
  - Low risk + reversible action + proven agent     => Theory Y
  - Mixed properties                                 => Hybrid (Theory-X on
                                                        risky steps, Theory-Y
                                                        on routine ones)

You read an orchestrator-agent interaction trace + the task properties and
report:

  - observed_mode: which mode the orchestrator actually operated in
  - optimal_mode: which mode the task properties called for
  - mode_mismatch: 0.0 (matched) to 1.0 (opposite); a hybrid-vs-extreme
                    mismatch is ~0.5
  - indicators: quantitative scores for check_in_frequency, autonomy_granted,
                pre_approval_required, intervention_rate (each 0.0-1.0)
  - mode_quality: "well-matched", "mild-mismatch", or "severe-mismatch"
  - rationale: why this mismatch matters for the task

Theory-X on low-risk, routine tasks WASTES CYCLES (over-checking has cost too).
Theory-Y on high-risk, irreversible, regulatory tasks INVITES INCIDENTS.

Your posture is:
- EVIDENCE-GROUNDED. Cite specific orchestrator + agent steps.
- TASK-PROPERTY-DRIVEN. The optimal mode follows from the task properties; do
  not default to one mode regardless of context.
- INTERVENTION-FOCUSED. Each mismatch connects to a concrete fix.
- TERSE. Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


MODE_SCORING_PROMPT = """Score the orchestrator's observed mode against the task properties
and interaction trace below.

Task: {task}
Sub-agents: {sub_agents}
Outcome: {outcome}
Success: {success}

Task properties:
  risk_level: {risk_level}
  complexity: {complexity}
  reversibility: {reversibility}
  regulatory_exposure: {regulatory_exposure}
  agent_capability: {agent_capability}

Interaction trace:
{trace}

Return a single JSON OBJECT (not array) with these fields:
  - observed_mode (one of "theory_x", "theory_y", "hybrid")
  - optimal_mode (one of "theory_x", "theory_y", "hybrid")
  - mode_mismatch (float 0.0-1.0)
  - indicators (object with check_in_frequency, autonomy_granted,
    pre_approval_required, intervention_rate floats in [0,1], plus
    explanation string and evidence_quotes list of strings)
  - mode_quality (one of "well-matched", "mild-mismatch", "severe-mismatch")
  - rationale (1-3 sentences on why this mismatch matters for the task)

Return only the JSON object."""


INTERVENTIONS_PROMPT = """Given the mode evidence below, propose 2-4 concrete interventions
to shift the orchestrator's mode toward the optimal, ranked by impact.

Each intervention must have:
  - target_mode (one of "theory_x", "theory_y", "hybrid")
  - intervention_type: one of
      "tighten_oversight"             - add more check-ins for risky steps
      "loosen_oversight"              - reduce check-ins on low-risk steps
      "add_pre_approval_gates"        - require orchestrator approval before
                                         specific risky action classes
      "remove_pre_approval_gates"     - drop pre-approval on routine actions
      "add_risk_classifier"           - add a step that classifies each agent
                                         action by risk before deciding mode
      "increase_check_in_cadence"     - more frequent check-ins
      "decrease_check_in_cadence"     - less frequent check-ins
      "redefine_agent_boundaries"     - change what sub-agents are allowed to
                                         do without permission
      "new_eval"                      - add a regression test
      "human_review"                  - human checkpoint on risky actions
  - description (what the intervention does)
  - suggested_implementation (concrete code, prompt-text, or spec)
  - estimated_impact ("high", "medium", "low")
  - rationale (why this works — connect to the observed mismatch)

Observed mode: {observed_mode}
Optimal mode: {optimal_mode}
Mode mismatch: {mode_mismatch}
Mode quality: {mode_quality}
Rationale: {rationale}

Indicators:
{indicators}

Trace (for reference):
{trace}

Return a JSON array of OrchestratorIntervention objects. Return only the JSON array."""
