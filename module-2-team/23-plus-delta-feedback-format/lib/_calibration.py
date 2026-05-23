"""Baseline + drift detection for the Plus/Delta feedback generator."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import BaselineComparison, PlusDeltaFeedback


def record_baseline(feedback: PlusDeltaFeedback, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = feedback.run_id or feedback.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "plus-delta-baseline/v1",
        "baseline_id": baseline_id,
        "feedback": json.loads(feedback.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> PlusDeltaFeedback:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "feedback" not in raw:
        return PlusDeltaFeedback.model_validate(raw)
    return PlusDeltaFeedback.model_validate(raw["feedback"])


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
    current: PlusDeltaFeedback, baseline: PlusDeltaFeedback
) -> BaselineComparison:
    deltas: dict[str, float] = {
        "feedback_quality_score": round(
            current.feedback_quality_score - baseline.feedback_quality_score, 4
        ),
        "plus_count": float(len(current.plus_items) - len(baseline.plus_items)),
        "delta_count": float(len(current.delta_items) - len(baseline.delta_items)),
    }
    profile_changed = current.profile_pattern != baseline.profile_pattern
    severity = _drift_severity(
        {"feedback_quality_score": deltas["feedback_quality_score"]},
        profile_changed,
    )
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
