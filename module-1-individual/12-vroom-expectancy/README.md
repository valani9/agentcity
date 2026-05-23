# Pattern #12 — Vroom Expectancy Calculator

**Layer:** Module 1 — Individual
**Status:** Shipped
**Package:** `agentcity.vroom_expectancy`

Victor Vroom's expectancy theory of motivation (*Work and Motivation*,
1964) applied to AI agents. Motivation = Expectancy × Instrumentality
× Valence. Multiplicative — if any term collapses, motivation
collapses.

## The framework

Three independent beliefs, multiplicative product:

- **Expectancy** [0, 1] — Will my effort produce performance? "Can I do this?"
- **Instrumentality** [0, 1] — Will my performance produce outcome? "Will this matter?"
- **Valence** [-1, 1] — Is the outcome something I value?

`MOTIVATION = E × I × V`. The product is computed **deterministically
in Python** — the LLM scores the three terms but cannot override the
math.

## Agent mapping

| Vroom term | AI agent manifestation |
| --- | --- |
| Expectancy | Sub-task scaffolding adequacy; task scope tractability |
| Instrumentality | "Will my output be read?" signal in the context |
| Valence | Purpose framing; user-benefit clarity; avoidance of boilerplate-quota |

## Files

- [`lib/schema.py`](lib/schema.py)
- [`lib/prompts.py`](lib/prompts.py)
- [`lib/generator.py`](lib/generator.py) — LLM scores E/I/V; Python computes the product
- [`demo/01_self_contained_demo.py`](demo/01_self_contained_demo.py) — Sprawling task + no-review signal demo
- [`eval/synthetic_vroom_traces.yaml`](eval/synthetic_vroom_traces.yaml) — 6 scenarios across bottleneck terms
- [`eval/run_benchmark.py`](eval/run_benchmark.py)
- [`tests/test_vroom_expectancy.py`](tests/test_vroom_expectancy.py)

## Quick start

```python
from agentcity.vroom_expectancy import (
    AgentExpectancyTrace, VroomExpectancyCalculator,
)
from agentcity.aar.clients import AnthropicClient

trace = AgentExpectancyTrace(
    agent_id="code-agent",
    task="Debug the entire codebase.",
    task_class="code_generation",
    system_prompt="Review all 200 files; no one will review carefully.",
    observed_behaviors=["Agent quit after 5 files."],
    effort_signals=["Stopped at 2.5% of scope."],
    outcome="Bugs unfound.",
    success=False,
)
detection = VroomExpectancyCalculator(AnthropicClient()).run(trace)
print(detection.to_markdown())
```
