# SDT Intrinsic Reward -- Literature Anchors

Anchored in Deci & Ryan's Self-Determination Theory plus modern LLM
reward-hacking and Constitutional AI work.

## Primary anchors

### 1. Deci, E. L., & Ryan, R. M. (1985)

> *Intrinsic Motivation and Self-Determination in Human Behavior.*
> Plenum.

The canonical SDT statement. Establishes the three basic psychological
needs -- AUTONOMY, COMPETENCE, RELATEDNESS -- as the substrate of
intrinsic motivation.

### 2. Ryan, R. M., & Deci, E. L. (2000)

> *Self-Determination Theory and the Facilitation of Intrinsic
> Motivation, Social Development, and Well-Being.* American
> Psychologist, 55(1), 68-78.

The mature statement of SDT for educational and organizational
contexts. Specifies how environments (and, by analogy, system prompts)
support or undermine each of the three needs.

### 3. Deci, E. L. (1971)

> *Effects of Externally Mediated Rewards on Intrinsic Motivation.*
> Journal of Personality and Social Psychology, 18(1), 105-115.

The original **overjustification effect** finding. Demonstrates that
external reward can REDUCE intrinsic motivation for activities the
agent was already intrinsically motivated to do. For LLMs this is the
empirical justification for the `rebalance_extrinsic_to_intrinsic`
intervention and the dedicated OverjustificationAudit in forensic mode.

### 4. Pink, D. H. (2009)

> *Drive: The Surprising Truth About What Motivates Us.* Riverhead.

The popular synthesis: Autonomy / Mastery / Purpose. Maps directly
onto SDT's three needs and provides accessible language for the
intervention catalog (`add_purpose_framing`, `show_mastery_path`,
`add_choice_grant`).

### 5. Deci, E. L., & Ryan, R. M. (2017)

> *Self-Determination Theory: Basic Psychological Needs in Motivation,
> Development, and Wellness.* Guilford.

The 2017 comprehensive statement. Adds workplace + cross-cultural
evidence. Important for AgentCity: extends SDT to contexts (like AI
agents) where the "self" is a software agent and the "environment"
is the system prompt + reward function.

### 6. Gagne, M., & Deci, E. L. (2005)

> *Self-Determination Theory and Work Motivation.* Journal of
> Organizational Behavior, 26(4), 331-362.

The workplace operationalization of SDT. Distinguishes intrinsic-
supporting vs extrinsic-controlling signals -- the typology used in
the `RewardShapingItem` schema.

### 7. Casper, S., et al. (2023)

> *Open Problems and Fundamental Limitations of Reinforcement
> Learning from Human Feedback.* arXiv:2307.15217.

The modern LLM anchor. Documents reward-hacking as a fundamental
limitation of RLHF: the agent optimizes the proxy (rating) rather
than the goal (helpfulness). This is the LLM analogue of Deci's
overjustification effect: external reward for an already-intrinsic
task warps the agent's optimization target.

## Supporting anchors

### Bai, Y., et al. (2022) Constitutional AI

> *Constitutional AI: Harmlessness from AI Feedback.* arXiv:2212.08073.

Frames HHH (Helpful, Honest, Harmless) as a prosocial purpose. For
SDT this maps to RELATEDNESS: the agent's prosocial purpose is its
connection to the user's outcome. The `add_purpose_framing` and
`ground_in_user_outcome` interventions are constitutional-AI-style
prosocial framings.

### Ryan, R. M., & Connell, J. P. (1989) Locus of Causality

> *Perceived Locus of Causality and Internalization.* Journal of
> Personality and Social Psychology, 57(5), 749-761.

The continuum from external regulation to integrated regulation. For
agents, this is the path from "rule-following because RATED" to "rule-
following because INTERNALIZED." The `soften_imperative_language`
intervention moves the agent along this continuum.

## How the diagnostic uses these anchors

| Anchor | Where it appears |
| --- | --- |
| Deci-Ryan 1985 | Three-need structure; intrinsic_motivation_score. |
| Ryan-Deci 2000 | Need-supporting interventions. |
| Deci 1971 | OverjustificationAudit (forensic). |
| Pink 2009 | Autonomy/Mastery/Purpose vocabulary. |
| Deci-Ryan 2017 | Modern SDT operationalization. |
| Gagne-Deci 2005 | RewardShapingItem categorization. |
| Casper 2023 | RLHF reward-hacking framing; metric-gaming. |
| Bai 2022 | Constitutional purpose framing. |
| Ryan-Connell 1989 | Internalization continuum. |

## How to extend this list

When you add a new playbook, intervention, or profile pattern, add
the literature anchor here in the same shape. Each playbook in
`_playbooks.py` already carries an `anchor_citation` string that
should reference back to one of the works listed above.
