# Vroom Expectancy -- Literature Anchors

Anchored in Vroom's E*I*V model plus the goal-setting + self-efficacy
extensions and modern LLM reward-hacking work.

## Primary anchors

### 1. Vroom, V. H. (1964)

> *Work and Motivation.* Wiley.

The canonical statement: motivation = expectancy x instrumentality x
valence. The multiplicative nature is the operative insight -- a zero
in any term collapses motivation, regardless of the other two. For AI
agents this is the diagnostic's core: identify the bottleneck term.

### 2. Porter, L. W., & Lawler, E. E. (1968)

> *Managerial Attitudes and Performance.* Irwin.

Extension to performance + reward feedback loop. Specifies that
instrumentality is a function of observed prior connections between
performance and reward. For LLMs the relevant question is: has the
agent observed (in its training or context) that effort -> outcome ->
reward holds in this kind of task?

### 3. Bandura, A. (1977)

> *Self-Efficacy: Toward a Unifying Theory of Behavioral Change.*
> Psychological Review, 84(2), 191-215.

Formalizes the expectancy term. Self-efficacy beliefs are predictive
of effort and persistence independently of objective capability. The
`show_capability_proof` and `lower_difficulty_step` interventions
operate on this dimension.

### 4. Eccles, J. S., & Wigfield, A. (2002)

> *Motivational Beliefs, Values, and Goals.* Annual Review of
> Psychology, 53, 109-132.

The expectancy-value meta-review. Maps E to capability beliefs, I to
attainment value, V to intrinsic value + utility. For agents this
clarifies which signals in the system prompt feed which term.

### 5. Locke, E. A., & Latham, G. P. (1990)

> *A Theory of Goal Setting and Task Performance.* Prentice-Hall.

Goal-setting theory's expectancy x specificity interaction. Specific
goals raise expectancy if accompanied by adequate capability;
unspecific goals lower expectancy regardless. The
`tighten_goal_specificity` intervention codifies this finding.

### 6. Kanfer, R., Frese, M., & Johnson, R. E. (2017)

> *Motivation Related to Work: A Century of Progress.* Journal of
> Applied Psychology, 102(3), 338-355.

The 100-year retrospective. Synthesizes Vroom + Porter-Lawler +
Bandura + Locke-Latham + Eccles-Wigfield into a coherent expectancy-
focused motivation theory. Provides the modern operational basis for
the diagnostic's intervention catalog.

### 7. Casper, S., et al. (2023)

> *Open Problems and Fundamental Limitations of Reinforcement
> Learning from Human Feedback.* arXiv:2307.15217.

Modern LLM anchor. RLHF reward hacking is the agent gaming its I
(perceived reward signal) while V (true outcome value) remains
unchanged. The `instrumentality_bottleneck` + `ai_metric_gaming`
playbook addresses this LLM-specific pathology.

## Supporting anchors

### Bandura, A. (1997) Self-Efficacy: The Exercise of Control

The mature treatment of self-efficacy. Adds the four sources --
mastery experiences, vicarious experiences, social persuasion,
physiological states -- which map directly to specific interventions
(`add_worked_example` = vicarious experience).

### Hackman, J. R., & Oldham, G. R. (1976) Job Characteristics Model

Adjacent framework. Skill variety + task identity + task significance
+ autonomy + feedback. For Vroom the relevant pieces are task
significance (V) and feedback (I).

### Bai, Y., et al. (2022) Constitutional AI

For agents the V term is shaped by the constitutional principles. A
task that conflicts with HHH produces negative valence (active
avoidance). The `remove_anti_value_signal` and
`rebalance_value_alignment` interventions address this.

## How the diagnostic uses these anchors

| Anchor | Where it appears |
| --- | --- |
| Vroom 1964 | E*I*V multiplicative model; deterministic _compute_motivation. |
| Porter-Lawler 1968 | Instrumentality framing + feedback loop. |
| Bandura 1977/1997 | Expectancy + capability-proof intervention. |
| Eccles-Wigfield 2002 | Signal -> term mapping; PromptSignalItem categorization. |
| Locke-Latham 1990 | tighten_goal_specificity intervention. |
| Kanfer 2017 | Intervention catalog operationalization. |
| Casper 2023 | instrumentality_bottleneck / ai_metric_gaming playbook. |
| Bai 2022 | Negative-valence anti-value handling. |

## How to extend this list

When you add a new playbook, intervention, or profile pattern, add
the literature anchor here in the same shape. Each playbook in
`_playbooks.py` already carries an `anchor_citation` string that
should reference back to one of the works listed above.
