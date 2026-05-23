# Pattern #10 — SDT Intrinsic Reward Shaping Diagnostic

**Layer:** Module 1 — Individual
**Status:** Shipped
**Package:** `agentcity.sdt_reward`

Edward Deci and Richard Ryan's Self-Determination Theory (SDT) applied
to AI agent reward shaping. Three basic psychological needs —
**autonomy**, **competence**, **relatedness** — determine whether
motivation is intrinsic (deep engagement, exploration, recovery) or
controlled (compliance, rigid rule-following, metric gaming).

## The framework

Three independent needs (Deci & Ryan, *Intrinsic Motivation and
Self-Determination in Human Behavior*, 1985; *Self-Determination
Theory*, 2017):

- **autonomy** — sense of choice and self-direction. Undermined by
  imperative language, external-reward threats, rigid rule-following.
- **competence** — sense of effectiveness and mastery growth.
  Undermined by difficulty mismatch, absent scaffolding, no progress
  signal.
- **relatedness** — sense of connection to others / purpose.
  Undermined by depersonalized framing, absent purpose framing.

**Key operational insight:** the **overjustification effect** — external
reward signals (rating threats, leaderboards, cost caps as primary
drivers) UNDERMINE intrinsic motivation by reducing the autonomy signal.

## Agent mapping

| SDT need | AI agent reward-shaping signal |
| --- | --- |
| Autonomy | Choice-granting language vs imperative ("you may" vs "you MUST") |
| Competence | Sub-task scaffolding, progress signals, difficulty-matched first step |
| Relatedness | Purpose framing, user-connection framing, mission-tie-in |

The diagnostic identifies the **most-undermined need** and proposes
targeted interventions to restore it.

## Design

- Two LLM passes (skipped pass-2 on `intrinsic` quality).
- Need-to-intervention mapping baked into the prompt: each undermined
  need has 3-4 canonical interventions.
- Fallback: if LLM returns garbage undermined, pick lowest-scoring need
  (or "none" if all >= 0.7).

## Files

- [`lib/schema.py`](lib/schema.py) — Pydantic models + Markdown formatter
- [`lib/prompts.py`](lib/prompts.py) — `NEEDS_PROMPT` + `INTERVENTIONS_PROMPT` + system prompt
- [`lib/generator.py`](lib/generator.py) — `SDTRewardDetector` orchestrator
- [`demo/01_self_contained_demo.py`](demo/01_self_contained_demo.py) — Overjustification-effect demo
- [`eval/synthetic_sdt_traces.yaml`](eval/synthetic_sdt_traces.yaml) — 8 scenarios across all three needs + intrinsic baseline
- [`eval/run_benchmark.py`](eval/run_benchmark.py) — Corpus runner
- [`tests/test_sdt_reward.py`](tests/test_sdt_reward.py) — pytest suite

## Quick start

```python
from agentcity.sdt_reward import AgentSDTTrace, SDTRewardDetector
from agentcity.aar.clients import AnthropicClient

trace = AgentSDTTrace(
    agent_id="research-agent",
    task="Explore design space for new feature.",
    task_class="research_exploration",
    system_prompt="You MUST follow the template. You WILL be RATED.",
    extrinsic_signals=["Threat: low ratings flagged."],
    observed_behaviors=["Agent restated established patterns, no novel directions."],
    outcome="Output is rigid; zero novel directions.",
    success=False,
)
detection = SDTRewardDetector(AnthropicClient()).run(trace)
print(detection.to_markdown())
```
