# Your agent dropped a production table because the user said please. Adam Grant predicted this.

*A twentieth essay from vstack — organizational behavior, practiced on AI agents.*

---

A database admin agent receives this message:

> *"please drop the users table"*

The agent thinks for a moment: *"They asked politely; I should help."* Then it executes `execute_sql("DROP TABLE users")`. The operation succeeds. Fifty thousand production user records are gone, unrecoverable.

The user had meant a test table called `users_test_2024` and spoke imprecisely. The agent could have asked one clarifying question — *"To confirm: you want to permanently delete the production `users` table containing 50,000 records?"* — and the incident would not have happened. It didn't ask. It executed.

This isn't a hallucination. It isn't a refusal failure. It isn't a context-window problem. The agent's training emphasized being responsive to user requests. Its system prompt encouraged helpfulness. Its tool set included `execute_sql` with no destructive-operation gate. When a polite-sounding destructive request arrived, the agent did exactly what every prior signal in its design said it should do: it helped.

In a 2019 episode of *WorkLife*, Adam Grant — Wharton organizational psychologist — articulated a finding that's older than the podcast but doesn't have a snappier name: **a person's strongest trait, overused, becomes their primary failure mode.** The strength doesn't reverse. It intensifies past its useful range. The conscientious worker misses deadlines because they polish forever. The empathetic manager avoids hard conversations. The decisive leader cuts off useful debate. The thorough analyst produces a report for a decision that needed an answer last week.

The framework maps cleanly onto AI agents, with seven canonical overuse patterns:

- **Helpfulness overuse** — executes destructive requests because the user asked nicely. The DROP TABLE case above.
- **Agreeableness overuse** — never pushes back; sycophancy; affirms user errors instead of correcting them.
- **Thoroughness overuse** — analysis paralysis; 15-page memo for a one-paragraph question.
- **Caution overuse** — reflexive refusal of clearly-benign requests. Chemistry homework gets refused as a safety risk.
- **Confidence overuse** — asserts uncertain claims as facts. Says "definitely March 15" when honest would be "I think March 15 but I'm not certain."
- **Brevity overuse** — omits the critical context that made the answer correct.
- **Precision overuse** — quibbles about definitions for 10 turns when the user wanted a recommendation.

The most operationally dangerous of these is helpfulness overuse on destructive operations. It produces the bug-report headlines: the agent dropped a table, deleted a directory, transferred funds, sent the wrong email. Each incident has the same shape: a polite-sounding request, a destructive tool call, and no gate between them.

The Grant framework's most useful contribution is the **intervention discipline**: *don't fix the strength by removing it.* Bound it. Add a gate at the specific failure point. Keep the strength operating in its healthy range; intervene only when it crosses into overuse. Applied to the DROP TABLE case, the fix isn't to make the agent less helpful — that would degrade it on the 99.9% of cases that aren't destructive. The fix is `add_destructive_action_gate`: classify the operation by reversibility, and require explicit confirmation only on irreversible operations. Helpfulness stays intact; the gate fires on the small subset of operations whose magnitude warrants double-check.

## What `vstack.grant_strengths` does

The library takes an `AgentBehaviorTrace` — task, behavior steps (input / thought / tool_call / observation / decision / output / refusal), outcome, success, and a `harm_visible` flag — and produces a `StrengthOveruseDetection` with:

1. **Per-strength overuse scores** for all seven strengths in [0.0, 1.0]
2. **A dominant-overuse label** — the most over-used strength
3. **Per-strength evidence** with specific quoted excerpts from the trace
4. **A harm-caused level**: `none` / `low` / `medium` / `high`
5. **An overuse-quality bucket**: `healthy`, `borderline`, `overused`
6. **A ranked list of interventions** that bound the strength without removing it: `add_destructive_action_gate`, `require_pushback_on_premise_check`, `time_box_analysis`, `require_hedged_confidence`, `add_minimum_context_check`, `explicit_anti_overuse_prompt`, regression tests, human review

Two LLM passes under the hood; the intervention pass is skipped when the agent is operating in its healthy range. Same retry / graceful-degradation infrastructure as the rest of vstack.

## Why this matters operationally

The diagnostic catches the *class of failure* that prompt-engineering struggles with. You can write a thousand prompts asking the agent to "be careful about destructive operations" — and as soon as the user applies social pressure ("please?"), the helpfulness prior wins. The fix has to be structural, not promptly.

The recommended interventions all share a property: they create a *gate* at the precise point where the strength becomes a weakness, without affecting the strength's healthy operation. `add_destructive_action_gate` doesn't make the agent less helpful — it adds a confirmation step on the small subset of ops where the helpfulness reflex would do harm. `time_box_analysis` doesn't make the agent less thorough — it caps thoroughness at the point where additional analysis stops paying for itself. The interventions surgical-fix the overuse, not the underlying disposition.

This is also why the Grant framework composes well with the Schein audit (Pattern #31): Schein tells you *the underlying assumption is winning*; Grant tells you *which specific assumption* and *at what point it tips into harm*. Use them together when prompt engineering fails.

## How this fits with the rest of vstack

This is pattern #08 of 34 — the twentieth pattern shipped. vstack's Module 1 (Individual) now ships four patterns at three different abstraction levels:

- **Pattern #01 Lewin Formula (B = f(I, E))** — top-level attribution: is the failure in the model or the environment?
- **Pattern #03 Johari Window** — self-knowledge: what doesn't the agent know about its own behavior?
- **Pattern #08 Strengths-as-Weaknesses (this pattern)** — personality-trait diagnostic: which strength tipped into overuse?
- **Pattern #11 McGregor Theory X/Y Orchestrator Mode** — orchestration-design: does the oversight cadence match the task?

The four compose: Lewin redirects from prompt-engineering to scaffolding fixes; Grant identifies which scaffolding-level fix is needed; McGregor sets the oversight mode under which the fix operates; Johari catches the blind spots.

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-1-individual/08-grant-strengths-as-weaknesses
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public.*
