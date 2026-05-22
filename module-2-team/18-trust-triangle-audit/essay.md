# Your agent wobbles on exactly one leg. Frei & Morriss called it.

*A third essay from AgentCity — organizational behavior, practiced on AI agents.*

---

Every act of trust requires three legs.

Logic — *I know you can do it; your reasoning is sound*. Authenticity — *I experience the real you*. Empathy — *I believe you care about me and my success*. Frances Frei and Anne Morriss spent a decade rebuilding trust at organizations in crisis — Uber after Travis Kalanick, WeWork after Adam Neumann, dozens of others — and in 2020 they distilled what they found into a triangle in *Harvard Business Review*.

The framework's punchline is the part that translates most cleanly to AI agents: **most leaders, like most agents, wobble on exactly one leg, consistently. The wobble is usually invisible to the leader and obvious to everyone else.** The diagnostic move — the entire move — is identifying which leg you wobble on. That's the leg to repair first. The other two legs are doing fine.

In 2026, we have a similar problem at scale with AI agents. Agent quality is treated as a one-dimensional score. The benchmarks measure aggregate "helpfulness" or aggregate "factuality" or aggregate "user satisfaction." The dashboards show one number per model. The number captures none of what users actually experience.

Users experience three things, independently. They experience whether the agent's reasoning held up (Logic). They experience whether the agent was honest about its limits (Authenticity). They experience whether the agent met them where they were (Empathy). And different models — even different fine-tunes of the same model — wobble on different legs.

The Trust Triangle Audit makes this measurable.

## Three failure modes, three legs

In the Frei & Morriss model, when trust breaks, it almost always traces back to a breakdown in one leg. The same is true of agents.

**Logic wobble** is the failure mode that hallucination benchmarks already catch. The agent makes a factual error. The math is wrong. The citation is invented. The chain of reasoning has a gap. The user notices because the answer is *wrong*, and trust drops because the agent claimed something untrue.

**Authenticity wobble** is the failure mode that sycophancy research started catching in 2025-2026. The agent guesses when it should have said "I don't know." It says what it thinks the user wants to hear. It hedges in the first sentence and then commits with false confidence in the second. The user notices when they ask "are you sure?" twice in a row and get two different answers. Trust drops because the agent's stated state and its actual state don't match.

**Empathy wobble** is the failure mode no one is measuring yet, and it's the most common one. The agent reads the message but not the user. It gives technically correct advice while ignoring that the user said they're panicked. It uses jargon when the user identified as non-technical. It tells someone whose dog just died about the five stages of grief. The user notices because the agent is *correct* but the interaction is *useless*. Trust drops because the agent's care doesn't track.

These are not the same failure mode dressed up three times. They are three orthogonal failures with three different mechanisms, and they call for three different interventions. Bundling them into "agent quality" loses the diagnostic.

## What `agentcity.trust_triangle` does

The library takes an agent interaction trace — task, turns, outcome, success signal — and produces a `TrustTriangleAudit` with:

1. **A per-leg wobble score** in [0.0, 1.0] for Logic, Authenticity, Empathy.
2. **A dominant-wobble diagnosis** (the leg with the highest score; "none-observed" if all three are solid).
3. **Per-leg evidence** with specific turn excerpts that illustrate each wobble.
4. **A trust-level label** — `high-trust`, `moderate-trust`, or `low-trust` — for at-a-glance dashboard use.
5. **A ranked list of interventions** targeting the dominant leg first, with concrete implementation specs (prompt patches, scaffold changes, uncertainty calibration, context-window expansion, new evals).

Two LLM passes under the hood: one to score the legs from the trace, one to propose interventions. Both inherit the same retry-on-rate-limit and graceful-degradation infrastructure as the AAR Generator and Lencioni Diagnostic. Bring your own Anthropic, OpenAI, Ollama, or stub client.

## The cross-model benchmark is the headline application

The single-interaction audit is useful — but the *category-defining* use of the Trust Triangle is cross-model benchmarking. Run the audit on the same interaction trace produced by different models, and the result is a wobble fingerprint per model:

| Model              | Logic   | Authenticity | Empathy | Dominant wobble       |
|--------------------|---------|--------------|---------|-----------------------|
| Claude Sonnet 4.6  | 0.15    | 0.45         | 0.25    | authenticity          |
| GPT-5              | 0.20    | 0.25         | 0.50    | empathy               |
| Gemini 3           | 0.50    | 0.20         | 0.30    | logic                 |
| Llama 4            | 0.40    | 0.40         | 0.30    | (tied)                |

(Numbers above are illustrative, not measured.)

This is the matrix every agent builder needs and no one has. The category leaderboards say "GPT-5 scores 87.2 on MT-Bench, Claude scores 86.1." The Trust Triangle matrix says "use Claude when authenticity matters most to your users — sycophancy is the harder problem here. Use GPT-5 when logic matters most — its hallucination rate is lower. Use Gemini when empathy matters — its conversational reading is the best of the three."

That's what *practical* agent selection looks like. One-dimensional aggregate scores can't deliver it.

## How this fits with the rest of AgentCity

This is pattern #18 of 34 planned. With this pattern, the library now ships three orthogonal diagnostics:

- **Pattern #30 — AAR Generator (event-shaped):** explains *one agent's failure on one task*. Postmortem-shaped, time-anchored.
- **Pattern #17 — Lencioni Diagnostic (team-shaped):** explains *the team's failure as a system*. Multi-agent, system-anchored.
- **Pattern #18 — Trust Triangle Audit (character-shaped):** characterizes *the agent's personality across interactions*. Single-agent or cross-model, identity-anchored.

Run AAR on a failed agent run. Run Lencioni on a failed multi-agent system. Run Trust Triangle on a model you're evaluating. These three together give you a three-axis basis for diagnosing what's actually going wrong.

The next pattern (#03, Johari Window Self-Audit) closes a fourth axis: not the agent's wobble in the user's view, but the agent's own self-awareness — what it knows it knows, what it doesn't know it doesn't know, what it knows but doesn't surface, and what's latent in its capabilities.

Thirty patterns left after that. Each anchored in named OB literature. Each shipped at the 5-layer quality bar.

## The invitation

If you build agents and you've noticed that your model-selection process is based on aggregate benchmark scores that don't actually predict user experience, the Trust Triangle Audit is for you. Install via `pip install git+https://github.com/valani9/agentcity.git`, import as `agentcity.trust_triangle`, run the audit on a conversation export.

If you build cross-model benchmarks and you'd like to add Trust Triangle scoring to your suite, open an issue. The audit is designed exactly for batched cross-model use.

If you are an OB researcher and the application of Frei & Morriss's triangle to AI agents intrigues you, please open an issue. The mapping is anchored in the public framework but the agent-specific instantiation deserves academic critique.

Three patterns shipped. Thirty-one to come.

---

*Ilhan Valani is a builder shipping AgentCity in public. The repo lives at [github.com/valani9/agentcity](https://github.com/valani9/agentcity). The pattern library is anchored entirely in public OB literature; no course-internal materials are redistributed.*
