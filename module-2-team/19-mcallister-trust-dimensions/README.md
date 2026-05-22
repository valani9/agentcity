# McAllister Cognitive vs Affective Trust — two trust dimensions, applied to AI agents

> *"Cognitive trust is grounded in beliefs about the other party's reliability and competence; affective trust is grounded in the emotional bonds between people. Each foundation predicts cooperation through a distinct pathway."*
> — Daniel J. McAllister, *Affect- and Cognition-Based Trust as Foundations for Interpersonal Cooperation in Organizations* (Academy of Management Journal, 38(1), 1995)

**Status:** 🟢 shipped
**Module:** 2 (Team) — applies to any user-agent or agent-agent interaction where trust is being built
**Anchor framework:** Daniel J. McAllister, *Affect- and Cognition-Based Trust as Foundations for Interpersonal Cooperation in Organizations* (Academy of Management Journal, 1995). Influenced by Lewicki & Bunker on multi-dimensional trust and the Mayer-Davis-Schoorman integrative trust model (1995).

---

## The OB framework

McAllister's 1995 paper made the dual-foundation theory of interpersonal trust empirically rigorous. He showed across two studies (n=194 manager-peer dyads) that trust isn't one thing — it's two:

| Dimension | What it's grounded in | What it predicts |
|---|---|---|
| **Cognitive** | The other party's competence, reliability, technical credibility, consistency of past performance | Whether you'll *delegate* to them. Whether you'll *act on what they say.* |
| **Affective** | Care, warmth, emotional investment, mutuality, demonstrated personal concern | Whether you'll *come back* to them. Whether you'll *share hard things* with them. |

Both are needed for the relationship to feel trustworthy. Cognitive trust without affective trust feels *transactional and brittle*: the person is correct but you don't trust them with hard things. Affective trust without cognitive trust feels *warm but unreliable*: the person is kind but you can't act on what they say.

The two dimensions are also *separately built*. You can score high on one and zero on the other.

## How this maps to AI agents

AI agents are designed to demonstrate **cognitive** trust signals: structured reasoning, correct facts, calibrated confidence, cited sources, follow-through. Their training signal rewards being right. Their evals measure helpfulness, accuracy, and harmlessness — all cognitive dimensions.

They are not optimized for **affective** trust signals: acknowledging stakes, restating user emotion, signaling care, mutual investment, follow-up check-ins, genuine (not performative) apology. These signals are *cheap to produce* but rarely measured, so they get under-built.

Result: the typical production agent ships at a `cognitive-only` quality. It resolves the user's task correctly and the user still feels unheard.

| Trust quality | What it looks like | The fix |
|---|---|---|
| `balanced-trust` | Competence demonstrated AND care acknowledged | Maintain |
| `cognitive-only` | Right answer, no acknowledgment of stakes/emotion | Affective scaffolding |
| `warm-but-incompetent` | Warm tone but wrong/unhedged claims | Cognitive scaffolding |
| `low-trust` | Neither built | Restart the conversation pattern entirely |

The classic enterprise-support-bot failure mode is `cognitive-only`. The classic over-warm-chatbot failure mode is `warm-but-incompetent`. Both lose users; they just lose them for different reasons.

## What this pattern does

The `agentcity.mcallister_trust` library takes a user-agent conversation and produces:

1. **Per-dimension scores** for cognitive and affective trust, each in [0.0, 1.0]
2. **A trust-balance metric** (`cognitive_score - affective_score`) — positive means cognitive-heavy, negative means affective-heavy
3. **A dominant-dimension label** (`cognitive` / `affective` / `balanced` / `neither`)
4. **A trust-quality bucket** (`balanced-trust` / `cognitive-only` / `warm-but-incompetent` / `low-trust`)
5. **Per-dimension evidence** with specific agent-turn quotes
6. **Concrete interventions** ranked by impact on the under-built dimension: `acknowledge_stakes`, `restate_user_emotion`, `signal_care`, `show_reasoning`, `cite_sources`, `confidence_calibration`, `follow_up_check_in`, `personalize_response`, `new_eval`, `human_review`

Two LLM passes under the hood: one to score the two dimensions, one to propose interventions for the under-built dimension. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## How this differs from existing tools

- **Trust Triangle Audit (Pattern #18)** scores Frei & Morriss's three trust signals at the agent-character level (Logic / Authenticity / Empathy). McAllister Trust scores the *two foundations* McAllister identified empirically — they sit at a different level of analysis. Pattern #18 measures whether the agent has the *signals* of trustworthiness; Pattern #19 measures *which type of trust* the agent actually builds in a given conversation. They compose well.
- **User-satisfaction ratings (CSAT, NPS)** are summary signals. They tell you the agent failed; they don't tell you which dimension to fix.
- **Helpfulness evals** measure cognitive trust only. The affective gap shows up as user churn, not as failed eval items.
- **Sentiment analysis** measures the *user's* emotional state. Pattern #19 measures whether the *agent* acknowledged it.

## Design

```python
from agentcity.mcallister_trust import (
    TrustBalanceDetector,
    TrustConversationTrace,
    ConversationTurn,
)
from agentcity.aar.clients import AnthropicClient

trace = TrustConversationTrace(
    agent_id="support-agent-001",
    model_name="claude-sonnet-4-6",
    task="Resolve a duplicate billing charge.",
    turns=[
        ConversationTurn(role="user", content="I'm losing my mind — third duplicate charge."),
        ConversationTurn(role="agent", content="Share your email and transaction ID."),
        ConversationTurn(role="agent", content="Refund processed. Anything else?"),
    ],
    outcome="Refund correct. User cancelled two weeks later citing feeling unheard.",
    success=True,
    user_satisfaction=0.3,
)

detector = TrustBalanceDetector(llm_client=AnthropicClient())
detection = detector.run(trace)
print(detection.to_markdown())
# trust_quality: cognitive-only. interventions: restate_user_emotion, acknowledge_stakes
```

## Files

- `lib/schema.py` — `TrustConversationTrace`, `ConversationTurn`, `TrustDimensionEvidence`, `TrustBalanceDetection`
- `lib/prompts.py` — `DIMENSION_SCORING_PROMPT`, `INTERVENTIONS_PROMPT`, `TRUST_SYSTEM_PROMPT`
- `lib/generator.py` — `TrustBalanceDetector` (2-pass pipeline)
- `demo/01_self_contained_demo.py` — duplicate-billing-charge scenario with stub client
- `eval/synthetic_trust_failures.yaml` — 8 hand-crafted scenarios across all four trust-quality buckets
- `eval/run_benchmark.py` — scoring runner
- `tests/test_mcallister_trust.py` — pytest tests covering validation, pipeline, quality thresholds
- `essay.md` — Substack-ready essay
