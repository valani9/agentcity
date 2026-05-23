"""Baseline + drift detection for the McGregor diagnostic."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import BaselineComparison, OrchestratorModeDetection


_INDICATOR_KEYS: tuple[str, ...] = (
    "check_in_frequency",
    "autonomy_granted",
    "pre_approval_required",
    "intervention_rate",
)


def record_baseline(detection: OrchestratorModeDetection, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = detection.run_id or detection.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "mcgregor-baseline/v1",
        "baseline_id": baseline_id,
        "detection": json.loads(detection.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> OrchestratorModeDetection:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "detection" not in raw:
        return OrchestratorModeDetection.model_validate(raw)
    return OrchestratorModeDetection.model_validate(raw["detection"])


def _drift_severity(
    deltas: dict[str, float],
    mode_changed: bool,
    profile_changed: bool,
) -> str:
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if abs_max > 0.40:
        return "severe"
    if mode_changed or profile_changed:
        return "moderate"
    if abs_max > 0.20:
        return "moderate"
    if abs_max > 0.10:
        return "minor"
    return "none"


def compare_to_baseline(
    current: OrchestratorModeDetection,
    baseline: OrchestratorModeDetection,
) -> BaselineComparison:
    deltas: dict[str, float] = {}
    for k in _INDICATOR_KEYS:
        c = float(getattr(current.indicators, k))
        b = float(getattr(baseline.indicators, k))
        deltas[k] = round(c - b, 4)

    mode_changed = current.observed_mode != baseline.observed_mode
    profile_changed = current.profile_pattern != baseline.profile_pattern
    severity = _drift_severity(deltas, mode_changed, profile_changed)

    notes_parts: list[str] = []
    if mode_changed:
        notes_parts.append(
            f"observed_mode shifted {baseline.observed_mode} -> {current.observed_mode}"
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
        baseline_observed_mode=baseline.observed_mode,
        baseline_profile_pattern=baseline.profile_pattern,
        indicator_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = ["compare_to_baseline", "load_baseline", "record_baseline"]
