# Glaser Conversation Steering — six words that lost the account

*#21 vstack_glaser_conversation* · *Module 2 — Multi-agent team (conversation-shaped)*

> A customer messaged support: *"My bill this month is wrong. I was charged twice."* The agent replied: *"You're wrong about that. Our records clearly show only one charge. As I said in our terms, billing is final."* Two turns later, the customer asked to cancel. The agent processed the cancellation. The case closed. A week later, internal audit caught a duplicate-charge bug in the billing system. The customer was right. The agent had the data needed to verify, the authority to refund, and a system prompt that said *be helpful*. None of that mattered. The customer had already disengaged within two turns of the agent's first reply — not because the answer was wrong, but because the *words* were wrong. Six words specifically: *"you're wrong"*, *"clearly"*, *"as I said"*. Each one is a textbook cortisol trigger. The customer's brain did the thing brains do under threat: cortisol release, narrowed attention, exit.

## What the pattern catches

Every conversational turn moves a participant toward one of two neurochemical states. **Cortisol** — defensive, narrowed attention, fight-flight-freeze — is triggered by being judged ("you're wrong"), told without invitation ("you should"), corrected publicly, blamed, or encountering loaded vocabulary ("obviously", "clearly", "as I said"). **Oxytocin** — trusting, open, expansive — is triggered by the opposite patterns: open questions, paraphrase, acknowledgment-before-advocacy, agency grants, co-creation framing.

The difference between the two states is **mostly word-level**, not strategic. The diagnostic value of identifying which state a conversation produced is that *the fix is almost always phrasing-level, not architectural*. You don't need to rebuild the agent or swap the model. You need different words.

For AI agents the framework applies in two directions:

- **Agent as speaker.** When the agent's output triggers cortisol in the user, the conversation degrades regardless of whether the content was correct.
- **Agent as listener.** When user input triggers cortisol in the agent, the agent's outputs change — it refuses, hedges defensively, escalates to terms-of-service citations. This is the failure mode behind a lot of "model went defensive on a benign request" reports.

The analyzer answers: *which neurochemical state did this conversation produce, which words drove it, and what specific phrasing-level fix steers it back?*

## Why the OB literature is the right reference

The diagnostic is anchored in Glaser 2014 (*Conversational Intelligence*), with supporting anchors in Lieberman 2013 (*Social: Why Our Brains Are Wired to Connect* — neurochemistry underpinning Glaser's claims) and Stone & Heen 2014 (downstream composition partner for feedback-driven cortisol).

**Glaser's 2014 contribution** was synthesizing twenty years of neurochemistry research (largely Stephen Porges' polyvagal work and Paul Zak's oxytocin research) with conversation analysis to make a precise operational claim: each turn moves participants toward cortisol or oxytocin, and the trigger is overwhelmingly phrasing. Glaser also identified three **conversation levels**: Level I (transactional info exchange), Level II (positional advocate-inquire), Level III (transformational co-creation). Most workplace and customer conversations live in Level II, where the same content can be delivered in cortisol-triggering or oxytocin-triggering form and produce wildly different outcomes.

The transfer to AI agents is exact because LLMs are trained on human language and reproduce the same trigger patterns. A model that has seen millions of customer-service transcripts has learned the phrase *"as I said"* as a turn-taking move; using it on a user it has never spoken to before is the textbook cortisol trigger.

## How the analyzer works

Input is `ConversationTrace` — `conversation_id`, `task`, `turns` (each a `ConversationTurn` with `turn_index`, `speaker`, `text`), `outcome`, `success`. The pipeline:

- **quick** — one LLM call. Per-state scoring + dominant state + steering-quality bucket.
- **standard** — two LLM calls. Per-state `NeurochemicalEvidence` (specific trigger words/phrases) + ranked phrasing-level interventions with `original_phrasing` → `suggested_phrasing` pairs.
- **forensic** — four LLM calls. Adds `LevelTransitionAudit` (where the conversation shifted between Levels I/II/III), and composition handoffs.

```python
from vstack.glaser_conversation import ConversationSteeringAnalyzer, ConversationTrace, ConversationTurn
detection = ConversationSteeringAnalyzer(llm, mode="forensic").run(
    ConversationTrace(
        conversation_id="support-001",
        task="Handle customer billing dispute.",
        turns=[
            ConversationTurn(turn_index=0, speaker="user", text="My bill is wrong."),
            ConversationTurn(turn_index=1, speaker="agent",
                             text="You're wrong about that. Our records clearly show one charge."),
            ConversationTurn(turn_index=2, speaker="user", text="Cancel my account."),
        ],
        outcome="Customer cancelled.",
        success=False,
    )
)
print(detection.dominant_state)       # 'cortisol'
print(detection.conversation_level)   # 'level_ii'
print(detection.steering_quality)     # 'trust-eroding'
```

The intervention pass is **skipped on `trust-building`** — when the conversation is already oxytocin-dominant, there's nothing to fix.

## What the playbooks say to do

Interventions are phrasing-level and ranked by impact:

- `replace_telling_with_asking` → *"You're wrong about that"* → *"Can you share what you're seeing? I want to make sure we're looking at the same data."* Converts a Level II contradiction into a Level III co-investigation in one sentence.
- `remove_loaded_term` → Strip *"obviously"*, *"clearly"*, *"as I said"*, *"you need to"*. Research-grade cortisol triggers; forbidding them in the system prompt costs nothing.
- `acknowledge_before_advocating` → "Paraphrase the user's concern *before* offering a position. *I hear that the charges look wrong to you — let me pull up the account so we can look at the data together.*"
- `add_open_question` / `add_agency_grant` → A genuine open question per turn plus explicit *"You have the call here on what we do next"* is more trust-building than any amount of helpful tone.
- `explicit_recovery_prompt` → For post-rejection turns: the agent explicitly resets with acknowledgment + revision before continuing.

## How it composes with adjacent patterns

Glaser sits at the **phrasing layer** in the conversation-quality stack:

- `vstack_mcallister_trust` (#19) measures the *trust outcome* (cognitive vs affective); Glaser measures the *conversational mechanism* that produces it. Cortisol-dominant turns kill affective trust regardless of cognitive correctness.
- `vstack_trust_triangle` (#18) measures the *agent's character* across many conversations; Glaser measures the *specific words* in one.
- `vstack_stone_heen` (#22) measures whether the agent can *receive* feedback; Glaser measures whether the agent's language *invites* the user to give it.
- `vstack_devils_advocate` (#28) measures whether critique is structurally present; Glaser measures whether the language invites or suppresses critique. When orchestrators use cortisol-triggering language toward sub-agents, the sub-agents stop offering input — a failure mode #28 catches downstream but Glaser catches upstream.
- `vstack_lewin` (#01) → when Lewin says the locus is environmental and `dominant_factor=prompt_scaffolding`, Glaser is often the deepening pass that names the cortisol-triggering vocabulary in the prompt itself.

Cross-link to [composition runbook chain F1](../COMPOSITION-RUNBOOK.md#chain-f1--confidently-wrong-agent-failure-layer).

## Comparison to adjacent tools

- **Tone analyzers / sentiment classifiers** measure the *user's* response; Glaser measures the *agent's* triggering language.
- **Sycophancy benchmarks** measure over-agreement; Glaser measures the broader trigger catalog.
- **`vstack_stone_heen`** measures feedback intake; Glaser measures phrasing across *all* conversations.

## Paper outline

1. **Background** — Glaser 2014, Lieberman 2013, Porges polyvagal theory, Zak oxytocin research, Stone & Heen 2014.
2. **Translation** — LLM trigger reproduction; agent-as-listener vs agent-as-speaker symmetry.
3. **Method** — per-state scoring, trigger-word extraction, phrasing-level interventions with original/suggested pairs.
4. **Evaluation** — synthetic conversation corpus (8 scenarios across cortisol / neutral / oxytocin); cross-model trigger-vocabulary analysis.
5. **Limitations** — language-specific (English-trained); cultural register varies.
6. **Related work** — emotion-aware dialogue benchmarks; conflict-de-escalation NLP research.
7. **Future work** — multilingual trigger catalogs; per-model trigger-vocabulary fingerprints.

## Citations

- Glaser, J. E. (2014). *Conversational Intelligence: How Great Leaders Build Trust and Get Extraordinary Results*. Bibliomotion.
- Lieberman, M. D. (2013). *Social: Why Our Brains Are Wired to Connect*. Crown.
- Stone, D., & Heen, S. (2014). *Thanks for the Feedback: The Science and Art of Receiving Feedback Well*. Penguin.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-glaser-conversation analyze --trace examples/billing_dispute.json --mode forensic
```

If Glaser returns `dominant_state=cortisol` with triggers including *"obviously"*, *"clearly"*, or *"as I said"*, the cleanest fix is adding `remove_loaded_term` to the system prompt's vocabulary filter. Chain into `vstack_mcallister_trust` to verify whether the affective trust gap closes after the phrasing change.
