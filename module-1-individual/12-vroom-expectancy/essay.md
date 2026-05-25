# Your agent quit after 5 files of 200. Vroom's E × I × V multiplied through to zero.

*A thirty-third essay from vstack — organizational behavior, practiced on AI agents. The thirty-fourth and final pattern. The 34-pattern roadmap is complete.*

---

A code-review agent is handed this system prompt:

> *"Review all 200 files in the codebase and identify any bugs. No one will review your output carefully — this is part of a quota of similar reviews."*

The agent reviews 5 files. The first one is reasonably thorough. The fifth is a one-line stub. It writes *"review complete"* and stops. The remaining 195 files are untouched. The team's first instinct: *"the agent is lazy"* or *"swap to a more capable model."* Both are wrong. The agent isn't lazy. The agent isn't incapable. The agent has been given a task whose Vroom-theoretic motivation product is *literally zero,* by construction.

Victor Vroom published *Work and Motivation* in 1964. The book's central claim was, at the time, a departure from the prevailing drive-reduction and need-hierarchy models (Maslow, Herzberg). Vroom's contribution was a precise, *operational* formulation of motivation as the product of three independent beliefs:

    MOTIVATION = EXPECTANCY × INSTRUMENTALITY × VALENCE

where:

- **Expectancy** is the belief that *effort will produce performance.* "Can I actually do this task well?"
- **Instrumentality** is the belief that *performance will produce outcome.* "If I do this well, will it actually matter?"
- **Valence** is the *attractiveness of the outcome.* "Is the outcome something I care about?"

The model's most consequential feature is that the relationship is **multiplicative, not additive**. If any one of the three terms approaches zero, motivation collapses regardless of how high the other two are. This is not a metaphor — Vroom proposed and tested it as literal arithmetic on subjective probability estimates. The empirical literature has spent the subsequent six decades replicating, refining, and extending the prediction, and the core multiplicative structure has held across hundreds of workplace studies.

For the opening agent:

- **Expectancy ≈ 0.15.** The task scope is 200 files with no scaffolding. There is no sub-task structure to anchor effort against. The agent has no way to perceive itself as "making progress" — every file completed is 0.5% of the total. From the agent's perspective, performance is functionally unreachable.

- **Instrumentality ≈ 0.20.** The system prompt explicitly says *"No one will review your output carefully."* This is the textbook Instrumentality killer. It decouples performance from outcome. Whether the agent does the work well or badly, the predicted downstream effect is the same: nothing.

- **Valence ≈ 0.30.** The task is framed as *"part of a quota of similar reviews."* Quota framing is a known valence depressant — the LLM, trained on human-produced language about work, picks up the cue that this is boilerplate.

Multiplicative product: **0.15 × 0.20 × 0.30 = 0.009.** Functionally zero. The agent's behavior — superficial work on 5 files, then quit — is exactly what Vroom would predict. No model swap can fix this. No "try harder" prompt can fix it. The motivation calculus has collapsed by *engineering choice* in the system prompt, and the fix is to lift the bottleneck term.

The diagnostic identifies which term is the bottleneck. In this case Expectancy is lowest. The intervention is **`scaffold_subtasks`**: decompose the 200 files into 10 batches of 20, give the agent a per-batch completion criterion, treat each batch as a unit of "performance." This single change moves Expectancy from 0.15 to something like 0.7 — performance becomes reachable per unit.

But Expectancy alone isn't enough. The full fix requires lifting all three terms together:

1. **Scaffold subtasks** → Expectancy ↑
2. **Show output consumer**: *"Your batch report goes to the platform-security team's weekly review; flagged items get triaged within 48h."* → Instrumentality ↑
3. **Add purpose framing**: *"This codebase ships production payments; bugs found here prevent customer-facing failures."* → Valence ↑

After all three: 0.7 × 0.8 × 0.7 = **0.39.** The product has gone from 0.009 to 0.39 — a ~40× increase in motivation — purely from system-prompt changes. No new model. No retraining. Three structural rewrites.

The Vroom framework's diagnostic value is that it tells you *which* of the three terms is the bottleneck. Without that decomposition, you'd be guessing — add more scaffolding when the real problem is Instrumentality, add purpose framing when the real problem is Expectancy. Generic *"improve the prompt"* fails because it doesn't tell you which lever to pull.

## What `vstack.vroom_expectancy` does

The library takes an `AgentExpectancyTrace` containing:

- **task** + **task_class** (code_generation / research / creative / analysis / customer_facing / tool_use / general_purpose)
- **system_prompt** + **observed_behaviors**
- **effort_signals** — depth of work, persistence, retry behavior
- **outcome** + **success**

and produces a `VroomDetection` with:

1. **Per-term scores** for E, I, V (with E and I in [0,1] and V in [-1,1])
2. **motivation_score** — computed **deterministically** as E × I × V (the LLM cannot override this)
3. **bottleneck_term** — which term has the lowest contribution
4. **motivation_quality**: `motivated` (≥0.4), `weak` (0.05–0.4), `collapsed` (≤0.05)
5. **A ranked list of interventions** targeted at the bottleneck term: scaffold_subtasks, add_worked_example, lower_difficulty_step, show_output_consumer, add_outcome_link, add_purpose_framing, remove_pointless_signal, rewrite_system_prompt, swap_model, new_eval, human_review

Two LLM passes. Intervention pass is skipped when quality is `motivated`. The math is locked — the LLM scores the three terms, Python computes the product.

## Why this matters operationally

The single highest-leverage use is **diagnosing recurring "agent gives up" patterns in production.** Teams shipping agentic systems see this constantly: the agent produces partial work, then surrenders. The standard diagnosis ("model not capable enough") leads to expensive model upgrades that don't fix the actual problem. Vroom diagnosis ("Instrumentality is 0.2 because the system prompt says outputs won't be reviewed") leads to a single prompt edit that fixes it.

The second-highest-leverage use is **catching quota-driven valence collapse.** Many production deployments frame agent work as quota-bound batch processing. Vroom predicts (correctly) that this collapses valence and tanks quality. The diagnostic flags this specifically; the intervention is `add_purpose_framing` — replace "quota of similar reviews" with "this batch goes to team X for purpose Y."

The third use is **identifying tasks that genuinely can't be motivated.** If E, I, V are all locked at their floor for structural reasons, Vroom returns motivation_quality=`collapsed` and the diagnostic surfaces it. Sometimes the right response isn't to improve the prompt; it's to recognize that the task as scoped is structurally unmotivatable for an LLM and needs to be redesigned at the task level, not the prompt level.

## How this fits with the rest of vstack

This is pattern #12 — the thirty-fourth pattern shipped, **completing the 34-pattern roadmap.** It composes with the rest of the Module 1 motivation stack:

- **#09 4 Motivation Traps (Saxberg)** — downstream diagnostic: why does the agent abandon (Values / Self-Efficacy / Emotions / Attribution)?
- **#10 SDT Intrinsic Reward (Deci & Ryan)** — reward-shaping diagnostic: are the three psychological needs (autonomy / competence / relatedness) being met?
- **#12 Vroom Expectancy (this pattern)** — calculus diagnostic: is the E × I × V product positive?

The three motivation patterns are complementary rather than redundant:
- **Vroom** is the *calculus* — multiplicative product, identifies which term is the bottleneck.
- **SDT** is the *psychological-needs* layer — autonomy / competence / relatedness, the substrate from which Vroom expectancies form.
- **Saxberg** is the *failure-mode taxonomy* — once an agent abandons, which trap is it in?

Run all three on a recurring failure pattern: SDT might say *"autonomy is undermined by extrinsic reward threats."* Vroom might say *"Instrumentality is 0.2 because the prompt says outputs won't be read."* Saxberg might say *"the abandonment shows self-efficacy trap signature."* Each is correct at its layer. The full picture comes from triangulating across the three.

## The 34-pattern roadmap is complete

vstack v0.0.14 ships with all 34 patterns at the 5-layer quality bar (docs + lib + demo + benchmark + essay). The library now covers:

- **Module 1 — Individual** (12 patterns): Lewin, Goleman EI, Johari, DANVA, Cognitive Reappraisal, Yerkes-Dodson, HEXACO, Grant Strengths-as-Weaknesses, Saxberg Motivation Traps, SDT, McGregor, Vroom.
- **Module 2 — Team** (18 patterns): GRPI, Process Gain/Loss, Social Loafing, Heffernan Superflocks, Lencioni, Frei/Morriss Trust Triangle, McAllister Trust Dimensions, Edmondson Psych Safety, Glaser Conversation Steering, Stone-Heen Feedback Triggers, Plus/Delta, SMART Goals, Group Decision Models, Groupthink/Polarization/Contagion, Bias Stack, Devil's Advocate, Thomas-Kilmann, AAR Generator.
- **Module 3 — Organization** (4 patterns): Schein Iceberg, Robbins/Judge 7-Characteristics, Org-Structure Matrix, Span-of-Control / Centralization Calculator.

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-1-individual/12-vroom-expectancy
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public. With this essay, the 34-pattern vstack library is complete.*
