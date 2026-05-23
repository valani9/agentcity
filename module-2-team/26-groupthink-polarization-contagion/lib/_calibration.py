"""Baseline + drift detection for the Debate Pathology diagnostic."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import PATHOLOGIES, BaselineComparison, DebatePathologyDetection


def record_baseline(detection: DebatePathologyDetection, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = detection.run_id or detection.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "debate-pathology-baseline/v1",
        "baseline_id": baseline_id,
        "detection": json.loads(detection.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> DebatePathologyDetection:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "detection" not in raw:
        return DebatePathologyDetection.model_validate(raw)
    return DebatePathologyDetection.model_validate(raw["detection"])


def _drift_severity(deltas: dict[str, float], profile_changed: bool) -> str:
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if abs_max > 0.40:
        return "severe"
    if profile_changed:
        return "moderate"
    if abs_max > 0.20:
        return "moderate"
    if abs_max > 0.10:
        return "minor"
    return "none"


def compare_to_baseline(
    current: DebatePathologyDetection, baseline: DebatePathologyDetection
) -> BaselineComparison:
    deltas: dict[str, float] = {}
    for p in PATHOLOGIES:
        c = float(current.pathology_scores.get(p, 0.0))
        b = float(baseline.pathology_scores.get(p, 0.0))
        deltas[p] = round(c - b, 4)
    profile_changed = current.profile_pattern != baseline.profile_pattern
    severity = _drift_severity(deltas, profile_changed)
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
        score_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = ["compare_to_baseline", "load_baseline", "record_baseline"]
