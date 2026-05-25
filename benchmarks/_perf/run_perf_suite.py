"""Per-pattern micro-benchmark harness for vstack.

Runs every pattern's full `.run(...)` pipeline against a deterministic
``StubClient`` over many iterations and reports latency statistics
(p50, p95, p99, max) per pattern. Because the stub eliminates LLM
network variance, the numbers measure only the library's own
overhead — schema validation, prompt construction, JSON parsing,
deterministic metric computation. That is exactly what we want to
catch in CI: if a pattern's pure-Python pipeline regresses, the
number moves; if it doesn't, the number stays put.

Run it:

    python benchmarks/_perf/run_perf_suite.py

Or as a regression gate:

    python benchmarks/_perf/run_perf_suite.py --max-p95-ms 50

Exits non-zero if any pattern's p95 exceeds the threshold.

This harness is intentionally not wired into the default CI matrix.
GitHub Actions runners have noisy CPUs and the absolute numbers will
shift between runs. Use it locally to track regressions, or wire it
into a self-hosted runner if you want trend lines.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class PerfResult:
    pattern: str
    iterations: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    failed: bool = False
    error: str = ""

    def passes(self, max_p95_ms: float | None) -> bool:
        if self.failed:
            return False
        if max_p95_ms is None:
            return True
        return self.p95_ms <= max_p95_ms


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def _time_once(callable_: Callable[[], Any]) -> float:
    start = time.perf_counter()
    callable_()
    return (time.perf_counter() - start) * 1000.0


def _run_pattern(
    name: str, build_run: Callable[[], Callable[[], Any]], iterations: int
) -> PerfResult:
    try:
        run_once = build_run()
        # Warm up the import + first-run JIT-ish costs.
        for _ in range(3):
            run_once()
        latencies = [_time_once(run_once) for _ in range(iterations)]
    except Exception as exc:
        return PerfResult(
            pattern=name,
            iterations=0,
            p50_ms=0.0,
            p95_ms=0.0,
            p99_ms=0.0,
            max_ms=0.0,
            failed=True,
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=2)}",
        )
    return PerfResult(
        pattern=name,
        iterations=iterations,
        p50_ms=statistics.median(latencies),
        p95_ms=_percentile(latencies, 0.95),
        p99_ms=_percentile(latencies, 0.99),
        max_ms=max(latencies),
    )


# Each entry returns a zero-argument callable that performs ONE complete
# pattern run against a fresh StubClient. The harness times that callable.
# When a pattern's surface changes, update its builder here.


def _builder_aar() -> Callable[[], Any]:
    from datetime import datetime, timezone

    from vstack.aar import AARGenerator, AgentTrace, StubClient, TraceStep

    canned = [
        "Refactor module.",
        "Edited 3 files; tests pass.",
        json.dumps(
            [
                {
                    "pattern": "happy-path",
                    "description": "Agent completed the goal.",
                    "root_cause": "scaffolding was adequate",
                    "framework_anchor": "Lewin 1936",
                    "cross_pattern_links": [],
                }
            ]
        ),
        json.dumps(
            [
                {
                    "intervention_type": "new_eval",
                    "description": "Add a regression eval.",
                    "suggested_implementation": "Add an eval covering the refactored path.",
                    "estimated_impact": "medium",
                    "rationale": "guard against future regression",
                }
            ]
        ),
    ]

    def run() -> Any:
        client = StubClient(list(canned))
        now = datetime.now(timezone.utc)
        trace = AgentTrace(
            goal="Refactor module",
            steps=[
                TraceStep(timestamp=now, type="observation", content="started"),
                TraceStep(timestamp=now, type="tool_call", content="edited"),
                TraceStep(timestamp=now, type="observation", content="tests pass"),
            ],
            outcome="ok",
            success=True,
        )
        return AARGenerator(llm_client=client).generate(trace)

    return run


def _builder_lewin() -> Callable[[], Any]:
    from vstack.aar import StubClient
    from vstack.lewin import AgentFailureTrace, FailureStep, LewinAttributionDetector

    canned = [
        json.dumps(
            [
                {
                    "locus": "internal",
                    "score": 0.2,
                    "severity": "low",
                    "explanation": "model fine",
                    "evidence_quotes": [],
                },
                {
                    "locus": "environmental",
                    "score": 0.8,
                    "severity": "high",
                    "explanation": "missing spec",
                    "evidence_quotes": ["spec one sentence"],
                },
                {
                    "locus": "interactional",
                    "score": 0.3,
                    "severity": "low",
                    "explanation": "minor",
                    "evidence_quotes": [],
                },
            ]
        ),
        json.dumps(
            [
                {
                    "target_locus": "environmental",
                    "intervention_type": "change_prompt",
                    "description": "Add accept criteria",
                    "suggested_implementation": "append to prompt",
                    "estimated_impact": "high",
                    "rationale": "fixes ambiguity",
                }
            ]
        ),
    ]

    def run() -> Any:
        client = StubClient(list(canned))
        trace = AgentFailureTrace(
            agent_id="t",
            task="Refactor",
            steps=[
                FailureStep(type="input", content="Refactor."),
                FailureStep(type="tool_call", content="edited"),
                FailureStep(type="error", content="failed"),
            ],
            outcome="bugs unfound",
            success=False,
        )
        return LewinAttributionDetector(client).run(trace)

    return run


def _builder_vroom() -> Callable[[], Any]:
    from vstack.aar import StubClient
    from vstack.vroom_expectancy import AgentExpectancyTrace, VroomExpectancyCalculator

    canned = [
        json.dumps(
            [
                {
                    "term": "expectancy",
                    "score": 0.3,
                    "explanation": "no scaffolding",
                    "evidence_quotes": [],
                },
                {
                    "term": "instrumentality",
                    "score": 0.5,
                    "explanation": "no review",
                    "evidence_quotes": [],
                },
                {
                    "term": "valence",
                    "score": 0.6,
                    "explanation": "purpose missing",
                    "evidence_quotes": [],
                },
            ]
        ),
        json.dumps(
            [
                {
                    "target_term": "expectancy",
                    "intervention_type": "scaffold_subtasks",
                    "description": "Break into 5 steps",
                    "suggested_implementation": "prompt",
                    "estimated_impact": "high",
                    "rationale": "raises E",
                }
            ]
        ),
    ]

    def run() -> Any:
        client = StubClient(list(canned))
        trace = AgentExpectancyTrace(
            agent_id="t",
            task="Debug entire codebase",
            task_class="code_generation",
            system_prompt="No scaffolding.",
            observed_behaviors=["quit after 5 files"],
            effort_signals=["quit early"],
            outcome="bugs unfound",
            success=False,
        )
        return VroomExpectancyCalculator(client).run(trace)

    return run


# Patterns NOT yet wired here run a no-op `import` smoke test only — they
# still appear in the perf-suite output but with iterations=0. Wiring them
# is incremental: each pattern's contributor adds a builder when it adopts
# the perf harness contract (see CONTRIBUTING.md, "Production-readiness
# checklist for new patterns").

PATTERN_BUILDERS: dict[str, Callable[[], Callable[[], Any]]] = {
    "aar": _builder_aar,
    "lewin": _builder_lewin,
    "vroom_expectancy": _builder_vroom,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="vstack per-pattern perf suite")
    parser.add_argument(
        "--iterations", type=int, default=100, help="Iterations per pattern (default 100)"
    )
    parser.add_argument(
        "--max-p95-ms",
        type=float,
        default=None,
        help="If set, exit non-zero when any pattern's p95 exceeds this value.",
    )
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="Comma-separated subset of pattern names to run (default: all wired).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output instead of the human table.",
    )
    args = parser.parse_args()

    selected = (
        [n.strip() for n in args.patterns.split(",") if n.strip()]
        if args.patterns
        else list(PATTERN_BUILDERS.keys())
    )
    unknown = [n for n in selected if n not in PATTERN_BUILDERS]
    if unknown:
        print(
            f"Unknown patterns: {unknown}. Available: {sorted(PATTERN_BUILDERS)}", file=sys.stderr
        )
        return 2

    results: list[PerfResult] = []
    for name in selected:
        result = _run_pattern(name, PATTERN_BUILDERS[name], args.iterations)
        results.append(result)

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "pattern": r.pattern,
                        "iterations": r.iterations,
                        "p50_ms": round(r.p50_ms, 3),
                        "p95_ms": round(r.p95_ms, 3),
                        "p99_ms": round(r.p99_ms, 3),
                        "max_ms": round(r.max_ms, 3),
                        "failed": r.failed,
                        "error": r.error,
                    }
                    for r in results
                ],
                indent=2,
            )
        )
    else:
        header = f"{'pattern':<24} {'n':>6} {'p50':>10} {'p95':>10} {'p99':>10} {'max':>10}"
        print(header)
        print("-" * len(header))
        for r in results:
            if r.failed:
                print(f"{r.pattern:<24}  FAILED  {r.error.splitlines()[0]}")
                continue
            print(
                f"{r.pattern:<24} {r.iterations:>6} "
                f"{r.p50_ms:>9.2f}ms {r.p95_ms:>9.2f}ms "
                f"{r.p99_ms:>9.2f}ms {r.max_ms:>9.2f}ms"
            )

    exit_code = 0
    if args.max_p95_ms is not None:
        for r in results:
            if not r.passes(args.max_p95_ms):
                print(
                    f"REGRESSION: pattern={r.pattern} p95={r.p95_ms:.2f}ms > max={args.max_p95_ms}ms",
                    file=sys.stderr,
                )
                exit_code = 1
    if any(r.failed for r in results):
        exit_code = max(exit_code, 1)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
