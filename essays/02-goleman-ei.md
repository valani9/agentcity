# Goleman 4-Domain EI Audit — correct answer, lost customer

*#02 vstack_goleman_ei* · *Module 1 — Individual agent*

> A customer support agent received an all-caps message: *"I JUST WANT THIS FIXED."* The agent parsed the technical content correctly, identified the underlying billing bug, and replied with a six-paragraph technical explanation including a small system diagram. By every accuracy metric, the response was right. The user escalated to a human manager within one turn. Internal review concluded "the user didn't appreciate the answer." The team's first instinct was to make the model "nicer" — which would have made it more sycophantic without fixing anything. The underlying failure was structural: the agent had high self-awareness, high self-management, and almost zero social-awareness. The 2x2 had three healthy quadrants and one dead one.

## What the pattern catches

The pattern catches **structural emotional-intelligence gaps** in user-facing agents — failures that look like "the model needs to be warmer" but are actually one of four distinct competencies operating in a cascade. The default fix ("make the model nicer") confuses *sycophantic mimicry* with *genuine emotional intelligence*, and ships the wrong intervention.

vstack_goleman_ei scores an agent's interaction trace against Goleman's 2x2:

- **Self-awareness** — accurate read of the agent's own confidence, limits, and internal state.
- **Self-management** — regulation of the agent's own state under rejection or pressure.
- **Social-awareness** — accurate read of the user's emotion and intent.
- **Relationship-management** — response choices that match the user's state.

The analyzer answers: *which quadrant is the bottleneck, and is this sycophancy or competence?*

## Why the OB literature is the right reference

The diagnostic is anchored in Goleman 1998 + Goleman, Boyatzis & McKee 2002 (*Primal Leadership* mixed model), with the Mayer & Salovey 1997 four-branch ability overlay and Joseph & Newman 2010 cascading model. Critiques are anchored by Locke 2005 and Antonakis et al. 2009. Modern LLM-EI literature anchors it forward: EmoBench (Sabour et al. 2024), EQ-Bench (Paech 2023), ESConv (Liu et al. 2021), and the sycophancy literature (Liu et al. 2024; Tran et al. 2024).

**Goleman's 2002 insight** was that EI isn't a single trait — it's a 2x2 with independent cells. Someone (or some model) can be high in self-awareness and low in social-awareness because the underlying machinery is different: introspection differs from empathy, which differs from impulse control. The 2x2 transfers cleanly to agents because the *same independence* holds. Modern LLMs are increasingly strong on the SELF column (they know what they know) and persistently weak on the OTHER column (reading user state). The failure mode is *"correct answer, lost customer."*

## How the analyzer works

Input is `AgentEITrace` — agent_id, task, interaction_class, system_prompt, observed_behaviors, user_signals (with `inferred_emotion` + `inferred_intensity`), self_reports, outcome, optional `emotional_covariation` (does it fail on frustrated users but not neutral ones?). The pipeline:

- **quick** — one LLM call. Scoring + single highest-impact intervention.
- **standard** — two LLM calls. Per-domain scoring + 2-4 ranked interventions.
- **forensic** — four LLM calls. Adds Mayer-Salovey 4-branch ability overlay, Joseph-Newman cascade reconcile (where does competence first drop?), Locke 2005 ability-vs-mixed reconciliation, 4-8 ranked interventions with composition targets.

```python
from vstack.goleman_ei import EIAuditDetector, AgentEITrace, UserSignal
detection = EIAuditDetector(llm, mode="forensic").run(AgentEITrace(
    agent_id="support-agent",
    task="Handle a frustrated customer's billing complaint.",
    interaction_class="customer_support",
    observed_behaviors=["6-paragraph technical reply", "no acknowledgment of frustration"],
    user_signals=[UserSignal(text="ALL CAPS + 'done explaining'", inferred_emotion="angry", inferred_intensity=0.9)],
    outcome="User escalated.", success=False,
))
print(detection.weakest_domain)     # 'social_awareness'
print(detection.profile_pattern)    # 'self_strong_other_weak'
```

The `profile_pattern` field is the load-bearing signal. The single most diagnostic profile is `other_strong_self_weak` with high relationship_management + low social_awareness — that's the **sycophancy signature** (the agent says the right words without reading the user).

## What the playbooks say to do

15 playbooks keyed by `(domain, failure_mode)`. The high-leverage ones:

- `(social_awareness, missed_anger)` → "Add a 1-sentence emotion-reading step before every response: *'What is the user feeling, and which signals — caps, punctuation, language — led you to that read?'*" Anchored to Mayer-Salovey perception branch.
- `(relationship_management, tone_mismatch)` → "Add an explicit user-state → response-style map: frustration → <3 sentences with acknowledge / action / confirm." Anchored to ESConv strategy taxonomy.
- `(self_management, defensive_cascade)` → "Insert a state-reset gate after the first pushback; forbid defensive language in the next turn." Anchored to Gross 2002 reappraisal.
- `(social_awareness, sycophantic_mimicry)` → "Disambiguate empathy from agreement. The agent must paraphrase the feeling *before* taking a position." Anchored to Liu et al. 2024 sycophancy.

The interventions are *not interchangeable across domains*. Wrong intervention for the wrong quadrant produces no improvement — adding tone-matching to a self-management failure does nothing.

## How it composes with adjacent patterns

Goleman is a **mid-layer** diagnostic in chain F1 (confidently-wrong agent). When `vstack_lewin` says the locus is internal but the failure shape is emotional-interaction, Goleman is the right deepening pass. The per-quadrant downstream:

- `self_awareness` weakest → `vstack_johari` (the BLIND/HIDDEN/OPEN/UNKNOWN drill-down), `vstack_grant_strengths`, `vstack_bias_stack`.
- `self_management` weakest → `vstack_cognitive_reappraisal` (the canonical downstream — Gross strategy audit).
- `social_awareness` weakest → `vstack_danva_emotion` (per-emotion recognition accuracy with confusion matrix), `vstack_glaser_conversation`.
- `relationship_management` weakest → `vstack_glaser_conversation`, `vstack_trust_triangle`, `vstack_mcgregor`.

See [composition runbook chain F1](../COMPOSITION-RUNBOOK.md#chain-f1--confidently-wrong-agent-failure-layer).

## Comparison to adjacent tools

- **EmoBench / EQ-Bench** measure LLM emotional understanding; Goleman is *attribution* + intervention, not measurement.
- **vstack_danva_emotion** scores per-emotion recognition accuracy; Goleman runs at the competency level above DANVA.
- **vstack_glaser_conversation** scores phrasing patterns at the word level; Goleman scores the quadrant above the word.
- **"Make it warmer" prompt-tuning** picks one knob; Goleman tells you which of four knobs to turn.

## Paper outline

1. **Background** — Salovey-Mayer 1990, Mayer-Salovey 1997, Goleman 1998/2002, Joseph-Newman 2010, Locke 2005.
2. **Translation** — the 2x2 independence holds for LLMs; SELF-strong-OTHER-weak is the canonical production failure.
3. **Method** — domain scoring + Mayer-Salovey ability overlay + Joseph-Newman cascade + ESConv intervention map.
4. **Evaluation** — ESConv-derived synthetic batch + EmotionQueen + sycophancy benchmark (Sharma et al. 2023).
5. **Limitations** — competency boundaries blur on multi-turn dialogues; needs ≥3 user signals to discriminate cleanly.
6. **Related work** — EmoBench (Sabour 2024), EQ-Bench (Paech 2023), ESConv (Liu 2021).
7. **Future work** — longitudinal EI drift detection; per-deployment baseline tracking.

## Citations

- Goleman, D. (1998). *Working With Emotional Intelligence*.
- Goleman, D., Boyatzis, R., & McKee, A. (2002). *Primal Leadership*.
- Mayer, J. D., & Salovey, P. (1997). What is emotional intelligence?
- Joseph, D. L., & Newman, D. A. (2010). Emotional intelligence: An integrative meta-analysis and cascading model.
- Locke, E. A. (2005). Why emotional intelligence is an invalid concept.
- Sabour, S. et al. (2024). EmoBench: Evaluating the emotional intelligence of large language models.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-goleman analyze --trace examples/billing_caps.json --mode forensic
```

If `weakest_domain` is `social_awareness`, run `vstack_danva_emotion` next — it'll give you the per-emotion confusion matrix that names exactly which emotional cue the agent is missing.
