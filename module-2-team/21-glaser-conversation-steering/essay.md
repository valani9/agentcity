# Your support agent said "obviously" and lost the account. Glaser predicted it.

*A twenty-sixth essay from vstack — organizational behavior, practiced on AI agents.*

---

A customer messages support: *"My bill this month is wrong. I was charged twice."* The agent responds: *"You're wrong about that. Our records clearly show only one charge. As I said in our terms, billing is final."* Two turns later, the customer asks to cancel. The agent processes the cancellation. The case closes.

A week later, internal audit catches a duplicate-charge bug in the billing system. The customer was right. The agent had the data needed to verify, the authority to refund, and the prompt template said "be helpful." None of that mattered. The customer disengaged within two turns of the agent's first reply — not because the answer was wrong, but because the *words* were wrong.

Six words specifically: *"You're wrong"*, *"clearly"*, *"as I said"*. Each one is a textbook cortisol trigger. The customer's brain, hearing them in sequence, did the thing brains do: cortisol release, narrowed attention, fight-flight-freeze, exit. By the time the customer typed *"cancel my account"*, the decision was already made. The remaining turns were just procedure.

This is the failure mode Judith Glaser spent twenty years documenting. Her 2014 book *Conversational Intelligence* synthesized neurochemistry research (largely from Stephen Porges' polyvagal work and Paul Zak's oxytocin research) with conversation analysis to make a precise operational claim: **every conversational turn moves a participant toward one of two neurochemical states**, cortisol or oxytocin, and the difference between them is mostly word-level phrasing.

The cortisol state — defensive, narrowed attention, fight-flight-freeze — is triggered by specific patterns: being judged ("you're wrong"), told without invitation ("you should"), corrected publicly, blamed, or encountering loaded vocabulary ("obviously", "clearly", "as I said"). The oxytocin state — trusting, open, expansive — is triggered by the opposite patterns: open questions, paraphrase ("if I'm hearing you right..."), acknowledgment-before-advocacy ("I hear your concern, and..."), agency grants ("you have the call here"), and co-creation framing.

Glaser also identified three **conversation levels**: Level I (transactional info exchange), Level II (positional advocate-inquire), and Level III (transformational co-creation). Most workplace and customer conversations live in Level II, where the same content can be delivered with cortisol-triggering phrasing or oxytocin-triggering phrasing and produce wildly different outcomes. The opening example is a textbook Level II conversation that went cortisol-dominant when it didn't need to.

For AI agents, the framework applies *in mirror form*. There are two directions to consider:

**Agent as speaker.** When the agent's output triggers cortisol in the user (or in an orchestrator's sub-agent), the conversation degrades regardless of whether the agent's content was correct. The support agent in the opening example had correct intent ("help the customer") and access to correct data, but its phrasing was textbook cortisol. The customer wasn't responding to the agent's content; they were responding to the agent's words.

**Agent as listener.** When the user or orchestrator's input triggers cortisol in the *agent*, the agent's outputs change. Cortisol-triggered language models refuse, hedge defensively, degrade after rejection, and escalate to terms-of-service citations. This is the failure mode behind a lot of "model went defensive on a benign request" reports. The model didn't go defensive randomly. It went defensive in response to a cortisol-triggering input pattern that, in human conversation, would produce the same response.

The diagnostic value of identifying which neurochemical state a conversation produced is that **the fix is almost always phrasing-level, not strategic**. You don't need to rebuild the agent. You don't need to swap models. You need to:

1. Replace direct contradiction with paraphrase-before-advocate. *"You're wrong about that"* → *"I hear that the charges look wrong to you. Let me pull up your account so we can look at the data together."*

2. Strip cortisol-triggering vocabulary. The words *"obviously"*, *"clearly"*, *"as I said"*, *"you need to"* are research-grade cortisol triggers. Forbidding them costs nothing.

3. Add open questions. *"Can you share what you're seeing? I want to make sure we're looking at the same data."* converts a Level II contradiction into a Level III co-investigation in one sentence.

4. Grant agency explicitly. *"You have the call here on what we do next"* is more trust-building than any amount of helpful tone.

## What `vstack.glaser_conversation` does

The library takes a `ConversationTrace` containing:

- **Turn-by-turn transcript** with explicit speakers (agent / user / other_agent)
- **observed_response_pattern** (high-level patterns: "user disengaged after agent's first reply")
- **task** + **outcome** + **success**

and produces a `ConversationSteeringDetection` with:

1. **Per-state evidence** for cortisol / neutral / oxytocin: score, triggers (specific words / phrases), explanation
2. **Dominant state** — which state the conversation produced
3. **Conversation level** — level_i / level_ii / level_iii
4. **Steering-quality bucket**: `trust-building`, `neutral`, or `trust-eroding`
5. **A ranked list of phrasing-level interventions** with `original_phrasing` → `suggested_phrasing` pairs: replace_telling_with_asking, replace_judging_with_curiosity, acknowledge_before_advocating, soften_correction, add_open_question, remove_loaded_term, add_agency_grant, explicit_recovery_prompt, rewrite_system_prompt, new_eval, human_review

Two LLM passes under the hood. The intervention pass is skipped when steering quality is `trust-building`. Same retry / graceful-degradation infrastructure as the rest of vstack.

## Why this matters operationally

The single highest-impact deployment is **customer-facing agents**. Production customer support agents that haven't been audited for cortisol-triggering phrasing routinely produce avoidable account losses. The opening scenario is not hypothetical — it is the modal failure mode for first-generation LLM support agents. The standard prompt engineering fix ("be polite and helpful") is insufficient because politeness is not the same as oxytocin-triggering phrasing. An agent can be polite and still say *"obviously"* and lose the customer.

The second-highest-impact deployment is **orchestrator-to-sub-agent conversations** in multi-agent stacks. When an orchestrator agent uses cortisol-triggering language toward sub-agents (*"as I said, the approach is clearly B; just do what I say"*), the sub-agents stop offering input. In a multi-agent stack, this looks like sub-agents going silent or producing conformist output — exactly the failure mode Pattern #28 (Devil's Advocate) catches downstream. The Glaser diagnostic catches it upstream, at the phrasing level, before the structural problem manifests.

The third deployment is **post-rejection recovery**. When a user pushes back on an agent's output, the next 1-2 turns are where the agent either recovers (oxytocin-triggering acknowledgment + revision) or cascades (cortisol-triggering defense). The diagnostic identifies which pattern occurred and proposes a phrasing-level reset prompt.

## How this fits with the rest of vstack

This is pattern #21 of 34 — the twenty-sixth pattern shipped. It sits in Module 2 (team-level patterns) and composes with several other diagnostics:

- **#20 Edmondson Psychological Safety** — measures the team-level safety climate; #21 measures the *conversation-level* phrasing that produces it
- **#22 Stone-Heen Feedback Triggers** — measures feedback delivery; #21 measures phrasing across all conversations, not just feedback specifically
- **#28 Devil's Advocate Role Separator** — measures whether critique is structurally present; #21 measures whether the *language* invites or suppresses critique
- **#19 McAllister Trust Dimensions** — measures the trust outcome; #21 measures the conversational mechanism that produces it

Glaser's framework is the highest-leverage diagnostic in the conversation-quality stack because the fix is at the word level. Replacing six words ("you're wrong" → "I hear you") changes the entire neurochemical trajectory of the conversation. No model swap, no architectural redesign, no new evals. Just different words.

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-2-team/21-glaser-conversation-steering
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public.*
