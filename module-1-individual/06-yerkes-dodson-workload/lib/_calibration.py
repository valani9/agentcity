"""Baseline comparison + drift detection for Yerkes-Dodson Workload."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import WORKLOAD_ZONES, BaselineComparison, WorkloadDetection


def record_baseline(detection: WorkloadDetection, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = detection.run_id or detection.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "yerkes-dodson-baseline/v1",
        "baseline_id": baseline_id,
        "detection": json.loads(detection.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> WorkloadDetection:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "detection" not in raw:
        return WorkloadDetection.model_validate(raw)
    return WorkloadDetection.model_validate(raw["detection"])


def _drift_severity(
    deltas: dict[str, float],
    zone_changed: bool,
    profile_changed: bool,
) -> str:
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if abs_max > 0.40:
        return "severe"
    if zone_changed or profile_changed:
        return "moderate"
    if abs_max > 0.20:
        return "moderate"
    if abs_max > 0.10:
        return "minor"
    return "none"


def compare_to_baseline(
    current: WorkloadDetection, baseline: WorkloadDetection
) -> BaselineComparison:
    curr_by_zone: dict[str, float] = {str(ev.zone): ev.score for ev in current.zone_evidence}
    base_by_zone: dict[str, float] = {str(ev.zone): ev.score for ev in baseline.zone_evidence}
    deltas: dict[str, float] = {}
    for z in WORKLOAD_ZONES:
        c = float(curr_by_zone.get(z, 0.0))
        b = float(base_by_zone.get(z, 0.0))
        deltas[z] = round(c - b, 4)

    zone_changed = current.observed_zone != baseline.observed_zone
    profile_changed = current.profile_pattern != baseline.profile_pattern
    severity = _drift_severity(deltas, zone_changed, profile_changed)

    notes_parts: list[str] = []
    if zone_changed:
        notes_parts.append(
            f"observed zone shifted {baseline.observed_zone} -> {current.observed_zone}"
        )
    if profile_changed:
        notes_parts.append(
            f"profile pattern shifted {baseline.profile_pattern} -> {current.profile_pattern}"
        )

    return BaselineComparison(
        historical_baseline_id=baseline.run_id
        or (
            baseline.generated_at.isoformat()
            if isinstance(baseline.generated_at, datetime)
            else None
        ),
        historical_generated_at=baseline.generated_at,
        baseline_zone=baseline.observed_zone,
        baseline_profile_pattern=baseline.profile_pattern,
        zone_score_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = ["compare_to_baseline", "load_baseline", "record_baseline"]
