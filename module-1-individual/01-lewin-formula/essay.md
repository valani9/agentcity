# Your agent isn't bad at math. Lewin had this debugged in 1936.

*An eleventh essay from AgentCity — organizational behavior, practiced on AI agents.*

---

A customer-support agent at a SaaS company keeps quoting wrong prices. The customer asks "what's your Enterprise plan?" and the agent confidently says "$499/month." The actual current price is $1,200. The customer escalates. This is the third such incident this week.

The team's instinct: *the model is hallucinating*. The fix queue:

1. Fine-tune on company-specific docs
2. Maybe upgrade to a bigger model
3. Add a hallucination evaluator
4. Engineer a tighter system prompt

That's the natural reading. It's also wrong. The agent's trace shows it called `retrieve_docs('Enterprise pricing')`, got back a chunk reading "Enterprise plan — $499/month", and used it. The model behaved correctly given its input. The bug isn't in the model. It's in the *environment around* the model — specifically, the RAG index contains `pricing-2024.pdf` and was never updated when pricing moved to a 2026 page.

The fix is one engineer-day of work on the indexing pipeline, not a fine-tuning run.

In 1936, Kurt Lewin published *Principles of Topological Psychology* with one of social psychology's most consequential equations:

> **B = f(I, E)** — behavior is a function of the individual and the environment.

The point isn't math. The point is attribution discipline. When you observe a behavior, your default move is to attribute it to the person ("she's lazy", "this team is dysfunctional"). Social psychologists call this **the fundamental attribution error**: over-weighting dispositional explanations, under-weighting situational ones. Lewin's formula is the cure: always check the environment before concluding it's the person.

The framework extends naturally to AI agents.

## Three loci of agent failure

When an agent fails, the cause sits in one of three places:

**Internal (I)** — the model itself: base capability, training cutoff, RLHF, reasoning depth, tool-use skill. *"This is a 4K-context model trying to summarize a 30K-token document — context overflow."* Fix: change the model.

**Environmental (E)** — the scaffolding around the model: system prompt, tools available, RAG context, task framing, orchestration loops, downstream consumers. *"The RAG index has stale data."* / *"The agent never got the tool it needed."* / *"The orchestration loop has no max-iteration cap."* Fix: change the scaffolding. Usually cheaper, usually faster, almost always under-prioritized.

**Interactional** — failure requires *both* this model AND this environment together. Neither swap alone fixes it. *"This model can't synthesize across three retrieved docs, AND the RAG isn't pre-summarizing for it."* Fix: usually environment first, then re-evaluate the model.

The systematic bias in AI engineering teams — at least the ones I've seen up close — is over-attribution to Internal. Every failure becomes "the model is bad." Every fix becomes "we need a better model." Half the time, the environment swap would have been a one-line change.

## What `agentcity.lewin` does

The library takes an `AgentFailureTrace` — task, reasoning steps, outcome, plus any **individual factors** and **environmental factors** the team has identified, plus an optional **initial team attribution** — and produces a `LewinDetection` with:

1. **Per-locus scores** for internal / environmental / interactional
2. **A dominant-locus diagnosis** (environmental breaks ties — the systematic bias to correct is over-attribution to the model)
3. **Per-locus evidence** with specific factor citations from the trace
4. **An attribution-quality label** (`well-attributed` / `ambiguous` / `miscalibrated`)
5. **A check on the initial team attribution** — does the diagnostic AGREE or OVERTURN where the team initially pointed the finger?
6. **A ranked list of interventions**: `change_model`, `change_prompt`, `change_tools`, `change_context`, `change_rag_index`, `change_orchestration`, `change_pipeline`, `new_eval`, `human_review`

Two LLM passes under the hood: one to score the three loci, one to propose interventions. Same retry / graceful-degradation / structured-logging infrastructure as the rest of AgentCity.

## Why this matters operationally

Most agent eval frameworks measure the *output* of the agent. They tell you it's wrong. They don't tell you where to redirect engineering effort.

The Lewin diagnostic answers the prior question. It tells you whether the failure is in the model or in the scaffolding *before* you spend the engineering cycles. The OVERTURNS verdict in particular — the diagnostic disagrees with the team's initial attribution — is the operationally valuable output. That's the moment you stop fine-tuning and start fixing your RAG index.

If you only adopt one diagnostic from AgentCity, this is a strong candidate. Most teams already know how to fix prompts and rebuild RAG indices. They just need a structured way to be told that's where the work actually is.

## How this fits with the rest of AgentCity

This is pattern #01 of 34 — and the eleventh patterns shipped. AgentCity now ships across multiple diagnostic axes:

- **Generative**: #13 GRPI Working Agreement
- **Event-shaped**: #30 AAR Generator
- **Team-shaped**: #17 Lencioni, #20 Edmondson Psychological Safety
- **Character-shaped**: #18 Trust Triangle
- **Self-knowledge**: #03 Johari Window
- **Reasoning-pattern**: #27 Bias-Stack
- **Conflict-style**: #29 Thomas-Kilmann
- **Feedback-intake**: #22 Stone & Heen 3-Trigger
- **Role-structure**: #28 Devil's Advocate Separator
- **Attribution**: #01 Lewin B = f(I, E)

The Lewin pattern sits *upstream* of the others. Before you reach for Bias-Stack ("is the model anchoring?") or Trust Triangle ("is the model character-wobbly?"), Lewin asks the prior question — "is this even a model problem at all?"

Install:

```bash
pip install git+https://github.com/valani9/agentcity.git
```

Run the demo without an API key:

```bash
cd module-1-individual/01-lewin-formula
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping AgentCity in public.*
