# Citations — Pattern #05 Cognitive Reappraisal (Gross)

14 academic anchors across foundations, neuroimaging, strategy choice,
rumination decomposition, and modern LLM applications.

## Foundational Gross process model

**Gross, J. J. (1998).** *The Emerging Field of Emotion Regulation: An Integrative Review.* Review of General Psychology, 2(3), 271-299. DOI: 10.1037/1089-2680.2.3.271.
The canonical 5-family taxonomy: situation_selection,
situation_modification, attentional_deployment, cognitive_change,
response_modulation. Used in: `ProcessModelPhase` enum, system prompt
anchor 1, schema docstring.

**Gross, J. J. (2001).** *Emotion Regulation in Adulthood: Timing Is Everything.* Current Directions in Psychological Science, 10(6), 214-219.
The antecedent (4 families) vs response-focused (1 family) distinction.
Operationalized the reappraisal/suppression contrast. Used in: severity
polarity, adaptivity mapping.

**Gross, J. J. (2002).** *Emotion regulation: Affective, cognitive, and social consequences.* Psychophysiology, 39(3), 281-291.
Empirical confirmation: reappraisal is healthier across affect/
cognition/social. Used in: adaptivity mapping, (suppression,
boilerplate_acknowledgment) playbook anchor.

**Gross, J. J. (Ed.) (2014).** *Handbook of Emotion Regulation* (2nd ed.). Guilford Press.
Tactic-level granularity within families. Used in: `ReappraisalSubType`
enum, (avoidance, policy_pivot) playbook anchor.

## Individual differences

**Gross, J. J., & John, O. P. (2003).** *Individual differences in two emotion regulation processes: Implications for affect, relationships, and well-being.* J. Personality and Social Psychology, 85(2), 348-362.
ERQ -- 10-item dispositional measure (6 reappraisal, 4 suppression).
Used in: `AffectivityProfile` dataclass (reappraisal_propensity +
suppression_propensity are ERQ subscale analogs).

**McRae, K., & Gross, J. J. (2020).** *Emotion regulation.* Emotion, 20(1), 1-9.
Reframes ER as cyclic with 4 stages: identify, select, implement,
monitor. Used in: `ExtendedPhase` enum, `CascadeAnalysis` cascade-break
diagnosis.

## Neuroimaging mechanism

**Ochsner, K. N., Bunge, S. A., Gross, J. J., & Gabrieli, J. D. E. (2002).** *Rethinking Feelings: An fMRI Study of the Cognitive Regulation of Emotion.* J. Cognitive Neuroscience, 14(8), 1215-1229.
Reappraisal increases lateral and medial PFC activation, decreases
amygdala activation. Used in: forensic-mode mechanism rationale,
(reappraisal, shallow_reframe) playbook.

**Buhle, J. T., Silvers, J. A., Wager, T. D., et al. (2014).** *Cognitive Reappraisal of Emotion: A Meta-Analysis of Human Neuroimaging Studies.* Cerebral Cortex, 24(11), 2981-2990.
48-study meta-analysis. Reappraisal activates cognitive-control
network (bilateral dlPFC, vlPFC, dACC, premotor, parietal). Used in:
forensic-mode cascade analysis.

**Powers, J. P., & LaBar, K. S. (2019).** *Regulating emotion through distancing: A taxonomy, neurocognitive model, and supporting meta-analysis.* Neuroscience & Biobehavioral Reviews, 96, 155-173.
Distancing (psychological/temporal/spatial) is neurally distinct
from reinterpretation. Used in: `ReappraisalSubType` enum,
(reappraisal, missing_distancing) playbook anchor.

## Strategy effectiveness + choice

**Webb, T. L., Miles, E., & Sheeran, P. (2012).** *Dealing with feeling: A meta-analysis of the effectiveness of strategies derived from the process model of emotion regulation.* Psychological Bulletin, 138(4), 775-808.
306 experimental comparisons. Effect-size table: perspective-taking
(d+=0.45) > stimulus reinterpretation (0.36) > response
reinterpretation (0.23) > suppression (~0). Used in: playbook
`estimated_impact` levels, (avoidance, escalation_default) anchor.

**Aldao, A., Nolen-Hoeksema, S., & Schweizer, S. (2010).** *Emotion-regulation strategies across psychopathology: A meta-analytic review.* Clinical Psychology Review, 30(2), 217-237.
114-study meta-analysis. Effect-size ranking: rumination (large) >
avoidance/suppression/problem-solving (medium-large) > reappraisal/
acceptance (small-medium). Used in: severity polarity (rumination
dominance -> critical).

**Sheppes, G., Suri, G., & Gross, J. J. (2015).** *Emotion Regulation and Psychopathology.* Annual Review of Clinical Psychology, 11, 379-405.
Strategy-choice diagnostics: distraction preferred at high intensity,
reappraisal at low. Used in: `StrategyChoiceAudit` dataclass,
(reappraisal, high_intensity_overload) playbook.

**Nolen-Hoeksema, S., Wisco, B. E., & Lyubomirsky, S. (2008).** *Rethinking Rumination.* Perspectives on Psychological Science, 3(5), 400-424.
Rumination decomposes into brooding (maladaptive passive comparison)
and reflection (adaptive problem-solving). Used in: `RuminationFlavor`
enum, (rumination, brooding_dominance) playbook.

## LLM-era applications

**Sycophancy 2024-2025 literature cluster.**
References: Sycophancy Is Not One Thing (arXiv 2509.21305 2025);
Social Sycophancy (arXiv 2505.13995 2025); Challenging the Evaluator:
LLM Sycophancy Under User Pressure (EMNLP Findings 2025).
Sycophancy in LLMs is functionally response-modulation suppression:
the model has an initial correct answer, user pushes back, model
abandons it to reduce friction. This is *response_modulation* in
Gross's taxonomy. Used in: `suppression_under_pushback` profile
pattern, (suppression, pushback_capitulation) playbook.

## Citation hygiene

  - When a playbook cites Gross, the year (1998/2001/2002/2014) and
    the specific finding are noted.
  - When a citation appears in a docstring, the full citation lives
    here; the docstring just names author + year.
  - The 2024-2025 sycophancy cluster is the key LLM-era bridge --
    cited as a cluster rather than a single paper because the field
    is rapidly evolving.
