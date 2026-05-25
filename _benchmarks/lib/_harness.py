"""Benchmark harness implementation.

Designed to be:

* **Stub-friendly** -- unit tests pass a :class:`vstack.aar.StubClient`
  through ``llm_client_factory`` and never touch a real API.
* **Real-friendly** -- production runs pass
  :class:`vstack.aar.AnthropicClient` (or any other ``vstack.aar``
  client) and get real numbers. The harness doesn't impose its own
  rate-limiting; rely on the underlying client's retry logic.
* **Reproducible** -- each case carries a deterministic seed (used
  only for case-ordering shuffles; LLM determinism is the client's
  problem); the report records the seed so re-runs are comparable.
* **Pluggable suites** -- ship a tiny ``canonical`` suite alongside
  the code; load larger suites (GAIA, SWE-Bench-multi, AppWorld,
  AgentBench) from JSON files via :func:`load_suite`.

This module is intentionally pattern-agnostic. A case names which
vstack pattern to run; the runner dispatches through the same
``vstack.adapters.run_pattern_dispatch`` the MCP server uses.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from vstack.adapters._base import run_pattern_dispatch
from vstack.mcp._registry import PATTERNS_BY_NAME

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkCase:
    """A single benchmark case.

    A case is *one* pattern + *one* trace + *one* mode + *one*
    expected-severity range. The harness runs it, captures the
    detection, and scores it.
    """

    case_id: str
    """Stable identifier (used in report rows + as filename when
    saving per-case detections to disk)."""

    pattern: str
    """vstack pattern import name (e.g. ``"lewin"``)."""

    mode: str = "standard"
    """Pipeline mode to run."""

    trace: Mapping[str, Any] = field(default_factory=dict)
    """The trace fields (top-level shape matching the pattern's input
    model). The harness merges this with ``mode``/``model`` before
    dispatch."""

    expected_severity_set: tuple[str, ...] = ()
    """If supplied, the case PASSES when the detection's severity
    field is in this set. Default: empty = no pass/fail signal,
    just a smoke check that the pipeline runs."""

    expected_dominant_field: str | None = None
    """If supplied, names a field on the detection that should equal
    ``expected_dominant_value`` for the case to PASS. Used for
    Lewin (``dominant_locus``), Lencioni (``dominant_dysfunction``),
    Schein (``dominant_layer``), etc."""

    expected_dominant_value: str | None = None
    """The expected value for ``expected_dominant_field``."""

    tags: tuple[str, ...] = ()
    """Free-form tags (suite name, source dataset, etc.)."""


@dataclass(frozen=True)
class BenchmarkCaseResult:
    """The recorded result of one case."""

    case_id: str
    pattern: str
    mode: str
    passed: bool
    elapsed_ms: float
    severity: str | None
    profile_pattern: str | None
    detection: Mapping[str, Any]
    error: str | None = None
    tags: tuple[str, ...] = ()


@dataclass
class BenchmarkReport:
    """Aggregated results over a full suite run."""

    suite: str
    total: int
    passed: int
    failed: int
    errors: int
    mean_elapsed_ms: float
    severity_distribution: dict[str, int]
    pass_rate: float
    cases: list[BenchmarkCaseResult]
    started_at: str
    ended_at: str
    seed: int = 0

    def to_summary_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly summary (no per-case detections)."""
        return {
            "suite": self.suite,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "pass_rate": self.pass_rate,
            "mean_elapsed_ms": self.mean_elapsed_ms,
            "severity_distribution": self.severity_distribution,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "seed": self.seed,
        }


@dataclass
class BenchmarkSuite:
    """Collection of benchmark cases with a name."""

    name: str
    cases: list[BenchmarkCase]
    description: str = ""


class BenchmarkRunner:
    """Iterates a :class:`BenchmarkSuite` and produces a :class:`BenchmarkReport`."""

    def __init__(
        self,
        *,
        llm_client_factory: Callable[[], Any] | None = None,
        on_case_complete: Callable[[BenchmarkCaseResult], None] | None = None,
    ) -> None:
        self.llm_client_factory = llm_client_factory
        self.on_case_complete = on_case_complete

    def run(self, suite: BenchmarkSuite, *, seed: int = 0) -> BenchmarkReport:
        results: list[BenchmarkCaseResult] = []
        started = datetime.now(timezone.utc)
        elapsed_total = 0.0
        severity_dist: dict[str, int] = {}

        for case in suite.cases:
            case_started = time.perf_counter()
            result = self._run_one(case)
            case_elapsed = (time.perf_counter() - case_started) * 1000.0
            result = BenchmarkCaseResult(
                case_id=result.case_id,
                pattern=result.pattern,
                mode=result.mode,
                passed=result.passed,
                elapsed_ms=round(case_elapsed, 3),
                severity=result.severity,
                profile_pattern=result.profile_pattern,
                detection=result.detection,
                error=result.error,
                tags=result.tags,
            )
            elapsed_total += case_elapsed
            sev = result.severity or ("error" if result.error else "unknown")
            severity_dist[sev] = severity_dist.get(sev, 0) + 1
            results.append(result)
            if self.on_case_complete:
                self.on_case_complete(result)

        ended = datetime.now(timezone.utc)
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        errored = sum(1 for r in results if r.error)
        failed = total - passed - errored
        mean_elapsed = (elapsed_total / total) if total else 0.0
        return BenchmarkReport(
            suite=suite.name,
            total=total,
            passed=passed,
            failed=failed,
            errors=errored,
            mean_elapsed_ms=round(mean_elapsed, 3),
            severity_distribution=severity_dist,
            pass_rate=round((passed / total) if total else 0.0, 4),
            cases=results,
            started_at=started.isoformat(),
            ended_at=ended.isoformat(),
            seed=seed,
        )

    def _run_one(self, case: BenchmarkCase) -> BenchmarkCaseResult:
        pattern = PATTERNS_BY_NAME.get(case.pattern)
        if pattern is None:
            return BenchmarkCaseResult(
                case_id=case.case_id,
                pattern=case.pattern,
                mode=case.mode,
                passed=False,
                elapsed_ms=0.0,
                severity=None,
                profile_pattern=None,
                detection={},
                error=f"unknown_pattern: {case.pattern}",
                tags=case.tags,
            )

        arguments = dict(case.trace)
        arguments["mode"] = case.mode
        detection = run_pattern_dispatch(
            pattern, arguments, llm_client_factory=self.llm_client_factory
        )

        if isinstance(detection, dict) and detection.get("error"):
            return BenchmarkCaseResult(
                case_id=case.case_id,
                pattern=case.pattern,
                mode=case.mode,
                passed=False,
                elapsed_ms=0.0,
                severity=None,
                profile_pattern=None,
                detection=detection,
                error=f"{detection['error']}: {detection.get('message', '')}",
                tags=case.tags,
            )

        severity = detection.get("severity") if isinstance(detection, dict) else None
        profile = detection.get("profile_pattern") if isinstance(detection, dict) else None

        passed = _score(case, detection)

        return BenchmarkCaseResult(
            case_id=case.case_id,
            pattern=case.pattern,
            mode=case.mode,
            passed=passed,
            elapsed_ms=0.0,
            severity=severity,
            profile_pattern=profile,
            detection=detection,
            error=None,
            tags=case.tags,
        )


def _score(case: BenchmarkCase, detection: Mapping[str, Any]) -> bool:
    """PASS/FAIL based on the case's expectations.

    Two checks (both optional):
      * severity falls in ``expected_severity_set``
      * ``detection[expected_dominant_field] == expected_dominant_value``
    A case with no expectations passes if it ran to completion.
    """
    if case.expected_severity_set:
        if detection.get("severity") not in case.expected_severity_set:
            return False
    if case.expected_dominant_field and case.expected_dominant_value is not None:
        if detection.get(case.expected_dominant_field) != case.expected_dominant_value:
            return False
    return True


# ----------------------------------------------------------------------
# canonical suite + IO
# ----------------------------------------------------------------------


def canonical_suite() -> BenchmarkSuite:
    """Three-case canonical suite shipped with vstack.

    Each case targets one of the three foundational diagnostics
    (Lewin / AAR / Schein). The traces are tiny but realistic; the
    harness's job is to run them, not to dataset-curate. Users
    bringing GAIA / SWE-Bench-multi / AppWorld / AgentBench cases
    add them via JSON suites loaded by :func:`load_suite`.
    """
    return BenchmarkSuite(
        name="canonical",
        description="Smoke-test suite shipped with vstack -- 3 cases.",
        cases=[
            BenchmarkCase(
                case_id="lewin/pluto-stale-rag",
                pattern="lewin",
                mode="standard",
                trace={
                    "agent_id": "qa-bot",
                    "model_name": "claude-opus-4-7",
                    "task": "Answer 'When was Pluto reclassified?'",
                    "steps": [
                        {"type": "input", "content": "When was Pluto reclassified?"},
                        {"type": "tool_call", "content": "rag.search(query='pluto')"},
                        {
                            "type": "observation",
                            "content": "returned a 2003 Wikipedia revision",
                        },
                        {"type": "output", "content": "Pluto was reclassified in 2003."},
                    ],
                    "outcome": "Confidently wrong year (correct: 2006).",
                    "success": False,
                    "initial_attribution": "model is bad at facts",
                },
                expected_dominant_field="dominant_locus",
                expected_dominant_value="environmental",
                tags=("canonical", "lewin", "rag-staleness"),
            ),
            BenchmarkCase(
                case_id="aar/jwt-refactor-broken-sessions",
                pattern="aar",
                mode="standard",
                trace={
                    "goal": "Refactor the auth module to use JWTs.",
                    "steps": [
                        {
                            "type": "tool_call",
                            "content": "edit_file(path='auth/middleware.py')",
                        },
                        {
                            "type": "observation",
                            "content": "session-middleware test failures",
                        },
                        {
                            "type": "output",
                            "content": "Created JWT tokens but broke session middleware.",
                        },
                    ],
                    "outcome": "Auth module half-migrated; session middleware broken.",
                    "success": False,
                },
                expected_severity_set=("low", "moderate", "medium", "high", "critical"),
                tags=("canonical", "aar", "code-refactor"),
            ),
            BenchmarkCase(
                case_id="schein/corporate-safe-tone",
                pattern="schein_culture",
                mode="standard",
                trace={
                    "crew_id": "campaign-team",
                    "task": "Generate Q3 marketing campaigns",
                    "observations": [
                        {
                            "category": "espoused_value",
                            "content": "We value bold, distinctive voice.",
                        },
                        {
                            "category": "behavior",
                            "content": "Every output reverts to corporate-safe tone.",
                        },
                        {
                            "category": "artifact",
                            "content": "Style guide doc says 'always provocative'.",
                        },
                    ],
                    "outcome": "Crew ships but tone defaults to corporate-safe.",
                    "success": False,
                },
                tags=("canonical", "schein", "tone-drift"),
            ),
        ],
    )


def load_suite(path: Path | str) -> BenchmarkSuite:
    """Load a suite from a JSON file.

    Expected JSON shape::

        {
          "name": "gaia-multi-agent-subset",
          "description": "...",
          "cases": [
            {
              "case_id": "...",
              "pattern": "lewin",
              "mode": "standard",
              "trace": {...},
              "expected_severity_set": ["high", "critical"],
              "expected_dominant_field": "dominant_locus",
              "expected_dominant_value": "environmental",
              "tags": ["gaia", "multi-agent"]
            },
            ...
          ]
        }
    """
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    return BenchmarkSuite(
        name=body["name"],
        description=body.get("description", ""),
        cases=[
            BenchmarkCase(
                case_id=row["case_id"],
                pattern=row["pattern"],
                mode=row.get("mode", "standard"),
                trace=row.get("trace") or {},
                expected_severity_set=tuple(row.get("expected_severity_set") or ()),
                expected_dominant_field=row.get("expected_dominant_field"),
                expected_dominant_value=row.get("expected_dominant_value"),
                tags=tuple(row.get("tags") or ()),
            )
            for row in body.get("cases", [])
        ],
    )


def save_report(report: BenchmarkReport, out_dir: Path | str) -> Path:
    """Write the full report (summary + per-case detections) under ``out_dir``.

    Returns the path to the summary file. The per-case detections
    are written as individual JSON files under
    ``out_dir/cases/<case_id>.json`` so they can be diffed across
    runs.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(report.to_summary_dict(), indent=2), encoding="utf-8")

    cases_dir = out_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    for case in report.cases:
        safe = case.case_id.replace("/", "__").replace(" ", "_")
        (cases_dir / f"{safe}.json").write_text(
            json.dumps(asdict(case), indent=2, default=str), encoding="utf-8"
        )
    return summary_path
