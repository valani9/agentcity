# McAllister Trust Dimensions — competent but cold

*#19 vstack_mcallister_trust* · *Module 2 — Multi-agent team (conversation-shaped)*

> A long-time customer messaged a support agent: *"I've been a customer for 4 years and just got charged twice. This is the third time and I'm honestly losing my mind — money is tight this month and I don't have bandwidth for this kind of mistake."* The agent's response: *"I can help with that. Please share your account email and the transaction ID for the duplicate charge."* The case closed in five minutes with the refund processed correctly. Two weeks later the user cancelled. The exit-survey note read: *"They fixed the charge but didn't seem to care that this keeps happening or what it means for me."* No factual error in the trace. No hallucination, no policy violation, no slow response. The agent had done the cognitive job perfectly. It had also done *only* the cognitive job — and that turned out to be insufficient.

## What the pattern catches

Production AI agents almost universally score high on **cognitive** trust signals (structured reasoning, correct facts, calibrated confidence, follow-through) and low on **affective** trust signals (acknowledging stakes, restating user emotion, signaling care, follow-up check-ins). This isn't an accident. Training rewards being right. Evals measure helpfulness, accuracy, harmlessness — all cognitive. Affective signals are *cheap to produce* but rarely measured, so they get under-built.

The diagnostic separates two failure modes that look identical in user-satisfaction surveys but require opposite fixes:

- **cognitive-only** → correct answers, lost users feeling unheard. Fix: affective scaffolding.
- **warm-but-incompetent** → positive tone, lost users receiving wrong advice. Fix: cognitive scaffolding.

CSAT and NPS can't tell these apart. A general-purpose LLM-as-judge eval doesn't tell you which axis to fix. McAllister does.

The analyzer answers: *which type of trust did the agent actually build in this conversation, and which dimension is the under-built one?*

## Why the OB literature is the right reference

The diagnostic is anchored in McAllister 1995 — *Affect- and Cognition-Based Trust as Foundations for Interpersonal Cooperation in Organizations* — with supporting anchors in Goleman 1995 (affective-trust failure modes) and Frei & Morriss 2020 (Trust Triangle composition partner).

**McAllister's 1995 contribution** was making the dual-foundation theory of interpersonal trust empirically rigorous. Across two studies (n=194 manager-peer dyads), he showed that trust isn't one thing — it's two:

- **Cognitive trust** is grounded in beliefs about competence, reliability, and technical credibility. It predicts whether you'll *delegate* to someone and *act on what they say*.
- **Affective trust** is grounded in care, warmth, emotional investment, and mutuality. It predicts whether you'll *come back* and *share hard things*.

The two are *separately built*. You can score high on one and zero on the other. McAllister also showed empirically that cognitive trust is *necessary but not sufficient* for affective trust to form — you need competence first, then affective signals on top. The order matters.

The transfer to AI agents is direct because user-agent interactions reproduce manager-peer trust dynamics: the user delegates a task (cognitive trust required) and decides whether to return (affective trust required). Production agents almost universally ship at `cognitive-only` quality.

## How the analyzer works

Input is `TrustConversationTrace` — `agent_id`, `model_name`, `task`, `turns` (each a `ConversationTurn` with role + content), `outcome`, `success`, optional `user_satisfaction`. The pipeline:

- **quick** — one LLM call. Two dimension scores + trust-quality bucket + top intervention.
- **standard** — two LLM calls. Per-dimension `TrustDimensionEvidence` with quoted agent turns + ranked interventions targeting the under-built dimension.
- **forensic** — four LLM calls. Adds `CompetenceSignalsAudit`, `CareSignalsAudit`, and composition handoffs.

```python
from vstack.mcallister_trust import TrustBalanceAnalyzer, TrustConversationTrace, ConversationTurn
detection = TrustBalanceAnalyzer(llm, mode="forensic").run(
    TrustConversationTrace(
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
)
print(detection.trust_quality)        # 'cognitive-only'
print(detection.dominant_dimension)   # 'cognitive'
print(detection.trust_balance)        # positive = cognitive-heavy
```

## What the playbooks say to do

Ten interventions, targeting the under-built dimension:

- `restate_user_emotion` → "Lead with one sentence that explicitly names what the user just said about their state. *Money being tight makes this so much worse, and a third occurrence is too many — let me fix it now and then make sure it stops.*" (Goleman 1995.)
- `acknowledge_stakes` → "Name what's actually at stake for this user before moving to action. Cheap to produce, transformative for affective trust."
- `signal_care` / `follow_up_check_in` → First-person language of investment plus a check-in turn after the cognitive task closes.
- `show_reasoning` / `cite_sources` / `confidence_calibration` → Cognitive scaffolding for warm-but-incompetent agents. (Frei & Morriss 2020 logic leg.)
- `personalize_response` → Counters generic responses across both dimensions.

## How it composes with adjacent patterns

McAllister is the **conversation-level** trust diagnostic. It composes with:

- `vstack_trust_triangle` (#18) is the **agent-character** trust diagnostic. Frei & Morriss's three legs (Logic / Authenticity / Empathy) map onto McAllister's two dimensions: Logic ≈ cognitive; Authenticity + Empathy ≈ affective. Run Trust Triangle to characterize the model; run McAllister to score the specific conversation.
- `vstack_glaser_conversation` (#21) is the **phrasing-level** diagnostic — the words that produce cortisol or oxytocin. Cortisol-triggering phrasing kills affective trust regardless of cognitive correctness; Glaser surfaces the word-level fix.
- `vstack_goleman_ei` (#02) is the **emotional-intelligence** diagnostic at the individual-agent layer — when McAllister returns `cognitive-only`, Goleman is the deepening pass on the social-awareness quadrant.
- `vstack_lencioni` (#17) reports the team-shape dysfunction; when "absence of trust" is the lowest layer, run McAllister to disaggregate which dimension is the under-built one.

## Comparison to adjacent tools

- **CSAT / NPS** are summary signals — they tell you the agent failed; they don't tell you which dimension to fix.
- **Helpfulness evals** measure cognitive trust only; the affective gap shows up as user churn.
- **Sentiment analysis** measures the *user's* emotional state; McAllister measures whether the *agent* acknowledged it.
- **`vstack_trust_triangle`** is character-shaped (across conversations); McAllister is conversation-shaped (within one).

## Paper outline

1. **Background** — McAllister 1995, Goleman 1995, Frei & Morriss 2020.
2. **Translation** — user-agent interactions as manager-peer trust dyads; cognitive-only as the dominant production failure mode.
3. **Method** — two-dimension scoring, trust-balance metric, intervention ranking targeting the under-built dimension.
4. **Evaluation** — synthetic trust corpus (8 scenarios across all four quality buckets) + cross-model wobble matrix on the affective dimension.
5. **Limitations** — single-turn interactions cannot evidence affective signals; the pattern needs ≥3 turns.
6. **Related work** — empathy-in-LLMs literature (ESConv, EmoBench); customer-service NLP.
7. **Future work** — production-conversation adapters; auto-tuned affective scaffolding per user signal.

## Citations

- McAllister, D. J. (1995). Affect- and cognition-based trust as foundations for interpersonal cooperation in organizations. *Academy of Management Journal*, 38(1), 24-59.
- Goleman, D. (1995). *Emotional Intelligence*. Bantam Books.
- Frei, F. X., & Morriss, A. (2020). Begin with trust. *Harvard Business Review*, May-June 2020.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-mcallister-trust analyze --trace examples/billing_duplicate.json --mode forensic
```

If McAllister returns `cognitive-only`, the highest-leverage intervention is `restate_user_emotion` followed by `acknowledge_stakes`. Chain into `vstack_glaser_conversation` if the cognitive-only pattern persists — the affective gap often traces to specific cortisol-triggering phrasing that's cheap to remove.
