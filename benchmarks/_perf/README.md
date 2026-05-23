# AgentCity Performance Suite

A per-pattern micro-benchmark harness that times the **deterministic**
portions of every pattern's pipeline — schema validation, prompt
construction, JSON parsing, computed metrics — against a
`StubClient`. The LLM is mocked, so the numbers measure only the
library's own overhead.

## Why

When you change `_json_parsing`, `_retry`, `schema.py`, or a
pattern's metric computation, the perf suite tells you whether your
change made the library faster, slower, or the same. The numbers are
useful as a **trend line**, not an absolute budget — GitHub Actions
runners have noisy CPUs and shift between releases.

## How to run

```bash
# All wired patterns, 100 iterations each, human-readable table:
python benchmarks/_perf/run_perf_suite.py

# A subset:
python benchmarks/_perf/run_perf_suite.py --patterns aar,lewin

# Machine-readable JSON (good for diff-against-baseline scripts):
python benchmarks/_perf/run_perf_suite.py --json

# Regression gate (exit non-zero if any pattern's p95 > 50ms):
python benchmarks/_perf/run_perf_suite.py --max-p95-ms 50
```

## Wiring a new pattern

Add a `_builder_<pkg_name>` function to `run_perf_suite.py` that
returns a zero-argument callable performing one complete run against
a fresh `StubClient`, and register it in `PATTERN_BUILDERS`. Use the
existing `_builder_aar`, `_builder_lewin`, `_builder_vroom` entries
as templates. The harness handles timing, warm-up, and statistics.

The contract for a wired pattern:

  - The builder may import lazily (most do).
  - The callable returned by the builder must be re-runnable any
    number of times. Construct a fresh `StubClient` each call.
  - Canned LLM responses should be valid JSON of the shape the
    pattern's generator expects, so the run exercises the parsing
    + downstream code paths.
