"""Baseline comparison + drift detection for Cognitive Reappraisal."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import REGULATION_STRATEGIES, BaselineComparison, RegulationDetection


def record_baseline(detection: RegulationDetection, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = detection.run_id or detection.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "reappraisal-baseline/v1",
        "baseline_id": baseline_id,
        "detection": json.loads(detection.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> RegulationDetection:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "detection" not in raw:
        return RegulationDetection.model_validate(raw)
    return RegulationDetection.model_validate(raw["detection"])


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
    current: RegulationDetection, baseline: RegulationDetection
) -> BaselineComparison:
    curr_by_strategy: dict[str, float] = {
        str(ev.strategy): ev.score for ev in current.strategy_evidence
    }
    base_by_strategy: dict[str, float] = {
        str(ev.strategy): ev.score for ev in baseline.strategy_evidence
    }
    deltas: dict[str, float] = {}
    for s in REGULATION_STRATEGIES:
        c = float(curr_by_strategy.get(s, 0.0))
        b = float(base_by_strategy.get(s, 0.0))
        deltas[s] = round(c - b, 4)

    dominant_changed = current.dominant_strategy != baseline.dominant_strategy
    profile_changed = current.profile_pattern != baseline.profile_pattern
    severity = _drift_severity(deltas, dominant_changed, profile_changed)

    notes_parts: list[str] = []
    if dominant_changed:
        notes_parts.append(
            f"dominant strategy shifted {baseline.dominant_strategy} -> {current.dominant_strategy}"
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
        baseline_dominant_strategy=baseline.dominant_strategy,
        baseline_profile_pattern=baseline.profile_pattern,
        strategy_score_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = [
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
]
