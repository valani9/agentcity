"""Baseline + drift detection for the 4 Motivation Traps."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import MOTIVATION_TRAPS, BaselineComparison, MotivationDetection


def record_baseline(detection: MotivationDetection, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = detection.run_id or detection.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "motivation-baseline/v1",
        "baseline_id": baseline_id,
        "detection": json.loads(detection.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> MotivationDetection:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "detection" not in raw:
        return MotivationDetection.model_validate(raw)
    return MotivationDetection.model_validate(raw["detection"])


def _drift_severity(
    deltas: dict[str, float],
    dominant_changed: bool,
    profile_changed: bool,
) -> str:
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if abs_max > 0.40:
        return "severe"
    if dominant_changed or profile_changed:
        return "moderate"
    if abs_max > 0.20:
        return "moderate"
    if abs_max > 0.10:
        return "minor"
    return "none"


def compare_to_baseline(
    current: MotivationDetection,
    baseline: MotivationDetection,
) -> BaselineComparison:
    curr_by_trap: dict[str, float] = {str(ev.trap): ev.score for ev in current.trap_evidence}
    base_by_trap: dict[str, float] = {str(ev.trap): ev.score for ev in baseline.trap_evidence}
    deltas: dict[str, float] = {}
    for t in MOTIVATION_TRAPS:
        c = float(curr_by_trap.get(t, 0.0))
        b = float(base_by_trap.get(t, 0.0))
        deltas[t] = round(c - b, 4)

    dominant_changed = current.dominant_trap != baseline.dominant_trap
    profile_changed = current.profile_pattern != baseline.profile_pattern
    severity = _drift_severity(deltas, dominant_changed, profile_changed)

    notes_parts: list[str] = []
    if dominant_changed:
        notes_parts.append(
            f"dominant_trap shifted {baseline.dominant_trap} -> {current.dominant_trap}"
        )
    if profile_changed:
        notes_parts.append(
            f"profile_pattern shifted {baseline.profile_pattern} -> {current.profile_pattern}"
        )

    return BaselineComparison(
        historical_baseline_id=baseline.run_id
        or (
            baseline.generated_at.isoformat()
            if isinstance(baseline.generated_at, datetime)
            else None
        ),
        historical_generated_at=baseline.generated_at,
        baseline_dominant_trap=baseline.dominant_trap,
        baseline_profile_pattern=baseline.profile_pattern,
        trap_score_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = ["compare_to_baseline", "load_baseline", "record_baseline"]
