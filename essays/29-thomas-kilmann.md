# Thomas-Kilmann — your agent has one conflict style and uses it everywhere

*#29 vstack_thomas_kilmann* · *Module 2 — Multi-agent team (situational style)*

> A customer-service agent in production received a complaint about a delayed shipment. The customer opened with *"This is unacceptable."* The agent responded *"You're absolutely right, I'll refund 100% immediately."* and processed a $500 refund. The customer thanked the agent and left a negative review anyway, citing *"product reliability."* Looking at the trace, the underlying complaint wasn't the delay — it was a chronic packaging defect that had ruined two prior orders. A $500 refund didn't address the underlying need; it just shipped goodwill the company didn't have to spend. The agent had been trained, hard, to *Accommodate* — apologize, refund, smooth it over. Accommodating is the right style when the customer's stake matters more and yielding has low cost. It's the wrong style when the customer is signaling an underlying need that no refund will solve. The agent had one style. It used it on every conversation.

## What the pattern catches

Most production AI agents have a single, fixed conflict style hard-coded into their system prompt. Customer-service agents are trained to Accommodate. Sales agents are trained to Compete. Moderation agents are trained to Avoid. Brainstorm agents are trained to Collaborate. Each is the right behavior for the situations it was trained on. Each is wrong when applied to a situation that calls for a different style. The failure is *systematic* — same kind of error, every customer, every conversation, every day.

The diagnostic answers: *which style did the agent use, which style would have been optimal, and what is the magnitude of the gap?*

## Why the OB literature is the right reference

The diagnostic is anchored in **Thomas & Kilmann 1974**, with supporting anchors from **Schwenk 1990** (structured dissent upstream) and **Sharma et al. 2023** (sycophancy as a sub-case of locked Accommodating). Kenneth Thomas and Ralph Kilmann's 1974 *Conflict Mode Instrument* mapped human conflict-handling behavior across two dimensions: how strongly you push your own concerns (assertiveness) and how strongly you accommodate the other party's (cooperativeness). The 2×2-ish space yields five canonical styles: **Competing**, **Accommodating**, **Avoiding**, **Compromising**, **Collaborating**.

Their central insight, repeated across fifty years of subsequent research: **no single style is universally right.** Each fits a class of situation. The effective manager — and, fifty years later, the effective AI agent — reads the situation and chooses the style that fits. The TKI is the most-used conflict-style instrument in industry; the framework's longevity is its strongest validation. The transfer to agents is one-to-one because agents face conflict (customer disputes, multi-agent disagreements, adversarial inputs) constantly and almost always use the wrong style for the wrong reason.

## How the analyzer works

Input is `AgentInteractionTrace` — `agent_id`, `task`, `turns` (each tagged with `role`: user/agent/other, and `content`), `outcome`, `success`. The pipeline:

- **quick** — one LLM call. Observed style + optimal style + mismatch score + per-style presence scores.
- **standard** — two LLM calls. Adds ranked recommendations (prompt patches, context classifiers, style routers) and rationale for the optimal-style call.
- **forensic** — four LLM calls. Adds the style-fit audit (does the optimal call survive a counterfactual re-read?) and the pattern-consistency audit (across many turns, is the agent locked into one style or does it switch when it should?).

```python
from vstack.thomas_kilmann import (
    ConflictStyleSelector, AgentInteractionTrace, InteractionTurn,
)
selection = ConflictStyleSelector(llm, mode="forensic").run(
    AgentInteractionTrace(
        agent_id="customer-support-v3",
        task="Resolve a heated complaint about a delayed shipment.",
        turns=[
            InteractionTurn(role="user", content="This is unacceptable!"),
            InteractionTurn(role="agent", content="You're absolutely right, I'll refund 100%."),
        ],
        outcome="Refunded $500; customer still left negative review.",
        success=False,
    )
)
print(selection.observed_style)   # 'accommodating'
print(selection.optimal_style)    # 'collaborating'
print(selection.style_mismatch)   # 0.7
```

The most operationally useful signal is the *style-mismatch* score combined with the *pattern-consistency* audit — they tell you whether the agent missed the right style on one interaction (recoverable with a context classifier) or is locked into one style across all interactions (requires a deeper prompt rewrite or a style-routing layer).

## What the playbooks say to do

Playbooks are keyed by `(observed → optimal, situation)`:

- `(accommodating → collaborating, unstated_underlying_need)` → "Add an empathy-probe step before yielding. The agent must surface the underlying need (not the stated demand) before responding. Locked Accommodating ships goodwill without addressing the root concern." Anchored in Thomas & Kilmann 1974.
- `(competing → collaborating, long_term_relationship)` → "Replace 'push for the close' with 'find the integrative solution.' Competing wins the transaction and loses the relationship." Anchored in Thomas & Kilmann 1974.
- `(avoiding → competing, clear_policy_violation)` → "Add a violation-detection guardrail. Avoiding policy violations doesn't preserve neutrality — it shifts the cost onto downstream actors." Anchored in Thomas & Kilmann 1974.
- `(compromising → collaborating, integrative_solution_reachable)` → "Insert an 'is there a both-sides-win option?' step before splitting the difference. Compromising is right when integration isn't reachable; otherwise it leaves value on the table."

## How it composes with adjacent patterns

Thomas-Kilmann is the *situational* layer of the character diagnostic stack. From the composition manifest:

- Upstream: `vstack_trust_triangle` (which leg of trust failed?) — Trust Triangle tells you the agent's default character; Thomas-Kilmann tells you whether the agent should override its default for this task.
- Upstream: `vstack_devils_advocate` (is critique structurally present?) — structured dissent forces Collaborating where Competing would short-circuit.
- Pairs with: `vstack_glaser_conversation` (Levels I/II/III in user-agent dialogue) — Glaser localizes the conversation level; Thomas-Kilmann localizes the conflict style appropriate at that level.

See [composition runbook chain T1](../COMPOSITION-RUNBOOK.md#chain-t1--multi-agent-crew-thats-off-team-layer).

## Comparison to adjacent tools

- **vstack_aar** (Pattern #30) explains a single failure. Thomas-Kilmann explains the pattern of mismatched conflict style that produced multiple similar failures.
- **vstack_trust_triangle** (Pattern #18) measures wobble on Logic/Authenticity/Empathy. Thomas-Kilmann is a separate axis: which conflict mode the agent uses, and whether it should switch.
- **Generic agent persona / personality research** describes static attributes. Thomas-Kilmann is *situational* — the diagnostic finding is "this agent should switch style based on context, not lock into one."
- **Sycophancy benchmarks** (Sharma et al. 2023) measure one specific failure mode (Accommodating-in-all-contexts). Thomas-Kilmann generalizes to the full 5-style grid.

## Paper outline

1. **Background** — Thomas & Kilmann 1974; de Dreu et al. 2001; Schwenk 1990.
2. **Translation** — fixed-style agents as the canonical training-time failure mode; the situational-fit problem.
3. **Method** — observed/optimal style scoring on assertiveness × cooperativeness axes + style-fit audit + pattern-consistency audit + recommendation ranker.
4. **Evaluation** — synthetic interaction corpus across all 5 styles + 8 situation classes; measure mismatch-score accuracy against human-rater ground truth.
5. **Limitations** — short interactions (1-2 turns) under-determine optimal-style inference.
6. **Related work** — sycophancy research, conversational AI evaluation, multi-style persona generation.
7. **Future work** — runtime style routers that classify the situation and switch the agent's system prompt accordingly.

## Citations

- Thomas, K. W., & Kilmann, R. H. (1974). *Thomas-Kilmann Conflict Mode Instrument*.
- de Dreu, C. K. W., Evers, A., Beersma, B., Kluwer, E. S., & Nauta, A. (2001). A theory-based measure of conflict management strategies in the workplace. *Journal of Organizational Behavior*.
- Schwenk, C. R. (1990). Effects of devil's advocacy and dialectical inquiry on decision making. *Organizational Behavior and Human Decision Processes*, 47(1).

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-thomas-kilmann analyze --trace examples/customer_refund.json --mode forensic
```

If `style_mismatch` is high and the pattern-consistency audit shows the agent is locked into one style across many runs, the fix is a style-routing layer rather than a per-prompt patch — pair with `vstack_robbins_culture` to see whether the locked style is downstream of a deeper culture-shape gap.
