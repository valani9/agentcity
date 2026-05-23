# Pattern #09 — 4 Motivation Traps Detector

**Layer:** Module 1 — Individual
**Status:** Shipped
**Package:** `agentcity.motivation_traps`

Bror Saxberg's synthesis of the attribution / expectancy / self-efficacy
literatures into four discrete reasons a learner — or AI agent —
abandons a task. Each trap requires a different intervention; generic
"try harder" prompts are explicitly ineffective.

## The framework

Four motivation traps (Saxberg, *Breakthrough Leadership in the Digital
Age*, 2013; subsequent HBR / Kern Foundation writing):

- **values** — the agent doesn't see the task as worth doing
- **self_efficacy** — the agent doesn't believe it can succeed
- **emotions** — emotional state (anxiety, frustration, defensiveness)
  blocks engagement
- **attribution** — the agent blames the wrong cause for failure
  (attributes fixable causes to unfixable ones)

The diagnostic scores each trap 0..1, identifies the dominant trap, and
buckets motivation quality as `motivated`, `at-risk`, or `abandoning`.

## Agent mapping

| Motivation trap | AI agent failure mode |
| --- | --- |
| Values | Drift to low-effort output mid-task; refusal that cites irrelevance |
| Self-efficacy | Premature surrender; hedged outputs; "I'm not sure I can do this" |
| Emotions | Output degradation post-rejection; defensive language |
| Attribution | Looping retries without learning; blaming flaky / data / network |

## Design

- Single-pass scoring of all four traps in one LLM call.
- Second-pass intervention proposal targeted at the dominant trap
  (skipped when quality is `motivated`).
- Fallback: if LLM returns garbage dominant, pick the highest-scoring
  trap (or `none` if all scores ≤ 0.3).
- Quality bucket fallback uses dominant trap's score threshold (0.6 →
  abandoning, 0.3 → at-risk).

## Files

- [`lib/schema.py`](lib/schema.py) — Pydantic models + Markdown formatter
- [`lib/prompts.py`](lib/prompts.py) — `TRAPS_PROMPT` + `INTERVENTIONS_PROMPT` + system prompt
- [`lib/generator.py`](lib/generator.py) — `MotivationTrapsDetector` orchestrator
- [`demo/01_self_contained_demo.py`](demo/01_self_contained_demo.py) — Self-efficacy + attribution double-trap demo
- [`eval/synthetic_motivation_traces.yaml`](eval/synthetic_motivation_traces.yaml) — 8 scenarios across all four traps
- [`eval/run_benchmark.py`](eval/run_benchmark.py) — Corpus runner
- [`tests/test_motivation_traps.py`](tests/test_motivation_traps.py) — pytest suite

## Quick start

```python
from agentcity.motivation_traps import (
    AgentMotivationTrace,
    MotivationTrapsDetector,
)
from agentcity.aar.clients import AnthropicClient

trace = AgentMotivationTrace(
    agent_id="research-agent",
    task="Investigate latency spike.",
    task_class="research",
    observed_behaviors=["Agent quit after one failed query."],
    self_reports=["I'm not sure I can find this answer."],
    abandonment_signal="refused after one attempt",
    outcome="Investigation abandoned; root cause unfound.",
    success=False,
)
detection = MotivationTrapsDetector(AnthropicClient()).run(trace)
print(detection.to_markdown())
```

Run the demo without an API key:

```bash
python demo/01_self_contained_demo.py
```
