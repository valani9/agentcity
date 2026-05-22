"""LLM prompts for the Devil's Advocate Role Separator.

Two passes:
  1. PHASE_EVIDENCE_PROMPT     - score whether each of the four phases (plan / execute /
                                  self_evaluate / external_critique) was present, who
                                  performed it, and how substantive it was
  2. INTERVENTIONS_PROMPT      - propose interventions to separate roles
"""

ROLE_SEPARATION_SYSTEM_PROMPT = """You are a role-separation diagnostic working in the
tradition of Irving Janis on groupthink ("Victims of Groupthink", 1972) and the broader
literature on structured dissent. The core principle: the same actor should not both
PROPOSE a plan and JUDGE its quality. When planning and judging collapse into one
actor, self-confirmation is almost guaranteed.

Applied to AI agents, the four phases you measure are:

  - PLAN              - the agent names a plan, hypothesis, or proposed solution
  - EXECUTE           - the agent acts on the plan (tool calls, generations, decisions)
  - SELF_EVALUATE     - the SAME actor reviews its own work
  - EXTERNAL_CRITIQUE - a DISTINCT actor (critic agent, reviewer, human) reviews the work

For each phase you must report:
  - present (bool): did this phase occur in the trace?
  - actor (str): which actor performed it (e.g. "primary", "critic", "human"). If
    the same string appears as the actor for both PLAN and SELF_EVALUATE, that is
    role conflation.
  - substantive_score (0.0 to 1.0): was the phase thorough (1.0) or rubber-stamping (0.2)
    or absent (0.0)?
  - explanation (1-3 sentences citing specific steps)
  - evidence_quotes (specific excerpts; can be empty)

Your posture is:
- EVIDENCE-GROUNDED. Cite specific steps.
- HONEST. If a phase is absent, mark present=false and substantive_score=0.0.
- INTERVENTION-FOCUSED. Each gap should connect to a concrete intervention.
- TERSE. Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


PHASE_EVIDENCE_PROMPT = """Score each of the four role phases against the agent trace below.

Task: {task}
Subject model: {model_name}
Outcome: {outcome}
Success: {success}

Reasoning trace:
{trace}

Return a JSON array of exactly 4 PhaseEvidence objects in the order:
  1. plan
  2. execute
  3. self_evaluate
  4. external_critique

For SELF_EVALUATE specifically, treat any step where the agent reviews, judges, or
expresses confidence in its OWN work as a self-evaluation. For EXTERNAL_CRITIQUE,
the actor must be DIFFERENT from the primary agent (look at the `actor` field on
each step).

Return only the JSON array."""


INTERVENTIONS_PROMPT = """Given the phase evidence below, propose 2-4 concrete interventions
to improve role separation, ranked by impact.

Each intervention must have:
  - target_phase (one of "plan", "execute", "self_evaluate", "external_critique")
  - intervention_type: one of
      "add_critic_agent"            - add a distinct critic-agent role separated from
                                       the primary agent
      "structured_self_critique"    - a structured self-critique template (lower-impact
                                       than a real second agent, but better than nothing)
      "red_team_loop"               - a red-team / adversarial-review loop before
                                       acceptance
      "devils_advocate_prompt"      - a prompt-patch making the same agent argue
                                       against its own plan (lowest-impact intervention)
      "external_review_gate"        - a hard gate requiring approval from a distinct
                                       actor before the work ships
      "pre_mortem_step"             - require the agent to imagine the plan failed and
                                       explain why, before executing
      "alternative_hypothesis_step" - require the agent to name 2+ alternatives before
                                       committing to a plan
      "human_review"                - insert a human checkpoint
  - description (what the intervention does)
  - suggested_implementation (concrete code, prompt-text, or spec)
  - estimated_impact ("high", "medium", "low")
  - rationale (why this works — connect to the target phase gap)

Role-separation quality: {quality}
Locus of judgment: {locus}
All phase evidence:
{evidence}

Trace (for reference):
{trace}

Return a JSON array of RoleSeparationIntervention objects. Return only the JSON array."""
