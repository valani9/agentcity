# Pattern #34 — Span-of-Control / Centralization Calculator

**Layer:** Module 3 — Organization
**Status:** Shipped
**Package:** `agentcity.span_of_control`

Deterministic quantitative diagnostic of an AI agent crew's structural
load. Six metrics, all computed locally in Python — the LLM is used
only for qualitative intervention generation. **The math is locked.**

Pairs with [Pattern #33](../33-org-structure-matrix/) (LLM-driven
qualitative fit diagnostic): #33 tells you what fits the task class;
#34 tells you whether the math actually works under load.

## The framework

Six metrics computed deterministically from the agent roster +
reports_to edges + decision_authority + incoming_request_rate:

- **max_span** — widest supervisor span. >7 starts being problematic; >10 severe.
- **mean_span** — mean span across supervisors. >5 is heavy.
- **centralization_index** — fraction of decision authority concentrated in top supervisors. >0.6 concerning.
- **hierarchy_depth** — longest reports_to chain. >3 adds latency.
- **span_gini** — inequality across the span distribution. >0.4 imbalanced.
- **decision_bottleneck** — composite of span + full-authority + incoming load. >0.5 = single-point-of-failure under load.

Each metric has a value and a normalized score (0..1). The composite
load score is weighted toward `decision_bottleneck` (0.30) and `span_gini`
(0.20) because those are the failure modes that escalate under load.

## Agent mapping

| Org metric | AI agent crew interpretation |
| --- | --- |
| max_span | Orchestrator subordinate count under one boss |
| centralization_index | Effective parallelism = 1 / centralization |
| hierarchy_depth | Number of approval hops per commit |
| span_gini | Imbalance: one supervisor overwhelmed while another idle |
| decision_bottleneck | The agent whose failure stalls the crew |

## Design

- All six metrics computed in `lib/metrics.py`, no LLM in the math.
- One LLM pass for intervention generation, skipped when load quality
  is `well-balanced` (composite score < 0.3).
- LLM cannot modify metric values — it receives them as locked inputs.

## Files

- [`lib/schema.py`](lib/schema.py) — Pydantic models + Markdown formatter
- [`lib/metrics.py`](lib/metrics.py) — Deterministic metric computation (pure Python)
- [`lib/prompts.py`](lib/prompts.py) — `INTERVENTIONS_PROMPT` + system prompt
- [`lib/generator.py`](lib/generator.py) — `SpanLoadCalculator` orchestrator
- [`demo/01_self_contained_demo.py`](demo/01_self_contained_demo.py) — Overloaded orchestrator demo
- [`eval/synthetic_span_traces.yaml`](eval/synthetic_span_traces.yaml) — 5 scenarios across load profiles
- [`eval/run_benchmark.py`](eval/run_benchmark.py) — Corpus runner
- [`tests/test_span_of_control.py`](tests/test_span_of_control.py) — pytest suite (metric correctness + pipeline)

## Quick start

```python
from agentcity.span_of_control import (
    AgentNode,
    CrewLoadTrace,
    SpanLoadCalculator,
)
from agentcity.aar.clients import AnthropicClient

trace = CrewLoadTrace(
    crew_id="cs-crew",
    task="Handle 100 rpm support load.",
    agents=[
        AgentNode(agent_id="orchestrator", decision_authority="full"),
        *[
            AgentNode(
                agent_id=f"worker-{i}",
                reports_to=["orchestrator"],
                decision_authority="advisory",
            )
            for i in range(12)
        ],
    ],
    incoming_request_rate=100.0,
    outcome="Queue backed up.",
    success=False,
)
analysis = SpanLoadCalculator(AnthropicClient()).run(trace)
print(analysis.to_markdown())
```
