"""Comparative-mode harness: quick vs. standard vs. forensic per pattern.

Useful for "how much do I gain in detection quality from going to
forensic mode, and is it worth the LLM-call cost?" The harness runs
the same case across all of a pattern's modes, captures the elapsed
ms + token totals + dominant-finding agreement, and emits a row per
mode that the user can stitch into a cost-quality plot.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from vstack.adapters._base import run_pattern_dispatch
from vstack.mcp._registry import PATTERNS_BY_NAME


@dataclass(frozen=True)
class ComparativeCase:
    """One case for the comparative harness."""

    case_id: str
    pattern: str
    trace: Mapping[str, Any]
    modes: tuple[str, ...] = ("quick", "standard", "forensic")
    """Modes to compare. Defaults to all three; some patterns only
    support a subset and the harness silently skips invalid modes."""


@dataclass
class ComparativeModeResult:
    mode: str
    elapsed_ms: float
    severity: str | None
    profile_pattern: str | None
    dominant: str | None
    detection: Mapping[str, Any]
    error: str | None = None


@dataclass
class ComparativeCaseReport:
    case_id: str
    pattern: str
    rows: list[ComparativeModeResult] = field(default_factory=list)

    def agreement(self) -> dict[str, Any]:
        """How consistent are the modes' dominant findings?"""
        finds = [r.dominant for r in self.rows if r.dominant]
        unique = set(finds)
        return {
            "modes_run": [r.mode for r in self.rows],
            "unique_dominant_findings": sorted(unique),
            "fully_consistent": len(unique) <= 1,
        }


def _dominant_for(detection: Mapping[str, Any], pattern: str) -> str | None:
    """Best-effort: pull a pattern-appropriate 'headline finding'.

    Different patterns name their headline field differently. We try
    a few common keys; users with custom patterns can override.
    """
    if not isinstance(detection, dict):
        return None
    for key in (
        "dominant_locus",
        "dominant_dysfunction",
        "dominant_layer",
        "dominant_finding",
        "dominant_factor",
        "dominant_quadrant",
        "profile_pattern",
        "severity",
    ):
        value = detection.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def run_comparative(
    cases: list[ComparativeCase],
    *,
    llm_client_factory: Callable[[], Any] | None = None,
) -> list[ComparativeCaseReport]:
    """Run each case across each mode; return per-case reports."""
    reports: list[ComparativeCaseReport] = []
    for case in cases:
        pattern = PATTERNS_BY_NAME.get(case.pattern)
        if pattern is None:
            reports.append(ComparativeCaseReport(case_id=case.case_id, pattern=case.pattern))
            continue
        resolved = pattern.load()
        report = ComparativeCaseReport(case_id=case.case_id, pattern=case.pattern)
        for mode in case.modes:
            if mode not in resolved.mode_values:
                continue
            arguments = dict(case.trace)
            arguments["mode"] = mode
            t0 = time.perf_counter()
            detection = run_pattern_dispatch(
                pattern, arguments, llm_client_factory=llm_client_factory
            )
            elapsed = (time.perf_counter() - t0) * 1000.0
            if isinstance(detection, dict) and detection.get("error"):
                report.rows.append(
                    ComparativeModeResult(
                        mode=mode,
                        elapsed_ms=round(elapsed, 3),
                        severity=None,
                        profile_pattern=None,
                        dominant=None,
                        detection=detection,
                        error=f"{detection['error']}: {detection.get('message', '')}",
                    )
                )
                continue
            report.rows.append(
                ComparativeModeResult(
                    mode=mode,
                    elapsed_ms=round(elapsed, 3),
                    severity=detection.get("severity") if isinstance(detection, dict) else None,
                    profile_pattern=detection.get("profile_pattern")
                    if isinstance(detection, dict)
                    else None,
                    dominant=_dominant_for(detection, case.pattern),
                    detection=detection,
                )
            )
        reports.append(report)
    return reports


def comparative_table(reports: list[ComparativeCaseReport]) -> list[dict[str, Any]]:
    """Flatten the comparative reports into a pandas-friendly row list."""
    rows: list[dict[str, Any]] = []
    for report in reports:
        for r in report.rows:
            rows.append(
                {
                    "case_id": report.case_id,
                    "pattern": report.pattern,
                    "mode": r.mode,
                    "elapsed_ms": r.elapsed_ms,
                    "severity": r.severity,
                    "profile_pattern": r.profile_pattern,
                    "dominant": r.dominant,
                    "error": r.error,
                }
            )
    return rows
