"""Baseline + drift detection for Social Loafing."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import BaselineComparison, SocialLoafingDetection


def record_baseline(detection: SocialLoafingDetection, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = detection.run_id or detection.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "social-loafing-baseline/v1",
        "baseline_id": baseline_id,
        "detection": json.loads(detection.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> SocialLoafingDetection:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "detection" not in raw:
        return SocialLoafingDetection.model_validate(raw)
    return SocialLoafingDetection.model_validate(raw["detection"])


def _drift_severity(gini_delta: float, profile_changed: bool) -> str:
    abs_delta = abs(gini_delta)
    if abs_delta > 0.30:
        return "severe"
    if profile_changed:
        return "moderate"
    if abs_delta > 0.15:
        return "moderate"
    if abs_delta > 0.08:
        return "minor"
    return "none"


def compare_to_baseline(
    current: SocialLoafingDetection, baseline: SocialLoafingDetection
) -> BaselineComparison:
    delta = round(current.gini_coefficient - baseline.gini_coefficient, 4)
    profile_changed = current.profile_pattern != baseline.profile_pattern
    severity = _drift_severity(delta, profile_changed)
    notes_parts: list[str] = []
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
        baseline_profile_pattern=baseline.profile_pattern,
        gini_delta=delta,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = ["compare_to_baseline", "load_baseline", "record_baseline"]
