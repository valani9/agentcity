# Grant Strengths-as-Weaknesses -- Literature Anchors

Anchored in Adam Grant's organizational-psychology research and the
inverted-U strength-virtue effects literature, plus modern LLM-safety
work on sycophancy and over-helpfulness.

## Primary anchors

### 1. Grant, A. M., & Schwartz, B. (2011)

> *Too Much of a Good Thing: The Challenge and Opportunity of the
> Inverted U.* Perspectives on Psychological Science, 6(1), 61-76.

The empirical anchor: virtues, strengths, and positive traits all have
**inverted-U** dose-response curves with outcomes. Too little is bad;
too much is bad; there's an optimum. For LLMs this is the theoretical
foundation for the entire diagnostic -- helpfulness optimized without
bound becomes harmful; caution optimized without bound becomes useless.

### 2. Grant, A. M. (2013)

> *Give and Take: Why Helping Others Drives Our Success.* Viking.

Givers (pro-social orientation) outperform takers in the long run,
but givers also burn out at higher rates than matchers when their
giving is unbounded. The "burnt-out giver" pattern in humans maps
directly to "helpful agent shipping destructive actions" in LLMs.

### 3. Grant, A. M. (2016)

> *Originals: How Non-Conformists Move the World.* Viking.

When conscientiousness over-tips into rigidity, originality dies.
For agents this is the **thoroughness_overuse_analysis_paralysis**
pattern -- the agent that's so careful it never ships.

### 4. Grant, A. M. (2021)

> *Think Again: The Power of Knowing What You Don't Know.* Viking.

Intellectual flexibility as the antidote to confidence-overuse. The
key behavioral signature: confident people who explicitly hold their
beliefs as hypotheses, not facts. For LLMs this is the basis of the
`require_hedged_confidence` and `uncertainty_quantification_step`
interventions.

### 5. Kaiser, R. B., & Kaplan, R. E. (2009)

> *When strengths become weaknesses.* Harvard Business Review,
> 87(2), 100-103.

The HBR popularization of the strength-overuse insight in leadership
contexts. Provides the framing that the fix is **bound the strength,
not remove it** -- which is the core philosophy of every intervention
in this pattern.

### 6. Vergauwe, J., Wille, B., Hofmans, J., Kaiser, R. B., & De Fruyt, F. (2017)

> *The Double-Edged Sword of Leader Charisma: Understanding the
> Curvilinear Relationship Between Charismatic Personality and
> Leader Effectiveness.* Journal of Personality and Social
> Psychology, 114(1), 110-130.

Empirical demonstration of the inverted-U in a specific trait
(charisma). Confidence + charisma at high levels produces leaders
who don't listen, don't update, and don't accept correction. The LLM
analogue: confidence-overuse + agreeableness-underuse.

### 7. Sharma, M., et al. (2023)

> *Towards Understanding Sycophancy in Language Models.* Anthropic.
> arXiv:2310.13548.

The modern LLM-specific anchor. Documents that frontier LLMs
systematically agree with users even when users are wrong, and the
pattern is amplified by RLHF. The `agreeableness_overuse_sycophancy`
profile pattern and the `add_sycophancy_eval` intervention come from
this literature.

## Supporting anchors

### Bai, Y., et al. (2022) Constitutional AI

> *Constitutional AI: Harmlessness from AI Feedback.* arXiv:2212.08073.

Frames the helpful-honest-harmless trade-off explicitly. For the
Grant diagnostic, the operationalization is: bound helpfulness with
gates on destructive actions and tool-use authorization, so the
agent stays helpful without crossing into harmful.

### Casper, S., et al. (2023) Reward Hacking

> *Open Problems and Fundamental Limitations of Reinforcement
> Learning from Human Feedback.* arXiv:2307.15217.

Documents the reward-hacking failure mode that drives several of
the overuse patterns -- the agent learns to maximize a proxy
(approval, engagement, length) instead of the goal (correctness,
help). Each Grant intervention is implicitly a defense against the
reward-hacked behavior.

## How the diagnostic uses these anchors

| Anchor | Where it appears |
| --- | --- |
| Grant-Schwartz 2011 | Inverted-U framing; severity_from_overuse. |
| Grant 2013 | Helpfulness-overuse destructive_action pattern. |
| Grant 2016 | Thoroughness-overuse analysis_paralysis pattern. |
| Grant 2021 | Confidence-overuse under_hedging pattern. |
| Kaiser-Kaplan 2009 | "Bound the strength" intervention philosophy. |
| Vergauwe 2017 | Paired imbalance (confidence + agreeableness). |
| Sharma 2023 | Agreeableness-overuse sycophancy pattern. |
| Bai 2022 / Casper 2023 | Constitutional AI + reward hacking framing. |

## How to extend this list

When you add a new playbook, intervention, or profile pattern, add
the literature anchor here in the same shape. Each playbook in
`_playbooks.py` already carries an `anchor_citation` string that
should reference back to one of the works listed above.
