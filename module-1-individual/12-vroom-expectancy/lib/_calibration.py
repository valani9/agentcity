"""Baseline + drift detection for the Vroom Expectancy diagnostic."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import VROOM_TERMS, BaselineComparison, VroomDetection


def record_baseline(detection: VroomDetection, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = detection.run_id or detection.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "vroom-baseline/v1",
        "baseline_id": baseline_id,
        "detection": json.loads(detection.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> VroomDetection:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "detection" not in raw:
        return VroomDetection.model_validate(raw)
    return VroomDetection.model_validate(raw["detection"])


def _drift_severity(
    deltas: dict[str, float],
    bottleneck_changed: bool,
    profile_changed: bool,
) -> str:
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if abs_max > 0.40:
        return "severe"
    if bottleneck_changed or profile_changed:
        return "moderate"
    if abs_max > 0.20:
        return "moderate"
    if abs_max > 0.10:
        return "minor"
    return "none"


def compare_to_baseline(current: VroomDetection, baseline: VroomDetection) -> BaselineComparison:
    curr_by_term: dict[str, float] = {str(t.term): t.score for t in current.terms}
    base_by_term: dict[str, float] = {str(t.term): t.score for t in baseline.terms}
    deltas: dict[str, float] = {}
    for t in VROOM_TERMS:
        c = float(curr_by_term.get(t, 0.0))
        b = float(base_by_term.get(t, 0.0))
        deltas[t] = round(c - b, 4)

    bn_changed = current.bottleneck_term != baseline.bottleneck_term
    profile_changed = current.profile_pattern != baseline.profile_pattern
    severity = _drift_severity(deltas, bn_changed, profile_changed)

    notes_parts: list[str] = []
    if bn_changed:
        notes_parts.append(
            f"bottleneck_term shifted {baseline.bottleneck_term} -> {current.bottleneck_term}"
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
        baseline_bottleneck_term=baseline.bottleneck_term,
        baseline_profile_pattern=baseline.profile_pattern,
        term_score_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = ["compare_to_baseline", "load_baseline", "record_baseline"]
