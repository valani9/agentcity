# Benchmark + comparative-eval harness

`vstack.benchmarks` runs vstack patterns against canonical + custom benchmark suites and emits structured reports. Pair it with `vstack.analytics` to capture cost per case.

## Canonical suite

3 cases spanning the foundational diagnostics (Lewin / AAR / Schein) ship with vstack:

```bash
vstack-bench list                     # show what's in the canonical suite
vstack-bench run canonical            # run it (uses your LLM keys)
vstack-bench run canonical --stub     # smoke test only (no LLM spend)
vstack-bench run canonical --out runs/2026-05-25
```

The `--out` flag writes a full report: a `summary.json` plus one JSON per case under `runs/<timestamp>/cases/`. Diff across runs to track quality drift.

## Custom suites

Load larger suites from JSON files:

```json
{
  "name": "gaia-multi-agent-subset",
  "description": "GAIA Level-1 cases that need multi-agent reasoning",
  "cases": [
    {
      "case_id": "gaia/level1/Q42",
      "pattern": "lencioni",
      "mode": "standard",
      "trace": { ... },
      "expected_severity_set": ["moderate", "medium"],
      "tags": ["gaia", "multi-agent"]
    }
  ]
}
```

```bash
vstack-bench run path/to/suite.json --out runs/gaia-subset
```

## Comparative mode

Quick vs. standard vs. forensic, side-by-side, with cost / quality / agreement signal:

```bash
vstack-bench compare canonical
vstack-bench compare canonical --mode quick --mode standard
vstack-bench compare canonical --json
```

Output:

```
case_id                              pattern          mode    ms      sev     dom
lewin/pluto-stale-rag                lewin            quick   1400    high    environmental
lewin/pluto-stale-rag                lewin            standard 2700   high    environmental
lewin/pluto-stale-rag                lewin            forensic 5100   high    environmental

[OK] lewin/pluto-stale-rag  unique_dominant_findings=['environmental']
```

The `[OK]` flag means all modes agreed on the dominant finding. Disagreement (`DRIFT`) is informative — usually means forensic mode caught something quick missed.

## What's not pre-shipped

GAIA / SWE-Bench-multi / AppWorld / AgentBench cases. Those datasets ship under their own licenses and we don't redistribute them. Bring your own copy + write a JSON suite that points at it; the harness handles the rest.
