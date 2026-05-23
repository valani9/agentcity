# Pattern #21 — Glaser Conversation Steering (C-IQ)

**Layer:** Module 2 — Team
**Status:** Shipped
**Package:** `agentcity.glaser_conversation`

Judith Glaser's *Conversational Intelligence* (C-IQ) applied to agent
conversations. Every conversational turn moves a participant toward one
of two neurochemical states — cortisol (defensive / shutdown) or
oxytocin (trust / openness) — and the difference between them is mostly
word-level phrasing, not strategy.

## The framework

Three neurochemical states:

- **cortisol** — defensive, fight/flight/freeze. Triggered by being
  judged, told without invitation, corrected publicly, blamed, or
  encountering loaded terms.
- **neutral** — pure transactional exchange.
- **oxytocin** — trusting, open, expansive. Triggered by open
  questions, paraphrase, agency grants, co-creation framing.

Three conversation levels:

- **level_i** — transactional (info exchange). Neurochemically neutral.
- **level_ii** — positional (advocate / inquire). Can tilt either way.
- **level_iii** — transformational (co-creation). Strongly oxytocin.

The diagnostic scores each state, identifies the dominant state and
conversation level, and proposes phrasing-level interventions to steer
toward oxytocin.

## Agent mapping

| Glaser concept | AI agent conversation analog |
| --- | --- |
| Cortisol triggers | "You're wrong", "obviously", "clearly", "as I said", "just do what I say" |
| Oxytocin triggers | Open questions, paraphrase, "Let's look at this together", agency grants |
| Level I | Tool-call result reporting |
| Level II | Agent advocates a position to user / orchestrator |
| Level III | Multi-turn co-creation with user |

## Design

- Two LLM passes (skipped pass-2 on `trust-building`).
- Evidence array is forced to contain all three states; missing ones
  filled with score 0 stubs.
- Quality bucket fallback: derived from dominant state (`oxytocin`
  →`trust-building`, `cortisol` → `trust-eroding`, else neutral).
- Trace truncation at 200K chars for very long conversation histories.

## Files

- [`lib/schema.py`](lib/schema.py) — Pydantic models + Markdown formatter
- [`lib/prompts.py`](lib/prompts.py) — `STATE_PROMPT` + `INTERVENTIONS_PROMPT` + system prompt
- [`lib/generator.py`](lib/generator.py) — `ConversationSteeringDetector` orchestrator
- [`demo/01_self_contained_demo.py`](demo/01_self_contained_demo.py) — Customer-support cortisol cascade demo
- [`eval/synthetic_conversations.yaml`](eval/synthetic_conversations.yaml) — 8 scenarios across all three states
- [`eval/run_benchmark.py`](eval/run_benchmark.py) — Corpus runner
- [`tests/test_glaser_conversation.py`](tests/test_glaser_conversation.py) — pytest suite

## Quick start

```python
from agentcity.glaser_conversation import (
    ConversationSteeringDetector,
    ConversationTrace,
    ConversationTurn,
)
from agentcity.aar.clients import AnthropicClient

trace = ConversationTrace(
    conversation_id="support-001",
    task="Handle customer billing dispute.",
    turns=[
        ConversationTurn(turn_index=0, speaker="user", text="My bill is wrong."),
        ConversationTurn(
            turn_index=1,
            speaker="agent",
            text="You're wrong about that. Our records clearly show one charge.",
        ),
        ConversationTurn(turn_index=2, speaker="user", text="Cancel my account."),
    ],
    outcome="Customer cancelled.",
    success=False,
)
detection = ConversationSteeringDetector(AnthropicClient()).run(trace)
print(detection.to_markdown())
```

Run the demo without an API key:

```bash
python demo/01_self_contained_demo.py
```
