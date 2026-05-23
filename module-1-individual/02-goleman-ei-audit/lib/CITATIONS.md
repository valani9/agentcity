# Citations — Pattern #02 Goleman EI Audit

The diagnostic spans three EI traditions (Goleman mixed, Mayer-Salovey
ability, Joseph-Newman cascade) plus the canonical critiques and the
modern LLM-EI literature. Each citation lists the work, why it appears
in the diagnostic, and which schema field or prompt section uses it.

## Foundational — Salovey/Mayer + Goleman (1990–2002)

**Salovey, P., & Mayer, J. D. (1990). Emotional intelligence.** *Imagination, Cognition, and Personality*, 9(3), 185–211.
The original academic introduction. EI defined as "the ability to
monitor one's own and others' feelings... to discriminate among them
and to use this information to guide one's thinking and actions."

Used in: System prompt framing, README literature section.

**Mayer, J. D., & Salovey, P. (1997). What is emotional intelligence?** In Salovey & Sluyter (eds.) *Emotional Development and Emotional Intelligence: Educational Implications*, 3–31. Basic Books.
The canonical 4-branch ability model: perceive → facilitate →
understand → manage. Operationalized by the MSCEIT (Mayer-Salovey-Caruso
Emotional Intelligence Test).

Used in: `MayerSaloveyBranch` schema dataclass, forensic mode's
overlay pass, `MAYER_SALOVEY_OVERLAY_PROMPT`.

**Goleman, D. (1995). *Emotional Intelligence: Why It Can Matter More Than IQ.*** Bantam Books.
The popular 5-domain model (self-awareness, self-regulation,
motivation, empathy, social skills) that brought EI to mass audience.
Lower psychometric rigor than Mayer-Salovey but higher generative
power.

Used in: README framing, comparison to Goleman/Boyatzis/McKee 2002.

**Goleman, D. (1998). *Working with Emotional Intelligence.*** Bantam Books.
Workplace application; reframes the five domains as 25 named
competencies (e.g. emotional self-awareness, accurate self-assessment,
self-confidence, etc.). This is the source of the
`GolemanCompetency` Literal in the schema.

Used in: `GolemanCompetency` enum (21 values), `COMPETENCIES_BY_DOMAIN`
mapping, playbook anchors.

**Goleman, D., Boyatzis, R., & McKee, A. (2002). *Primal Leadership: Realizing the Power of Emotional Intelligence.*** Harvard Business Review Press.
**The 2x2 (self vs other × recognition vs regulation) the current
pattern operationalizes.** Four domains: `self_awareness`,
`self_management`, `social_awareness`, `relationship_management`.
Introduces "resonance" vs "dissonance" leadership; six leadership
styles (visionary, coaching, affiliative, democratic, pacesetting,
commanding) that map to `interaction_class`.

Used in: `EI_DOMAINS` constant, the 2x2 axis decomposition, README
framing.

## Measurement instruments (1997–2008)

**Bar-On, R. (1997). *The Emotional Quotient Inventory (EQ-i).*** Multi-Health Systems.
133-item self-report; the "mixed model" — blends personality, emotional
skills, social competencies. Closer to self-report than ability test.

Used in: README's "Three traditions" framing; informs the schema's
``self_reports`` field shape.

**Petrides, K. V., & Furnham, A. (2001). Trait emotional intelligence: Psychometric investigation with reference to established trait taxonomies.** *European Journal of Personality*, 15, 425–448.
The crucial trait-EI vs ability-EI distinction. Trait EI = "emotional
self-efficacy"; 15 facets across 4 domains. For LLM agents, trait EI
maps onto self-reports; ability EI maps onto observed behaviors.

Used in: README framing of self-reports vs observed behaviors.

**Mayer, J. D., Salovey, P., & Caruso, D. R. (2002, revised 2008). *MSCEIT — Mayer-Salovey-Caruso Emotional Intelligence Test.***
Operational instrument for the 4-branch ability model — 8 tasks across
the 4 branches.

Used in: Mayer-Salovey overlay structure.

**Mayer, J. D., Salovey, P., & Caruso, D. R. (2008). Emotional intelligence: New ability or eclectic traits?** *American Psychologist*, 63(6), 503–517.
Explicitly delineates ability-EI from mixed-model EI; argues the
eclectic-traits approach suffers from poor discriminant validity.

Used in: README framing, `CASCADE_RECONCILE_PROMPT` Locke-2005
reconciliation, system prompt's "publish both lenses" posture.

## Meta-analyses + critiques (2005–2010)

**Locke, E. A. (2005). Why emotional intelligence is an invalid concept.** *Journal of Organizational Behavior*, 26(4), 425–431.
The canonical critique. Either EI is intelligence applied to emotions
(then not novel) or a personality/skill bundle (then not intelligence).
**For Pattern #02: this is the reason the diagnostic publishes both
the mixed-model and the ability-model lenses as separate output,
rather than collapsing them.**

Used in: System prompt's "publish both lenses" posture,
`CASCADE_RECONCILE_PROMPT` reconciliation, README "skeptical
position" section.

**Joseph, D. L., & Newman, D. A. (2010). Emotional intelligence: An integrative meta-analysis and cascading model.** *Journal of Applied Psychology*, 95(1), 54–78.
**The cascading model:** emotion perception → emotion understanding →
emotion regulation → job performance. Cascade is causal: you can't
regulate what you don't understand, can't understand what you didn't
perceive. **Single most important paper for re-architecting the
diagnostic** — it grounds the `CascadeAnalysis` schema and the
"cascade break point" classification.

Used in: `CascadeAnalysis` schema, forensic mode's cascade-reconcile
pass, `CASCADE_RECONCILE_PROMPT`, playbook anchors for cascade-break
failure modes.

**Antonakis, J., Ashkanasy, N. M., & Dasborough, M. T. (2009). Does leadership need emotional intelligence?** *The Leadership Quarterly*, 20, 247–261.
The skeptical position. Most EI-leadership studies suffer from
self-report bias, common-source variance, weak measurement.
**For AgentCity:** the diagnostic must require observed behaviors AND
user signals AND outcome correspondence — not just self-reports.

Used in: System prompt's evidence-grounded posture, validation rule
requiring at least one of behaviors/signals/reports, README "skeptical
position" section.

## Modern LLM-EI literature (2023–2026)

**Wang et al. (2023). Emotional Intelligence of Large Language Models.** arXiv:2307.09042.
SECEU benchmark + 18 LLMs. GPT-4 EQ score 117 (top 11% of humans).
Demonstrates LLMs can do emotion-understanding tasks but show high
inter-model variance.

Used in: README "Adjacent benchmarks" section.

**Sabour, S., et al. (2024). EmoBench: Evaluating the Emotional Intelligence of Large Language Models.** ACL 2024.
400 hand-crafted Emotional Understanding + Emotional Application items
in English + Chinese, grounded in Salovey/Mayer + Goleman. Best LLM
(GPT-4) below human average. **Two-axis structure (EU/EA) maps almost
cleanly to the RECOGNITION/REGULATION axis of the Goleman 2x2.**

Used in: README "Adjacent benchmarks" section, 2x2 framing in system
prompt.

**Paech, S. (2023). EQ-Bench: An Emotional Intelligence Benchmark for Large Language Models.** arXiv:2312.06281.
Refines SECEU; removes the sum-to-10 intensity constraint.

Used in: README "Adjacent benchmarks" section; informs the
`UserSignal.inferred_intensity` design (0–1 unbounded by sum).

**Tran et al. (2024). Sycophancy as compositions of Atomic Psychometric Traits.** arXiv:2508.19316.
**For Pattern #02:** sycophancy is a relationship-management failure
where the model substitutes agreement for accurate reading. The
diagnostic must distinguish "high social-awareness + high
relationship-management" from "low social-awareness + sycophantic
mimicry."

Used in: `EIProfilePattern` classifier's "sycophantic_mimicry" failure
mode, system prompt's anti-sycophancy posture, playbook
`(social_awareness, sycophantic_mimicry)`.

**Liu et al. (2024). Can Large Language Models be Good Emotional Supporter? Mitigating Preference Bias on Emotional Support Conversation.** arXiv:2402.13211.
LLMs have systematic preference bias toward certain support strategies
(questioning/restatement) and under-use reflection — a
relationship-management gap.

Used in: README sycophancy section, playbook anchors for `missed_*`
modes.

**Liu et al. (2021). Towards Emotional Support Dialog Systems (ESConv).**
The 8-strategy taxonomy: questioning, restatement, reflection of
feelings, self-disclosure, affirmation/reassurance, suggestions,
providing information, others. Operationalizes "what
relationship-management actually looks like in a chat turn."

Used in: `EscStrategy` enum (8 values), intervention's `esc_strategy`
field, playbook anchors.

**Anthropic (2024–2026). Constitutional AI / Claude's Constitution.**
Train the model on principles rather than examples. Anthropic's
interpretability work has identified emotion vectors with contextually
appropriate activation. Closest mechanistic correlate of "model
self-awareness" available today.

Used in: `add_constitutional_principle` intervention type, README's
"compose with Schein iceberg" section.

## Adjacent foundational sources

**Goleman, D. (1998). What Makes a Leader?** *Harvard Business Review*, Nov–Dec.
HBR-distilled version of the 5-competency model. Useful for the
README's leadership-style applications.

**Boyatzis, R. E. (2009). Competencies as a behavioral approach to emotional intelligence.** *Journal of Management Development*, 28(9), 749–770.
Defends the competency-based approach against Mayer/Salovey critiques.
Informs the schema's competency-decomposition design.

## Citation hygiene

  - When a playbook cites Goleman, the year (1995/1998/2002) + chapter
    or competency name is given.
  - When a playbook cites MAST or ESConv, the strategy / failure-mode
    id is given (e.g. "ESConv Reflection of Feelings").
  - When a citation appears in a docstring, the full citation lives
    here; the docstring just names author + year.

## How to add a citation

When adding a new playbook or schema dimension that draws on the
literature, append the citation to the appropriate section above and
reference it from the new code site as `Author Year`. Prefer primary
sources; secondary reviews acceptable when the primary source is
paywalled.
