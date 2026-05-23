"""Baseline + drift detection for the SMART Goal Generator."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import BaselineComparison, SMARTGoal


def record_baseline(goal: SMARTGoal, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = goal.run_id or goal.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "smart-goal-baseline/v1",
        "baseline_id": baseline_id,
        "goal": json.loads(goal.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> SMARTGoal:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "goal" not in raw:
        return SMARTGoal.model_validate(raw)
    return SMARTGoal.model_validate(raw["goal"])


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


def compare_to_baseline(current: SMARTGoal, baseline: SMARTGoal) -> BaselineComparison:
    current_criteria = {c.criterion: c.quality_score for c in current.criteria}
    baseline_criteria = {c.criterion: c.quality_score for c in baseline.criteria}
    deltas: dict[str, float] = {
        "overall_smart_score": round(current.overall_smart_score - baseline.overall_smart_score, 4),
    }
    for c in ("specific", "measurable", "achievable", "relevant", "time_bound"):
        deltas[c] = round(current_criteria.get(c, 0.0) - baseline_criteria.get(c, 0.0), 4)
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
