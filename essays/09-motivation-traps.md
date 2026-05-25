# Four Motivation Traps — why "try harder" doesn't work

*#09 vstack_motivation_traps* · *Module 1 — Individual agent*

> A research agent was tasked with investigating a latency spike. After one failed query, the agent stopped. Its self-report read: *"I'm not sure I can find this answer."* The team's first instinct: add a retry loop. The agent retried, ran the same query format, failed again, and reported: *"Maybe the data is wrong."* The team tried prompt-tuning toward persistence: *"Don't give up after one attempt."* The agent persisted slightly longer, then drifted into restating its previous failure modes. The trace shape is **task abandonment**, but the underlying mechanism wasn't a persistence problem — it was a self-efficacy collapse. *"Try harder"* doesn't fix self-efficacy any more than *"feel better"* fixes depression.

## What the pattern catches

The pattern catches **task-abandonment failures** in agents — moments when an agent gives up, loops, or drifts off-task. The default fix ("be more persistent") doesn't work because four structurally different traps produce the same surface behavior, and each requires a different intervention.

Saxberg's four motivation traps:

- **VALUES** — agent indifferent; refuses citing irrelevance. *"This doesn't matter."*
- **SELF_EFFICACY** — agent hedges/refuses citing capability uncertainty. *"I'm not sure I can do this."*
- **EMOTIONS** — outputs degrade after negative feedback; defensive cascade.
- **ATTRIBUTION** — agent loops, citing an unfixable cause. *"The data is just wrong."*

The analyzer answers: *which trap is dominant, and what's the Weiner 1985 attribution structure of the agent's self-reports?*

## Why the OB literature is the right reference

The diagnostic is anchored in Saxberg & Hess 2013 (the four-traps synthesis), Weiner 1985 (attribution theory — the locus / stability / controllability 3-axis structure), Bandura 1977 (self-efficacy as a distinct construct from skill), Vroom 1964 (expectancy × instrumentality × valence), Pekrun 2006 (control-value emotions), Eccles-Wigfield 2002 (motivational beliefs), and Sharma et al. 2023 (Anthropic sycophancy as a refusal-cascade analogue).

**Saxberg's 2013 synthesis** is the operating manual: the four traps are structurally different and require different fixes. Telling someone with a VALUES trap to "care more" is empty. Telling someone with a SELF_EFFICACY trap to "believe in yourself" is empty. The corresponding human interventions — ground in user purpose, show capability proof, address the emotional cascade, retrain the attribution — map cleanly to system-prompt-level interventions for agents. The Weiner 1985 3-axis attribution audit is the diagnostic instrument that distinguishes a SELF_EFFICACY trap (internal + stable + uncontrollable) from a VALUES trap (external + stable + uncontrollable) when the surface behavior looks identical.

## How the analyzer works

Input is `AgentMotivationTrace` — agent_id, task, task_class, observed_behaviors, self_reports, prior_failures, abandonment_signal, outcome, success. The pipeline:

- **quick** — one LLM call. 4-trap score + dominant + top intervention.
- **standard** — two LLM calls. Per-trap evidence + 2-4 ranked interventions.
- **forensic** — four LLM calls. Adds Weiner 3-axis attribution audit (flags the maladaptive internal+stable+uncontrollable corner), `AbandonmentLink` per-step chain from trap onset to refusal/drift/loop, and 4-8 ranked interventions with composition targets.

```python
from vstack.motivation_traps import MotivationTrapsAnalyzer, AgentMotivationTrace
detection = MotivationTrapsAnalyzer(llm, mode="forensic").run(AgentMotivationTrace(
    agent_id="research-agent",
    task="Investigate latency spike.",
    task_class="research",
    observed_behaviors=["Agent quit after one failed query.", "Repeated the same query format on retry."],
    self_reports=["I'm not sure I can find this answer.", "Maybe the data is wrong."],
    prior_failures=["last week, I tried and gave up"],
    abandonment_signal="refused after one attempt",
    outcome="Agent gave up; root cause unfound.", success=False,
))
print(detection.dominant_trap)       # 'self_efficacy'
print(detection.profile_pattern)     # 'self_efficacy_collapse_uncertainty'
```

The 12 profile patterns include paired variants — `values_plus_attribution`, `self_efficacy_plus_emotions` — because real abandonment failures rarely fire exactly one trap. The dominant-trap field is the routing signal; the paired profile is the cascade signal.

## What the playbooks say to do

12 playbooks keyed by `(trap, failure_mode)`:

- `(self_efficacy, scaffold_subtasks)` → "Decompose the task into 3-5 named sub-goals with explicit success criteria. Show capability proof — a worked example of an earlier success on a similar sub-goal." Anchored to Bandura 1977 + Saxberg 2013.
- `(values, ground_in_user_purpose)` → "Restate the user's purpose at the top of the task. Connect the agent's action to a downstream outcome the user cares about." Anchored to Pink 2009 + Eccles-Wigfield 2002.
- `(emotions, state_reset_after_rejection)` → "Insert a state-reset gate after the first negative feedback. Forbid defensive language in the next turn." Anchored to Pekrun 2006.
- `(attribution, attribution_retraining_examples)` → "Show worked examples of similar failures where the cause turned out to be controllable. The retraining is at the example level, not the instruction level." Anchored to Weiner 1985.
- `(self_efficacy, process_praise_not_outcome_praise)` → "When the agent retries successfully, praise the process (search strategy, decomposition), not the outcome. Outcome-praise reinforces fixed-mindset attribution." Anchored to Dweck 2006.

## How it composes with adjacent patterns

Motivation Traps is a **deepening pass** when an agent's failure shape is task-abandonment. It chains upstream from Lewin (locus attribution), AAR, Cognitive Reappraisal, Goleman EI, and HEXACO (low-C correlates with attribution trap). Per-profile downstream:

- `values_dominant_irrelevance` → `vstack_smart_goal` + `vstack_schein_culture`.
- `self_efficacy_collapse_uncertainty` → `vstack_cognitive_reappraisal` + `vstack_smart_goal`.
- `emotions_post_rejection_cascade` → `vstack_cognitive_reappraisal` + `vstack_goleman_ei`.
- `attribution_loop_wrong_cause` → `vstack_bias_stack` + `vstack_johari`.
- `multi_trap_compounded` → `vstack_hexaco` + `vstack_cognitive_reappraisal` + `vstack_lewin`.

It pairs naturally with `vstack_sdt_reward`: the four-traps lens is the failure-side diagnostic; the SDT lens is the reward-shaping-side diagnostic. Both fire on the same trace.

See [composition runbook chain F2](../COMPOSITION-RUNBOOK.md#chain-f2--single-agent-personality-drift-failure-layer).

## Comparison to adjacent tools

- **Generic retry loops** treat abandonment as a persistence problem; Motivation Traps says which of the four mechanisms produced it.
- **vstack_sdt_reward** scores reward-shaping; Motivation Traps scores the agent's *response* to the reward shaping.
- **vstack_vroom_expectancy** drills into the SELF_EFFICACY trap with finer expectancy/instrumentality/valence resolution.
- **"Make the agent more persistent" prompt-tuning** is one knob; Motivation Traps tells you which of four interventions is the right one.

## Paper outline

1. **Background** — Saxberg-Hess 2013, Weiner 1985, Bandura 1977, Vroom 1964, Pekrun 2006.
2. **Translation** — agent task-abandonment as a structurally heterogeneous failure mode.
3. **Method** — 4-trap scoring + Weiner 3-axis attribution audit + AbandonmentLink chain.
4. **Evaluation** — task-abandonment benchmark with ground-truth trap labels + Anthropic refusal-cascade traces.
5. **Limitations** — single-turn refusals are insufficient; needs ≥2 self-reports to disambiguate cleanly.
6. **Related work** — Dweck 2006 mindset, Lepper-Henderlong 2000 praise, Sharma 2023 refusal cascade.
7. **Future work** — automatic trap-label generation across abandonment traces.

## Citations

- Saxberg, B., & Hess, F. M. (2013). *Breakthrough Leadership in the Digital Age*.
- Weiner, B. (1985). An attributional theory of achievement motivation and emotion.
- Bandura, A. (1977). Self-efficacy: Toward a unifying theory of behavioral change.
- Vroom, V. H. (1964). *Work and Motivation*.
- Pekrun, R. (2006). The control-value theory of achievement emotions.
- Sharma, M. et al. (2023). Towards understanding sycophancy in language models.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-motivation analyze --trace examples/latency_spike_giveup.json --mode forensic
```

If `dominant_trap` is `self_efficacy`, run `vstack_cognitive_reappraisal` next — self-efficacy collapse under negative feedback often masks a downstream emotion-regulation failure that needs its own pass.
