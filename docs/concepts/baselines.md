# Calibration baselines

A **baseline** is a JSON snapshot of a pattern's detection on a known-healthy trace. Subsequent runs supplied with the same baseline path return a `BaselineComparison` block on the detection showing per-metric drift, direction, and significance. This is how vstack does monitoring without a database.

## How to use one

```python
from vstack.span_of_control import SpanLoadCalculator

# Future runs against a stored baseline:
detection = SpanLoadCalculator(llm).run(
    new_trace,
    baseline_path="~/.vstack/baselines/span_of_control.json",
)
print(detection.baseline_comparison.deltas)  # per-metric drift
```

## Where they're stored

- `~/.vstack/baselines/<pattern_name>.json` is the canonical location.
- Override via `VSTACK_HOME=/custom/path` env var.
- Print the resolved path: `vstack-config path baselines`.

## Pre-shipped canonical baselines

vstack ships three Span-of-Control baselines that you can use immediately without recording your own (Span-of-Control's math is deterministic — no LLM in the metrics — so its baseline JSON is reproducible across machines):

| File | Crew topology |
|---|---|
| `_baselines/canonical/span_of_control_small_flat.json` | 1 orchestrator + 2 workers @ 10 req/min — healthy small-crew |
| `_baselines/canonical/span_of_control_two_layer.json` | 1 orchestrator → 3 leads → 9 workers @ 50 req/min — healthy mid-scale |
| `_baselines/canonical/span_of_control_hub_and_spoke.json` | 1 orchestrator + 12 flat workers @ 100 req/min — textbook failure mode (centralized + saturated) |

See [`_baselines/README.md`](https://github.com/valani9/vstack/blob/main/_baselines/README.md) for the regeneration recipe + the per-pattern process for the 33 LLM-bearing patterns.

## Recording your own baseline

1. Find a recent run on a crew that's behaving the way you want.
2. Run the pattern in `forensic` mode.
3. Save the detection JSON.

```bash
vstack-lewin analyze --trace healthy_run.json --mode forensic \
    --baseline-out ~/.vstack/baselines/lewin.json
```

After that, every subsequent vstack-lewin invocation compares against the saved baseline. The `/vstack-baseline` Claude Code skill orchestrates this for bundles of patterns.
