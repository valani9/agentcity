# vstack Cookbook

Cross-pattern composition examples. Each pattern's own `demo/`
directory shows the pattern in isolation; this cookbook shows the
patterns being **wired together** — fan-out across patterns, post-AAR
follow-on diagnosis, telemetry-aware deployment, async server traffic,
structured-log shipping.

All recipes use the `StubClient` by default so they run with `pip
install vstack` and no API key.

## Recipes

  - [01_aar_then_lewin.py](01_aar_then_lewin.py) — run an After-Action
    Review (#30), then route the AAR's identified gap to a Lewin
    (#01) Person × Environment diagnosis for a follow-on intervention.
  - [02_parallel_pattern_fan_out.py](02_parallel_pattern_fan_out.py)
    — fan out three patterns over the same agent trace in parallel
    using the async LLM clients, then merge the results.
  - [03_observable_run.py](03_observable_run.py) — wire structured
    logging (run-id correlation), token / cost telemetry, and
    prompt-injection input guards into a single pattern run. Print
    the resulting log lines and telemetry events.

## Running

```bash
# Stub (no API key required, deterministic):
python examples/cookbook/01_aar_then_lewin.py

# Against Anthropic / OpenAI / Ollama:
vstack_LLM=anthropic python examples/cookbook/01_aar_then_lewin.py
vstack_LLM=openai    python examples/cookbook/01_aar_then_lewin.py
vstack_LLM=ollama    python examples/cookbook/01_aar_then_lewin.py
```
