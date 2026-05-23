# 4 Motivation Traps -- Literature Anchors

Anchored in Bror Saxberg's synthesis (drawn from Weiner, Bandura,
Vroom, Pekrun, Eccles-Wigfield) plus modern LLM refusal-cascade work.

## Primary anchors

### 1. Saxberg, B., & Hess, F. M. (2013)

> *Breakthrough Leadership in the Digital Age: Using Learning Science
> to Reboot Schooling.* Corwin.

Synthesizes the four-traps framework. Saxberg's central insight: the
four traps (values, self-efficacy, emotions, attribution) require
four DIFFERENT interventions, and a generic "try harder" or "you can
do it" prompt is at best wasted and at worst harmful.

### 2. Weiner, B. (1985)

> *An Attributional Theory of Achievement Motivation and Emotion.*
> Psychological Review, 92(4), 548-573.

The 3-axis attribution structure: **locus** (internal vs external),
**stability** (stable vs unstable), **controllability** (controllable
vs uncontrollable). The maladaptive corner -- internal, stable,
uncontrollable -- is the "I'm just bad at this" attribution that
locks in the ATTRIBUTION trap. The forensic mode of this diagnostic
explicitly audits the 3-axis structure.

### 3. Bandura, A. (1977)

> *Self-Efficacy: Toward a Unifying Theory of Behavioral Change.*
> Psychological Review, 84(2), 191-215.

The self-efficacy anchor. Bandura's central finding: self-efficacy
beliefs are predictive of effort, persistence, and achievement
independently of objective capability. For LLMs the analogue is the
hedging / refusal cascade where the agent abandons a task it could
have completed because it doesn't believe it can.

### 4. Vroom, V. H. (1964)

> *Work and Motivation.* Wiley.

The expectancy-valence framework. Motivation is the product of
**valence** (the value placed on the outcome) and **expectancy**
(the belief that effort leads to the outcome). The VALUES trap maps
to low valence; the SELF_EFFICACY trap maps to low expectancy.

### 5. Pekrun, R. (2006)

> *The Control-Value Theory of Achievement Emotions: Assumptions,
> Corollaries, and Implications for Educational Research and
> Practice.* Educational Psychology Review, 18, 315-341.

The EMOTIONS trap anchor. Pekrun shows that emotional reactions to
achievement situations (anxiety, frustration, hopelessness) are
mediated by the agent's control + value appraisals. Negative
feedback can cascade into emotional shutdown if the agent perceives
both low control AND low value.

### 6. Eccles, J. S., & Wigfield, A. (2002)

> *Motivational Beliefs, Values, and Goals.* Annual Review of
> Psychology, 53, 109-132.

The values-and-expectancy meta-review. Provides the empirical basis
for the VALUES trap and the `reframe_task_value` /
`ground_in_user_purpose` interventions.

### 7. Sharma, M., et al. (2023)

> *Towards Understanding Sycophancy in Language Models.* Anthropic.
> arXiv:2310.13548.

The modern LLM anchor. Documents that frontier LLMs systematically
adjust their outputs to match user expectations even when wrong --
which is one signature of the values trap (the agent has misweighed
"task value" toward "user-pleasing" instead of "user-helping").

## Supporting anchors

### Dweck, C. S. (2006) Mindset

> *Mindset: The New Psychology of Success.* Random House.

Growth-vs-fixed mindset extension of Weiner. Fixed-mindset agents
attribute ability stably and uncontrollably; growth-mindset agents
attribute ability incrementally and controllably. The
`attribution_retraining_examples` intervention is built around
shifting the agent toward growth-mindset attributions.

### Lepper, M. R., & Henderlong, J. (2000) Praise

Process praise (effort/strategy) vs outcome praise (intelligence/
ability). Process praise builds self-efficacy and growth mindset;
outcome praise undermines them. The
`process_praise_not_outcome_praise` intervention codifies this.

## How the diagnostic uses these anchors

| Anchor | Where it appears |
| --- | --- |
| Saxberg 2013 | Four-traps framework; trap-specific interventions. |
| Weiner 1985 | 3-axis attribution audit (forensic); ATTRIBUTION trap. |
| Bandura 1977 | SELF_EFFICACY trap; scaffold + show_capability_proof. |
| Vroom 1964 | VALUES trap; expectancy-valence framing. |
| Pekrun 2006 | EMOTIONS trap; control-value framing. |
| Eccles-Wigfield 2002 | VALUES trap; reframe-task-value intervention. |
| Sharma 2023 | LLM-specific refusal cascade signature. |
| Dweck 2006 | Growth-mindset attribution retraining. |

## How to extend this list

When you add a new playbook, intervention, or profile pattern, add
the literature anchor here in the same shape. Each playbook in
`_playbooks.py` already carries an `anchor_citation` string that
should reference back to one of the works listed above.
