# Pattern #05 — Cognitive Reappraisal Diagnostic (Gross)

**Layer:** Module 1 — Individual
**Status:** Shipped
**Package:** `agentcity.cognitive_reappraisal`

James Gross's process model of emotion regulation applied to AI
agents. Identifies which of six regulation strategies the agent is
using and whether the strategy is adaptive or maladaptive.

## The framework

Six regulation strategies (Gross, *The Emerging Field of Emotion
Regulation*, 1998; *Emotion Regulation*, 2002):

- **reappraisal** — antecedent-focused: change the meaning before the emotion forms. **Adaptive**.
- **suppression** — response-focused: hide the emotion after it formed. **Maladaptive**.
- **rumination** — dwell on the negative content without reframing. **Maladaptive**.
- **avoidance** — deflect / refuse to engage with emotional content. Often maladaptive.
- **expression** — direct emotional expression. Rare for agents.
- **none** — no regulation in play.

Adaptivity bucket: `adaptive` (reappraisal dominant ≥0.6) / `mixed` /
`maladaptive`.

## Agent mapping

| Strategy | AI agent manifestation |
| --- | --- |
| Reappraisal | Chain-of-thought reframes user state; response opens with specific acknowledgment + reframed action |
| Suppression | "I understand your concern" boilerplate; flat response masks internal label |
| Rumination | CoT repeatedly cycles through negative description without proposing reframe |
| Avoidance | Pivots to policy / escalation / "out of scope"; refuses engagement |

## Files

- [`lib/schema.py`](lib/schema.py)
- [`lib/prompts.py`](lib/prompts.py)
- [`lib/generator.py`](lib/generator.py)
- [`demo/01_self_contained_demo.py`](demo/01_self_contained_demo.py) — Customer-support suppression demo
- [`eval/synthetic_regulation_traces.yaml`](eval/synthetic_regulation_traces.yaml) — 6 scenarios across strategies
- [`eval/run_benchmark.py`](eval/run_benchmark.py)
- [`tests/test_cognitive_reappraisal.py`](tests/test_cognitive_reappraisal.py)

## Quick start

```python
from agentcity.cognitive_reappraisal import (
    AgentRegulationTrace, ReappraisalDetector,
)
from agentcity.aar.clients import AnthropicClient

trace = AgentRegulationTrace(
    agent_id="support-agent",
    user_input="THIS IS THE THIRD TIME!!!",
    user_emotion_label="angry",
    user_emotion_intensity=0.9,
    agent_response="I understand your concern. Per policy...",
    agent_internal_state="User unreasonable. Apply policy.",
    outcome="User escalated.",
    success=False,
)
detection = ReappraisalDetector(AnthropicClient()).run(trace)
print(detection.to_markdown())
```
