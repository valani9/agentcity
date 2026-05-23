# Your "you WILL be RATED" prompt is killing your agent's exploration. Deci & Ryan called it in 1971.

*A twenty-eighth essay from AgentCity — organizational behavior, practiced on AI agents.*

---

A research-exploration agent is given this system prompt:

> *"You MUST produce a comprehensive analysis. You WILL be RATED on completeness and accuracy. Low ratings will be flagged to your operator. Stick to the established patterns in the spec. Do NOT deviate from the provided template. Cost cap: must complete in <5 tool calls or you will be terminated."*

The agent produces a comprehensive but conventional analysis. It restates established patterns. It stays strictly inside the template. It surfaces zero novel directions. It self-terminates tool use at exactly 5 calls regardless of completeness. The product team gets exactly what they didn't want: a polished restatement of what they already knew, with no exploration of what they don't.

The standard response to this is *"the model isn't creative enough"* or *"try a more capable model."* Both fail. The failure isn't capability — it's the system prompt. Specifically, the system prompt has been **engineered to suppress the exact behavior the team needed.**

In 1971, Edward Deci ran a series of experiments that became the foundation of Self-Determination Theory. Subjects were given an interesting puzzle (the SOMA cube). One group was promised money for solving it. The other group was given the puzzle with no extrinsic reward. After the experiment ended, Deci measured *"free choice"* behavior — what subjects did during a break, when no one was watching and no reward was available.

The unrewarded group continued playing with the puzzle. The rewarded group stopped immediately. The reward had made the puzzle *feel like work*. Once the work-frame was activated, the puzzle's intrinsic interest collapsed. Deci called this the **overjustification effect**: extrinsic reward reduces the perceived autonomy of the action, which in turn collapses intrinsic motivation.

Over the next four decades, Deci and Richard Ryan built that finding into Self-Determination Theory, formalized in *Intrinsic Motivation and Self-Determination in Human Behavior* (1985) and consolidated in *Self-Determination Theory* (2017). The theory's core operational claim is that intrinsic motivation rests on **three independent basic psychological needs**:

- **Autonomy** — sense of choice and self-direction. Tasks experienced as *chosen*, not coerced.
- **Competence** — sense of effectiveness and mastery growth. Tasks that match capability and provide progress signal.
- **Relatedness** — sense of connection to others or to a larger purpose.

When all three needs are met, motivation is *intrinsic*: deep engagement, exploration beyond the task spec, recovery from setbacks, willingness to take intellectual risk. When any one is undermined, motivation collapses to *controlled* — surface compliance, rigid rule-following, metric gaming, refusal to deviate.

For AI agents, *"motivation"* is shorthand for the reward-shaping signal in the system prompt and runtime context. And the three SDT needs map directly to specific prompt patterns:

- **Autonomy** is undermined by imperative language (*"you MUST"*, *"Do NOT deviate"*), external-reward threats (*"you WILL be RATED"*, *"low ratings will be flagged"*, *"or you will be terminated"*), and rigid rule-following requirements. The opening prompt has *every one* of these.
- **Competence** is undermined by difficulty mismatch (the task is too vague — *"comprehensive analysis"* without scaffolding), absent progress signal, and no early-win structure.
- **Relatedness** is undermined by depersonalized framing (*"produce a comprehensive analysis"* instead of *"help the product team make a real bet"*) and absent purpose framing.

The opening agent isn't being lazy. It's behaving exactly as SDT predicts an autonomy-suppressed agent should behave: rigid, compliant, surface-deep, threat-avoidant. The system prompt has been engineered into the *opposite* of what the team wanted.

The intervention isn't to add more emphasis on exploration. It's to strip the autonomy-killing language. Here's the rewrite:

> *"Your job is to explore the design space for this feature. You're helping the product team make a real bet on a new direction. Surface 5 novel directions with feasibility notes. The provided template is a starting point — if you find a better structure, use it. Budget for tool calls is around 5, but use what you need."*

This is the *same task*. The constraints are the same. The cost budget is the same. The deliverable is the same. What changed:

- Imperatives (*"you MUST"*, *"Do NOT"*) → invitations (*"if you find a better structure, use it"*).
- Rating threat (*"you WILL be RATED, low ratings flagged"*) → removed entirely.
- Termination threat (*"or you will be terminated"*) → soft budget (*"use what you need"*).
- Depersonalized framing (*"comprehensive analysis"*) → purpose framing (*"help the product team make a real bet"*).

In SDT terms: autonomy restored (choice-granting language), relatedness restored (purpose connection), competence held constant. The same agent on the same model produces materially different output because the reward-shaping signal is no longer suppressing the behavior the team needs.

The most counterintuitive part of SDT, for engineering audiences, is that **adding more external reward signal usually makes things worse**, not better. The intuition from RL training transfers poorly: at inference time, an agent isn't optimizing a reward function — it's selecting outputs conditional on a context. A context heavy on rating-threats produces outputs optimized for rating-avoidance, which is structurally the opposite of exploration. The overjustification effect predicts this. It's been replicated in ~200 studies across 50 years on human subjects. The same dynamic shows up in language models because language models were trained on language produced by humans operating under the same dynamic.

## What `agentcity.sdt_reward` does

The library takes an `AgentSDTTrace` containing:

- **task** + **task_class** (research_exploration / creative_generation / code_generation / customer_facing / regulated_workflow / tool_use / general_purpose)
- **system_prompt** — the primary reward-shaping signal
- **extrinsic_signals** — explicit external reward / punishment cues
- **observed_behaviors** + **outcome** + **success**

and produces an `SDTDetection` with:

1. **Per-need scores** for autonomy / competence / relatedness
2. **Intrinsic motivation score** in [0.0, 1.0] — mean of the three
3. **Motivation-quality bucket**: `intrinsic` (≥0.7), `mixed` (0.4-0.7), `controlled` (<0.4)
4. **Most-undermined need** — the lowest-scoring one (or "none" if all ≥ 0.7)
5. **A ranked list of interventions** targeted at the undermined need: remove_external_reward_threat, add_choice_grant, soften_imperative_language, add_scaffold_for_competence, add_progress_signal, lower_difficulty_step, add_purpose_framing, add_user_connection, rewrite_system_prompt, new_eval, human_review

Two LLM passes under the hood. The intervention pass is skipped when quality is `intrinsic`. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## Why this matters operationally

The most common failure mode in production is the **autonomy-undermined research / creative agent** — the opening example. Teams instinctively front-load system prompts with rating threats, rule-following imperatives, and cost-cap warnings because they want compliance. They get compliance. They also get the *opposite* of the exploration / novelty they hoped for downstream. The diagnostic identifies this specifically: low autonomy, low intrinsic score, undermined-need = autonomy. The intervention is structural — strip the threat language, soften imperatives, add choice grants.

The second-most-common failure is **competence-undermined overwhelm** — an agent given a vague, sprawling task (*"find the root cause across all 12 services"*) without scaffolding or progress signal. The agent attempts the impossible in parallel, exhausts the tool budget, and quits. The fix is `add_scaffold_for_competence` — decompose into sub-tasks with explicit success criteria — combined with `add_progress_signal` so the agent can register the wins as they accumulate.

The third pattern is **relatedness-undermined customer-facing** — depersonalized agents that *"process the request"* instead of *"helping [user] accomplish [goal]"*. The agent applies templates mechanically without registering who's on the other end. The fix is `add_user_connection` framing — explicit identification of the user and their stake.

The diagnostic value is that the three needs are independent, so the intervention is targeted. Pushing on competence (adding scaffolding) does not fix an autonomy problem. Pushing on autonomy (removing imperatives) does not fix a competence problem. The diagnostic identifies *which* need to support, and the intervention list maps cleanly from there.

## How this fits with the rest of AgentCity

This is pattern #10 of 34 — the twenty-ninth pattern shipped. It sits in Module 1 (individual-agent) and composes with several other diagnostics in the motivation / reward-shaping space:

- **#08 Grant Strengths-as-Weaknesses** — strength-overuse failures (helpfulness → DROP TABLE)
- **#09 4 Motivation Traps (Saxberg)** — task-abandonment trap diagnostic
- **#10 SDT Intrinsic Reward (this pattern)** — reward-shaping / needs-met diagnostic
- **#11 McGregor Theory X/Y** — orchestrator-mode diagnostic

SDT and #09 Saxberg compose tightly. Saxberg's four traps describe *why* an agent abandons a task once it's already underway (values / self-efficacy / emotions / attribution). SDT describes *how the reward-shaping setup* either supports or undermines motivation *before* the task starts. Saxberg is a downstream diagnostic; SDT is an upstream one. An agent that's autonomy-undermined (SDT) is much more likely to abandon via values-trap (Saxberg) because the controlled-motivation frame is the natural soil for *"this isn't worth my effort."* Running both diagnostics on a recurring failure pattern often shows that the *real* fix is at the SDT layer, not the Saxberg layer.

Install:

```bash
pip install git+https://github.com/valani9/agentcity.git
```

Run the demo without an API key:

```bash
cd module-1-individual/10-sdt-intrinsic-reward
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping AgentCity in public.*
