"""Baseline comparison + drift detection for DANVA Emotion Reader."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import EMOTION_CATEGORIES, BaselineComparison, EmotionRecognitionAnalysis


def record_baseline(analysis: EmotionRecognitionAnalysis, path: str | Path) -> Path:
    """Write ``analysis`` to ``path`` as a baseline."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = analysis.run_id or analysis.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "danva-baseline/v1",
        "baseline_id": baseline_id,
        "analysis": json.loads(analysis.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> EmotionRecognitionAnalysis:
    """Read a baseline written by :func:`record_baseline`."""
    p = Path(path)
    raw = json.loads(p.read_text())
    if "analysis" not in raw:
        return EmotionRecognitionAnalysis.model_validate(raw)
    return EmotionRecognitionAnalysis.model_validate(raw["analysis"])


def _drift_severity(
    deltas: dict[str, float],
    weakest_changed: bool,
    profile_changed: bool,
) -> str:
    """Map deltas + categorical moves to severity bucket."""
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if abs_max > 0.40:
        return "severe"
    if weakest_changed or profile_changed:
        return "moderate"
    if abs_max > 0.20:
        return "moderate"
    if abs_max > 0.10:
        return "minor"
    return "none"


def compare_to_baseline(
    current: EmotionRecognitionAnalysis, baseline: EmotionRecognitionAnalysis
) -> BaselineComparison:
    """Compute a :class:`BaselineComparison`."""
    curr_by_emotion: dict[str, float] = {str(m.emotion): m.accuracy for m in current.metrics}
    base_by_emotion: dict[str, float] = {str(m.emotion): m.accuracy for m in baseline.metrics}
    deltas: dict[str, float] = {}
    for e in EMOTION_CATEGORIES:
        c = float(curr_by_emotion.get(e, 0.0))
        b = float(base_by_emotion.get(e, 0.0))
        deltas[e] = round(c - b, 4)

    weakest_changed = current.weakest_emotion != baseline.weakest_emotion
    profile_changed = current.profile_pattern != baseline.profile_pattern
    severity = _drift_severity(deltas, weakest_changed, profile_changed)

    notes_parts: list[str] = []
    if weakest_changed:
        notes_parts.append(
            f"weakest emotion shifted {baseline.weakest_emotion} -> {current.weakest_emotion}"
        )
    if profile_changed:
        notes_parts.append(
            f"profile pattern shifted {baseline.profile_pattern} -> {current.profile_pattern}"
        )
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if abs_max > 0.20:
        worst = max(deltas, key=lambda k: abs(deltas[k]))
        notes_parts.append(f"largest delta on {worst}: {deltas[worst]:+.2f}")

    return BaselineComparison(
        historical_baseline_id=baseline.run_id
        or (
            baseline.generated_at.isoformat()
            if isinstance(baseline.generated_at, datetime)
            else None
        ),
        historical_generated_at=baseline.generated_at,
        baseline_weakest_emotion=baseline.weakest_emotion,
        baseline_profile_pattern=baseline.profile_pattern,
        emotion_accuracy_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = [
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
]
