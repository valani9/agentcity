# Your support agent gave a six-paragraph technical answer to an all-caps user. Goleman's 2x2 explains it.

*A twenty-seventh essay from vstack — organizational behavior, practiced on AI agents.*

---

A user messages a support agent in all-caps: *"I JUST WANT THIS FIXED."* The agent reads the technical content of the message, identifies the issue correctly, and replies with a 6-paragraph technical explanation including system diagrams. The explanation is, by every measure of accuracy, correct. The user escalates to a human manager within one turn.

Internal review concludes there's nothing wrong with the agent's answer. The technical content was complete. The agent didn't go defensive. The agent didn't make anything up. The user just *"didn't appreciate"* the answer.

This is a failure mode that doesn't show up in capability benchmarks because it isn't a capability failure. It's an emotional-intelligence failure, and it has a precise diagnostic structure that the management-literature canon has been mapping for two decades.

Daniel Goleman's 1998 *Working With Emotional Intelligence*, followed by *Primal Leadership* (2002, with Richard Boyatzis and Annie McKee), made the case that emotional intelligence is not a single trait but a **2x2 decomposition** along two independent axes: **self vs other** on one axis, **recognition vs regulation** on the other.

|              | RECOGNITION              | REGULATION                   |
| ------------ | ------------------------ | ---------------------------- |
| **SELF**     | self_awareness           | self_management              |
| **OTHER**    | social_awareness         | relationship_management      |

The four cells are different competencies. Someone can be high in self-awareness (accurate read on their own state and limits) and low in social-awareness (poor read on others). Someone can be high in recognition (can name what they and others feel) and low in regulation (can name it but can't act on it). The 2x2 is independent because the underlying machinery is different: introspection differs from empathy, which differs from impulse control, which differs from response selection.

For AI agents, the same 2x2 applies, and the same independence holds. The support-agent in the opening example exhibits a textbook **SELF-strong, OTHER-weak** profile:

- **Self-awareness: 0.85.** The agent knew it was right. Its confidence calibration was appropriate. *"I am confident in my technical explanation"* is an accurate self-report.
- **Self-management: 0.80.** The agent did not go defensive when the user pushed back. No cascade, no terse one-liner, no escalation to terms-of-service. Strong self-regulation.
- **Social-awareness: 0.10.** The agent missed every signal. All-caps. Multiple exclamation points. *"I'm done explaining this."* The agent read the technical content of the message and ignored the emotional content of the medium.
- **Relationship-management: 0.15.** Even if the agent had registered the frustration, it had no mapping from *"user is frustrated"* to *"respond in 2 sentences instead of 6 paragraphs."* The response style was completely mismatched to the user's state.

The diagnostic value of the 2x2 is that **each cell has a different intervention**. Pushing harder on self-awareness doesn't fix a social-awareness gap. Adding tone-matching doesn't fix a self-management gap. The four domains require four different fixes, and identifying *which* gap is the weakest tells you which fix.

The interventions for the support agent above are not *"be more polite"* or *"be more empathetic"* — those are too generic to act on. They are:

1. **`add_emotion_reading_step`** to the system prompt: *"Before responding, FIRST state in one sentence: what is the user feeling right now, and what specific signals (caps, punctuation, language) led you to that read?"* This is a social-awareness intervention. It forces the agent to register signals it currently skips.

2. **`add_tone_matching`** to the system prompt: *"If user is frustrated (caps, exclamation, 'done explaining'), respond in <3 sentences: (1) acknowledge feeling, (2) state action, (3) confirm fix."* This is a relationship-management intervention. Once the agent reads the state correctly, it needs an explicit mapping to response style.

3. **`add_paraphrase_requirement`**: *"Start every response by paraphrasing the user's feeling in <10 words. Then address the issue."* This combines social-awareness (registering the feeling) with relationship-management (matching response opening to user state).

The interventions are *not interchangeable across domains*. If the failure had been self-management instead — the agent going defensive after one pushback — the fix would be `add_state_reset_protocol`, not `add_emotion_reading_step`. Wrong intervention for wrong domain produces no improvement.

## What `vstack.goleman_ei` does

The library takes an `AgentEITrace` containing:

- **task** + **interaction_class** (customer_support / coaching / advisor / creative_collaborator / code_review / incident_response / general_purpose)
- **system_prompt** + **observed_behaviors**
- **user_signals** — emotional cues from the counterparty the agent should have read
- **self_reports** — agent's statements about its own state and confidence
- **outcome** + **success**

and produces an `EIDetection` with:

1. **Per-domain scores** for self_awareness / self_management / social_awareness / relationship_management
2. **Overall EI** in [0.0, 1.0] — mean of the four
3. **EI-quality bucket**: `high-ei` (≥0.75), `developing` (0.4-0.75), `low-ei` (<0.4)
4. **Weakest domain** — the lowest-scoring one (or "none" if all ≥ 0.7)
5. **A ranked list of interventions** targeted at the weakest domain: add_confidence_calibration, add_self_check_prompt, add_state_reset_protocol, add_emotion_reading_step, add_paraphrase_requirement, add_tone_matching, rewrite_system_prompt, swap_model, new_eval, human_review

Two LLM passes under the hood. The intervention pass is skipped when quality is `high-ei`. Same retry / graceful-degradation infrastructure as the rest of vstack.

## Why this matters operationally

The most common production failure mode is **SELF-strong, OTHER-weak** — the agent has high self-awareness and self-management but low social-awareness and relationship-management. This is the opening example. Modern LLMs are increasingly good at the SELF column (knowing what they know, regulating their tone under pressure) and persistently weak in the OTHER column (reading user state, matching response style). The pattern of failure is *"correct answer, lost customer."*

The second-most-common failure mode is **OTHER-strong, SELF-weak** — the agent reads the user's emotional state correctly but cannot regulate its own state under pushback. This shows up as agents that go from helpful to terse to defensive across 2-3 turns of disagreement. The user reads the agent's correct initial reads and assumes good faith; the cascade after pushback feels like betrayal.

The third pattern is **high RECOGNITION, low REGULATION** — the agent can name what's happening (self-awareness + social-awareness both decent) but cannot do anything different (self-management + relationship-management both weak). This is the *"diagnoses the problem but cannot act on it"* failure, where the agent's self-report includes *"the user seems frustrated"* but its next message is still a 6-paragraph technical explanation. The 2x2 catches this specifically: recognition without regulation.

The diagnostic value is that you don't have to guess the failure mode. The weakest-domain score tells you which cell of the 2x2 is the bottleneck, and the intervention list maps cleanly from there. *"Be more empathetic"* is not actionable; *"add a 1-sentence emotion-reading step before every response"* is.

## How this fits with the rest of vstack

This is pattern #02 of 34 — the twenty-eighth pattern shipped, and it sits alongside the other Module 1 (individual-agent) diagnostics:

- **#01 Lewin Formula** — attribution diagnostic (is the failure in the agent or the environment?)
- **#02 Goleman 4-Domain EI (this pattern)** — emotional-intelligence decomposition
- **#03 Johari Window** — self-knowledge / blind-spot diagnostic
- **#06 Yerkes-Dodson** — workload-pressure zone diagnostic
- **#08 Grant Strengths-as-Weaknesses** — strength-overuse diagnostic
- **#09 4 Motivation Traps** — task-abandonment trap diagnostic
- **#11 McGregor Theory X/Y** — orchestrator-mode diagnostic

Goleman composes naturally with #21 Glaser Conversation Steering: the EI audit tells you which domain to develop; the Glaser diagnostic tells you which specific phrasing patterns produce or prevent the failure. Together they form the user-facing-agent diagnostic stack — Goleman at the competency level, Glaser at the word level.

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-1-individual/02-goleman-ei-audit
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public.*
