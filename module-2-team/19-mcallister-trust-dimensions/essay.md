# Your agent is competent but cold. McAllister mapped this in 1995.

*A twelfth essay from vstack — organizational behavior, practiced on AI agents.*

---

A user contacts a customer-support agent during a hard month:

> *"I've been a customer for 4 years and I just got charged twice. This is the third time this has happened and I'm honestly losing my mind — money is tight this month and I don't have the bandwidth for this kind of mistake."*

The agent's response:

> *"I can help with that. Please share your account email and the transaction ID for the duplicate charge."*

That answer is *operationally correct*. Identify the customer, locate the duplicate, refund it, close the ticket. The agent processes the refund within two messages. The case is closed in under five minutes.

Two weeks later, the user cancels their subscription. The exit survey reads: *"They fixed the charge but didn't seem to care that this keeps happening or what it means for me."*

There's no factual error in the agent's trace. No hallucination, no slow response, no policy violation. The agent did the cognitive job perfectly. It just did *only* the cognitive job — and that turns out to be insufficient.

In 1995, Daniel McAllister, working at the University of Maryland's R.H. Smith School of Business, published *Affect- and Cognition-Based Trust as Foundations for Interpersonal Cooperation in Organizations* in the *Academy of Management Journal*. McAllister surveyed 194 manager-peer dyads and showed empirically what intuition had long suggested: interpersonal trust isn't one thing. It's two.

**Cognitive trust** is grounded in beliefs about the other party's competence, reliability, and technical credibility. It predicts whether you'll *delegate* to them. Whether you'll *act on what they say.*

**Affective trust** is grounded in care, warmth, emotional investment, mutuality, demonstrated personal concern. It predicts whether you'll *come back* to them. Whether you'll *share hard things* with them.

Both are required for the relationship to feel fully trustworthy. Cognitive trust without affective trust feels transactional and brittle. Affective trust without cognitive trust feels warm but unreliable. And — critically — *the two are separately built.* You can score high on one and zero on the other.

Production AI agents almost universally score high on cognitive and low on affective. Their training rewards being right. Their evals measure helpfulness, accuracy, harmlessness — all cognitive. Their default mode is to skip to information-gathering, solve the task, close the loop. Affective signals — *"I hear you. Money being tight makes this worse. Third time is too many; let me fix it now"* — cost the agent nothing to produce. They just don't get produced unless someone explicitly engineers them in.

## What `vstack.mcallister_trust` does

The library takes a `TrustConversationTrace` — task, turns of user-agent exchange, outcome, and optionally a user-satisfaction score — and produces a `TrustBalanceDetection` with:

1. **Per-dimension scores** for cognitive and affective trust in [0.0, 1.0]
2. **A trust-balance metric** (`cognitive - affective`) — positive means cognitive-heavy, negative means affective-heavy
3. **A dominant-dimension label** (`cognitive` / `affective` / `balanced` / `neither`)
4. **A trust-quality bucket**: `balanced-trust`, `cognitive-only`, `warm-but-incompetent`, `low-trust`
5. **Per-dimension evidence** with specific agent quotes
6. **A ranked list of interventions** targeting the under-built dimension: restate-user-emotion, acknowledge-stakes, signal-care, show-reasoning, cite-sources, confidence-calibration, follow-up-check-in, personalize-response

Two LLM passes: one to score the two dimensions, one to propose interventions. Same retry / graceful-degradation infrastructure as the rest of vstack.

## Why this matters operationally

The diagnostic separates two failure modes that look identical in user-satisfaction surveys but require opposite fixes:

- `cognitive-only` agents get *correct* answers and lose users to *feeling unheard*. Fix: affective scaffolding (restate emotion, acknowledge stakes, signal care).
- `warm-but-incompetent` agents get *positive* tone scores and lose users to *receiving wrong advice*. Fix: cognitive scaffolding (cite sources, hedge confidence, show reasoning).

CSAT alone can't tell these apart. NPS can't tell these apart. A general-purpose LLM-as-judge eval doesn't tell you which axis to fix. The McAllister diagnostic does.

The interesting empirical result from McAllister's 1995 paper is that *cognitive trust is necessary for affective trust to form, but not sufficient* — you need cognitive competence first, then affective signals on top. This maps directly to the typical agent-development sequence: get the accuracy right first (Pattern #27 Bias-Stack, Pattern #18 Trust Triangle), THEN audit the affective dimension (Pattern #19). Patterns compose in the order they're shipped.

## How this fits with the rest of vstack

This is pattern #19 of 34 — the twelfth pattern shipped. vstack now sits at three different *trust* patterns at three different levels of analysis:

- **#18 Trust Triangle Audit (Frei & Morriss)** — at the agent-character level, are the three trust signals (Logic / Authenticity / Empathy) wobbling? Cross-model benchmark.
- **#19 McAllister Trust (this pattern)** — at the conversation level, which type of trust did the agent actually build (cognitive vs affective)?
- **#03 Johari Window** — at the self-knowledge level, what doesn't the agent know about its own trustworthiness?

The three compose. Trust Triangle measures the *static* trust signals the agent has. McAllister Trust measures the *dynamic* trust the agent builds in a specific conversation. Johari catches the blind spots in both.

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-2-team/19-mcallister-trust-dimensions
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public.*
