"""Baseline + drift detection for the Thomas-Kilmann selector."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import STYLES, BaselineComparison, ConflictStyleSelection


def record_baseline(selection: ConflictStyleSelection, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = selection.run_id or selection.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "thomas-kilmann-baseline/v1",
        "baseline_id": baseline_id,
        "selection": json.loads(selection.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> ConflictStyleSelection:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "selection" not in raw:
        return ConflictStyleSelection.model_validate(raw)
    return ConflictStyleSelection.model_validate(raw["selection"])


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
    current: ConflictStyleSelection, baseline: ConflictStyleSelection
) -> BaselineComparison:
    deltas: dict[str, float] = {
        "style_mismatch": round(current.style_mismatch - baseline.style_mismatch, 4),
        "assertiveness": round(current.assertiveness_score - baseline.assertiveness_score, 4),
        "cooperativeness": round(current.cooperativeness_score - baseline.cooperativeness_score, 4),
    }
    for s in STYLES:
        deltas[s] = round(
            current.observed_style_scores.get(s, 0.0) - baseline.observed_style_scores.get(s, 0.0),
            4,
        )
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
