"""Baseline + drift calibration for Org-Structure Matrix."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .schema import BaselineComparison, StructureAnalysis


def record_baseline(detection: StructureAnalysis, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(detection.model_dump_json())
    payload["_baseline_recorded_at"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_baseline(path: str | Path) -> StructureAnalysis:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw.pop("_baseline_recorded_at", None)
    return StructureAnalysis.model_validate(raw)


def _severity(magnitude: float) -> str:
    if magnitude < 0.05:
        return "none"
    if magnitude < 0.15:
        return "minor"
    if magnitude < 0.30:
        return "moderate"
    return "severe"


def compare_to_baseline(
    current: StructureAnalysis, baseline: StructureAnalysis
) -> BaselineComparison:
    deltas: dict[str, float] = {
        "overall_fit": round(current.overall_fit - baseline.overall_fit, 4),
    }
    baseline_fits = {d.dimension: d.fit_score for d in baseline.dimensions}
    for d in current.dimensions:
        old = baseline_fits.get(d.dimension)
        if old is not None:
            deltas[f"fit::{d.dimension}"] = round(d.fit_score - old, 4)

    magnitudes = [abs(v) for v in deltas.values()]
    severity = _severity(max(magnitudes) if magnitudes else 0.0)

    return BaselineComparison(
        historical_baseline_id=baseline.run_id,
        historical_generated_at=baseline.generated_at,
        baseline_profile_pattern=baseline.profile_pattern,
        score_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes=(
            f"current pattern: {current.profile_pattern}; "
            f"baseline pattern: {baseline.profile_pattern}"
        ),
    )


__all__ = [
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
]
