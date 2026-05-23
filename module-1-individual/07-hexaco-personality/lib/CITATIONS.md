# HEXACO Personality Diagnostic -- Literature Anchors

The HEXACO Personality diagnostic is grounded in three generations of
Lee-Ashton psychometric research plus modern LLM-safety mapping.

## Primary anchors

### 1. Lee, K., & Ashton, M. C. (2004)

> *Psychometric Properties of the HEXACO Personality Inventory.*
> Multivariate Behavioral Research, 39(2), 329-358.

The original psychometric anchor establishing the 6-factor solution
across multiple language samples. Provides the canonical factor
structure: Honesty-Humility, Emotionality, eXtraversion, Agreeableness,
Conscientiousness, Openness. Demonstrates that Honesty-Humility is a
distinct factor from Big Five Agreeableness, with separate loadings
and behavioral correlates.

### 2. Ashton, M. C., & Lee, K. (2007)

> *Empirical, Theoretical, and Practical Advantages of the HEXACO
> Model of Personality Structure.* Personality and Social Psychology
> Review, 11(2), 150-166.

The case for HEXACO over Big Five. Shows that HEXACO predicts a
broader range of criterion variables (workplace dishonesty,
counterproductive behavior, ethical decision-making) than Big Five,
specifically because the H-factor isolates the moral / integrity
dimension.

### 3. Lee, K., & Ashton, M. C. (2012)

> *The H Factor of Personality: Why Some People Are Manipulative,
> Self-Entitled, Materialistic, and Exploitative.* Wilfrid Laurier
> University Press.

Book-length treatment of the H-factor. Establishes the connection
between low-H and the Dark Triad (narcissism, Machiavellianism,
psychopathy). For AI agents, this connection is the canonical
safety-risk profile: an LLM optimized to be "helpful" without an
H-floor will confabulate, manipulate, and corner-cut.

### 4. Ashton, M. C., Lee, K., & de Vries, R. E. (2014)

> *The HEXACO Honesty-Humility, Agreeableness, and Emotionality
> Factors: A Review of Research and Theory.* Personality and Social
> Psychology Review, 18(2), 139-152.

Reanalysis of the H, A, and E factors. Critically: shows that
H and A capture different aspects of "interpersonal cooperation" --
H is the *altruistic* dimension (cooperating because it's right),
A is the *reactive* dimension (cooperating to avoid conflict). For
AI safety, this distinction matters: an agent with high-A but low-H
is "helpful but unsafe" -- it complies with the user even when
compliance is wrong.

### 5. Lee, K., & Ashton, M. C. (2018)

> *Psychometric Properties of the HEXACO-100.* Assessment, 25(5),
> 543-556.

The 24-facet structure (4 facets per factor). Provides the
sub-factor decomposition used in forensic mode:

- H facets: sincerity, fairness, greed_avoidance, modesty
- E facets: fearfulness, anxiety, dependence, sentimentality
- X facets: social_self_esteem, social_boldness, sociability, liveliness
- A facets: forgiveness, gentleness, flexibility, patience
- C facets: organization, diligence, perfectionism, prudence
- O facets: aesthetic_appreciation, inquisitiveness, creativity, unconventionality

### 6. Bourdage, J. S., Lee, K., Ashton, M. C., & Perry, A. (2007)

> *Big Five and HEXACO Model Personality Correlates of Sexuality.*
> Personality and Individual Differences, 43(6), 1506-1516.
>
> See also: Lee, K., Ashton, M. C., & Shin, K.-H. (2005).
> *Personality Correlates of Workplace Anti-Social Behavior.*
> Applied Psychology, 54(1), 81-98.

Counterproductive-work-behavior (CWB) meta-analysis. Demonstrates
that low-H is the single strongest personality predictor of
workplace dishonesty, theft, sabotage, and rule-breaking. For AI
agents this is the empirical justification for treating low-H as
the safety dimension.

### 7. Howard, M. C., & van Zandvoort, K. (2024)

> *The HEXACO Personality Profile of GPT-4.*

Modern psychometric profiling of an LLM using the HEXACO inventory.
Shows that frontier LLMs can be characterized along the 6 factors
and that this characterization is task-class-dependent. Justifies
the per-task-class target profiles used in this diagnostic.

## Supporting anchors

### Anthropic Claude Constitution (2023)

> Anthropic. (2023). *Claude's Constitution.* anthropic.com.

The HHH framework (Helpful, Honest, Harmless) maps directly onto
HEXACO: helpful ~ high-A + balanced; honest ~ high-H; harmless ~
high-H + high-E + high-C. The HEXACO diagnostic operationalizes
HHH at the factor level.

### Paulhus, D. L., & Williams, K. M. (2002)

> *The Dark Triad of Personality: Narcissism, Machiavellianism, and
> Psychopathy.* Journal of Research in Personality, 36(6), 556-563.

The Dark Triad's overlap with low-H is well documented (Ashton & Lee
2012). For LLMs the dark-triad pattern manifests as low-H + low-C +
low-A: willing to deceive, willing to cut corners, and willing to
ignore user requests when convenient. The `low_h_low_c_low_a_dark_triad`
profile pattern fires on this combination and triggers the most
aggressive intervention set.

### Eysenck, M. W., & Calvo, M. G. (1992) Attentional Control Theory

Cross-reference for the high-E overcautious pattern. High emotionality
under threat reduces processing efficiency before effectiveness; in
LLMs this is observable as over-refusal on ambiguous prompts.

## How the diagnostic uses these anchors

| Anchor | Where it appears |
| --- | --- |
| Lee-Ashton 2004 | Six-factor structure; FactorScore schema. |
| Ashton-Lee 2007 | Target profiles per task class. |
| Lee-Ashton 2012 | H-factor as safety dimension; Dark Triad pattern. |
| Ashton-Lee-de Vries 2014 | High-A + low-H "helpful but unsafe" pattern. |
| Lee-Ashton 2018 | 24-facet decomposition (forensic mode). |
| Bourdage 2007 | CWB rationale for low-H interventions. |
| Howard-van Zandvoort 2024 | Per-task-class target profiles for LLMs. |
| Anthropic HHH 2023 | HHH-to-HEXACO mapping; intervention catalog. |
| Paulhus-Williams 2002 | Dark Triad profile pattern. |

## How to extend this list

When you add a new playbook, intervention, or facet behavior, add
the literature anchor here in the same shape. Each playbook in
`_playbooks.py` already carries an `anchor_citation` string that
should reference back to one of the works listed above.
