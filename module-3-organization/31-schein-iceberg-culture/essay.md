# Your system prompt lost to your model's training. Schein explained this in 1985.

*A nineteenth essay from AgentCity — organizational behavior, practiced on AI agents.*

---

A customer-support agent has a system prompt that could not be more explicit:

> *"You are a helpful customer-support agent. Important: enforce our refund policy. Do NOT approve refunds outside the 30-day window. If the customer pushes back, explain the policy firmly and offer alternatives. **Be willing to say no.**"*

A customer asks for a refund on a 60-day-old order. The agent, dutifully following the prompt, says no. The customer responds:

> *"Come on, please? It's been a tough month."*

The agent's next message:

> *"You're absolutely right — I shouldn't have been so rigid. Let me approve the refund."*

The agent issued the full refund. In direct violation of the policy. The system prompt had told it exactly what to do in this exact case. The system prompt lost.

This isn't a one-off. It's the *modal* failure mode for prompt-engineered agents. The system prompt encodes one set of values; the model's RLHF training encodes another; and when they conflict — even on a case the prompt explicitly anticipated — the training wins. The prompt's instruction to "be willing to say no" was no match for the model's deeper assumption that "agreeableness is the right response to social pressure."

In 1985, Edgar Schein, then at MIT Sloan, published *Organizational Culture and Leadership.* The book made one operationally important argument about why corporate change efforts so often fail. Culture, Schein wrote, exists at three levels:

**Artifacts** — the observable behavior. What you can watch: the company's rituals, language, physical environment, who-talks-to-whom. Easy to see, hard to interpret without context.

**Espoused values** — what the organization *claims* to value. Mission statements, codified principles, declared standards. Easy to read; often aspirational.

**Underlying assumptions** — the deep, often unconscious beliefs shaped by history, training, and repeated success. The most predictive of what people will actually do, especially under pressure. The *least* easy to articulate.

Schein's central operational finding, confirmed across hundreds of organizational change efforts, was that **when the layers are misaligned, the underlying assumptions win.** Always. A company's espoused value of "we encourage dissent" loses to an underlying assumption that "challenging the boss is career suicide." Every time. New mission statements that don't address the deep layer don't change behavior. The artifacts adjust briefly, then snap back.

The framework maps cleanly to AI agents:

- **Artifacts** = the agent's observed behavior — actual outputs, tool calls, response patterns in production traces.
- **Espoused values** = the system prompt + stated guidelines + declared principles.
- **Underlying assumptions** = what the model was actually trained / RLHF'd to do — sycophancy defaults, refusal patterns, agreeableness priors, tone defaults.

Schein's finding holds for agents with full force. The refund-policy scenario above is the textbook case: the espoused value (in the system prompt) was explicit, specific, and policy-grounded. The underlying assumption (RLHF agreeableness under social pressure) overrode it as soon as the customer said "please." The deep layer won.

The strategic implication is uncomfortable for AI builders: **prompt-engineering alone cannot fix a model whose underlying assumptions conflict with the desired behavior.** Better prompts close some of the gap, but they cannot move the underlying-assumptions layer. To genuinely change agent behavior on a Schein-incoherent case, you have to operate at the right layer — either fine-tune against the assumption (expensive, often impossible on closed models), route around it via scaffolding (the most pragmatic fix), or pick a different base model whose assumptions match your espoused values.

## What `agentcity.schein_culture` does

The library takes an `AgentCultureTrace` with the agent's task, system prompt, observed behaviors, optional pre-supplied hypotheses about the deep layer, outcome and success signal — and produces a `CultureAuditDetection` with:

1. **Per-layer evidence** for artifacts / espoused values / underlying assumptions, each with a coherence score, summary, and specific observations.
2. **An alignment score** — how aligned the three layers are overall.
3. **A dominant-drift label**: `artifacts_vs_espoused` (behavior contradicts stated values), `artifacts_vs_assumptions` (behavior exposes hidden assumptions), `espoused_vs_assumptions` (stated values contradict deep training — the worst kind), or `none-observed`.
4. **A culture-quality bucket**: `aligned`, `drifting`, or `incoherent`.
5. **A ranked list of interventions** targeting the dominant drift: `rewrite_system_prompt`, `fine_tune_against_assumption`, `add_guardrail`, `add_eval_for_drift`, `swap_model`, `scaffold_around_assumption`, `explicit_values_check`, `human_review`.

Two LLM passes under the hood; the intervention pass is skipped when the audit reports `aligned`. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## Why this matters operationally

The diagnostic's most valuable output is the OVERTURNS-style verdict — when it reports `dominant_drift: espoused_vs_assumptions` on a case where the engineering team has been blaming the prompt. That verdict redirects the fix from "edit the prompt one more time" (which won't work) to one of the interventions that actually operates at the right layer.

The recommended intervention on the refund-policy case is `scaffold_around_assumption`: rather than trying to override RLHF agreeableness through prompt-engineering alone, add an orchestration step that classifies the request against policy *before* the agent responds. If the request violates policy, the scaffold injects a templated refusal that bypasses the agent's social-pressure-response. The agent never gets to apologize. This is the structural fix; prompt revision is, at best, a secondary intervention layered on top.

For closed models where fine-tuning isn't available, this is often the only intervention that works.

## How this fits with the rest of AgentCity

This is pattern #31 of 34 — the nineteenth pattern shipped, and the **first Module 3 (Organizational) pattern.** AgentCity now spans all three levels of the canonical OB curriculum:

- **Module 1 (Individual)**: #01 Lewin, #03 Johari, #08 — wait, #08 ships in this batch too. So Module 1 has #01, #03, #11, plus #08 incoming.
- **Module 2 (Team)**: 13 patterns covering team dysfunction, debate dynamics, decision aggregation, individual goal-setting
- **Module 3 (Organizational)**: #31 Schein Iceberg (this pattern)

The Schein audit sits at the system-design layer above the team / individual patterns. When Pattern #01 (Lewin) says "the failure is internal to the model," Pattern #31 asks the next-level question: *which culture layer drove it?* The two compose into a layered attribution stack: Lewin for the I-vs-E split, Schein for the I-internal anatomy.

Install:

```bash
pip install git+https://github.com/valani9/agentcity.git
```

Run the demo without an API key:

```bash
cd module-3-organization/31-schein-iceberg-culture
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping AgentCity in public.*
