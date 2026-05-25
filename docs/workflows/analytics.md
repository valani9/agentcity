# Telemetry + cost analytics

Every pattern emits `record_llm_call` events for each LLM invocation. `vstack.analytics` ships a `FileTelemetrySink` that appends one JSONL line per event to `~/.vstack/analytics/telemetry.jsonl`, plus a streaming aggregator for usage + cost rollups.

## Enable the file sink

```python
from vstack.analytics import enable_file_telemetry
enable_file_telemetry()   # install for the lifetime of the process
```

All subsequent `record_llm_call` events from every pattern flow into the JSONL file.

## CLI

```bash
vstack-analytics summary                    # per-pattern usage rollup
vstack-analytics summary --by model         # per-model
vstack-analytics summary --by day           # per-day
vstack-analytics top-costs -n 10            # N most expensive individual calls
vstack-analytics cost                       # total estimated cost
vstack-analytics raw                        # stream raw events
vstack-analytics path                       # print the JSONL file path
```

## Cost estimation

`CostEstimator` ships a baseline `$/1k tokens` table covering:

- Claude Opus 4.7, Sonnet 4.6, Haiku 4.5, 3.5 Sonnet, 3 Opus, 3 Haiku
- GPT-5, GPT-4o, GPT-4 Turbo, GPT-4o Mini
- o1 Preview, o1 Mini
- Llama 3.1 (local, $0)

Override per-model rates:

```python
from vstack.analytics import CostEstimator, TelemetryAggregator
est = CostEstimator(rates={"my-custom-model": (0.002, 0.008)})
agg = TelemetryAggregator(estimator=est)
print(agg.total_cost())
```
