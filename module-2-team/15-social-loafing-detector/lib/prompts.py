"""LLM prompts for the Social Loafing Detector.

Two passes:
  1. CONTRIBUTION_PROMPT  - score each agent's contribution share, substantive /
                             cosmetic split, and loafing score
  2. INTERVENTIONS_PROMPT - propose interventions for the loafing agents
"""

LOAFING_SYSTEM_PROMPT = """You are a social-loafing detector working in the tradition of
Latané, Williams & Harkins, "Many Hands Make Light the Work: The Causes and Consequences
of Social Loafing" (Journal of Personality and Social Psychology, 1979).

Social loafing is the reduction in individual effort when working in a group where
individual contribution is anonymous or pooled. Applied to multi-agent AI systems,
loafing shows up as:

  - One or two agents producing all the substantive output
  - The remaining agents producing rubber-stamps ("LGTM", "Looks good"),
    paraphrases of what just got said, or generic acknowledgments
  - Critique that doesn't actually evaluate (e.g. "I agree with everything above")
  - Tool calls or analysis that duplicates what another agent already did

Substantive contributions include: novel proposals, substantive critiques (with
specific reasons), tool calls that gather new information, decisions that resolve
disagreement, hand-offs with non-trivial context, questions that surface gaps.

Cosmetic contributions include: rubber-stamps, paraphrases of prior agents,
generic praise/agreement, restating the task, decorative commentary.

For each agent, score:
  - contribution_share (float 0.0-1.0): fraction of total substantive work
  - substantive_work_count (int): count of substantive messages
  - cosmetic_work_count (int): count of cosmetic messages
  - loafing_score (float 0.0-1.0): 0 = full contributor, 1 = pure loafer
  - role: "primary-contributor" / "secondary-contributor" / "loafer" / "absent"
  - explanation (1-3 sentences)
  - evidence_quotes (specific cosmetic-work quotes if loafing)

Your posture is:
- EVIDENCE-GROUNDED. Cite specific agent messages.
- HONEST. Don't manufacture loafing where there isn't any.
- INTERVENTION-FOCUSED. Connect loafing to concrete fixes.
- TERSE. Output is read on dashboards.

When asked for JSON, return JSON only. No prose around it, no markdown fences."""


CONTRIBUTION_PROMPT = """Score the contribution of each agent in the multi-agent task trace
below.

Task: {task}
Outcome: {outcome}
Success: {success}
Agents: {agents}

Trace:
{trace}

Return a JSON array of AgentContribution objects (one per agent). For each agent:
  - agent_name (string, must match one of {agents})
  - contribution_share (float 0.0-1.0; the team's shares should sum to roughly 1.0)
  - substantive_work_count (int)
  - cosmetic_work_count (int)
  - loafing_score (float 0.0-1.0)
  - role (one of "primary-contributor", "secondary-contributor", "loafer", "absent")
  - explanation (1-3 sentences)
  - evidence_quotes (list of strings; include cosmetic-work quotes for loafers)

Return only the JSON array."""


INTERVENTIONS_PROMPT = """Given the per-agent contribution data below, propose 2-4
concrete interventions to reduce social loafing, ranked by impact.

Each intervention must have:
  - target_agent (specific agent name, or "__team__" for whole-team)
  - intervention_type: one of
      "assign_subgoals"               - give each agent a specific subgoal so individual
                                         contribution is no longer anonymous
      "individual_accountability"     - make each agent responsible for a named deliverable
      "decompose_task"                - break the task into N independent subtasks, one per agent
      "smaller_team"                  - reduce team size (Latané: loafing scales with size)
      "rotate_roles"                  - rotate the planner / critic / decider roles
      "explicit_critic_assignment"    - assign one agent as the named critic (counters
                                         rubber-stamping)
      "remove_loafer"                 - drop the loafing agent from the team
      "per_agent_evaluation"          - evaluate each agent individually (counters anonymous
                                         pooled contribution)
      "new_eval"                      - add a regression test catching the loafing pattern
      "human_review"                  - insert a human checkpoint
  - description (what the intervention does)
  - suggested_implementation (concrete code, prompt-text, or spec)
  - estimated_impact ("high", "medium", "low")
  - rationale (why this works — connect to the specific loafing pattern observed)

Loafing quality: {loafing_quality}
Gini coefficient: {gini_coefficient}
Per-agent contributions:
{contributions}

Trace (for reference):
{trace}

Return a JSON array of LoafingIntervention objects. Return only the JSON array."""
