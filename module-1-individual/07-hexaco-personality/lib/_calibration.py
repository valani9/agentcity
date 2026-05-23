"""Baseline comparison + drift detection for HEXACO Personality."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import HEXACO_FACTORS, BaselineComparison, HEXACODetection


def record_baseline(detection: HEXACODetection, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = detection.run_id or detection.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "hexaco-baseline/v1",
        "baseline_id": baseline_id,
        "detection": json.loads(detection.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> HEXACODetection:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "detection" not in raw:
        return HEXACODetection.model_validate(raw)
    return HEXACODetection.model_validate(raw["detection"])


def _drift_severity(
    deltas: dict[str, float],
    h_risk_changed: bool,
    profile_changed: bool,
) -> str:
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if h_risk_changed and abs_max > 0.15:
        return "severe"
    if abs_max > 0.40:
        return "severe"
    if h_risk_changed or profile_changed:
        return "moderate"
    if abs_max > 0.20:
        return "moderate"
    if abs_max > 0.10:
        return "minor"
    return "none"


def compare_to_baseline(current: HEXACODetection, baseline: HEXACODetection) -> BaselineComparison:
    curr_by_factor: dict[str, float] = {str(f.factor): f.score for f in current.factors}
    base_by_factor: dict[str, float] = {str(f.factor): f.score for f in baseline.factors}
    deltas: dict[str, float] = {}
    for fac in HEXACO_FACTORS:
        c = float(curr_by_factor.get(fac, 0.5))
        b = float(base_by_factor.get(fac, 0.5))
        deltas[fac] = round(c - b, 4)

    h_risk_changed = current.h_factor_risk != baseline.h_factor_risk
    profile_changed = current.profile_pattern != baseline.profile_pattern
    severity = _drift_severity(deltas, h_risk_changed, profile_changed)

    notes_parts: list[str] = []
    if h_risk_changed:
        notes_parts.append(
            f"h_factor_risk shifted {baseline.h_factor_risk} -> {current.h_factor_risk}"
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
        baseline_h_factor_risk=baseline.h_factor_risk,
        baseline_profile_pattern=baseline.profile_pattern,
        factor_score_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = ["compare_to_baseline", "load_baseline", "record_baseline"]
