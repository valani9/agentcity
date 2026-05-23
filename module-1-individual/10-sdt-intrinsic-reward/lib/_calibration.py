"""Baseline + drift detection for the SDT diagnostic."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import SDT_NEEDS, BaselineComparison, SDTDetection


def record_baseline(detection: SDTDetection, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = detection.run_id or detection.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "sdt-baseline/v1",
        "baseline_id": baseline_id,
        "detection": json.loads(detection.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> SDTDetection:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "detection" not in raw:
        return SDTDetection.model_validate(raw)
    return SDTDetection.model_validate(raw["detection"])


def _drift_severity(
    deltas: dict[str, float],
    undermined_changed: bool,
    profile_changed: bool,
) -> str:
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if abs_max > 0.40:
        return "severe"
    if undermined_changed or profile_changed:
        return "moderate"
    if abs_max > 0.20:
        return "moderate"
    if abs_max > 0.10:
        return "minor"
    return "none"


def compare_to_baseline(current: SDTDetection, baseline: SDTDetection) -> BaselineComparison:
    curr_by_need: dict[str, float] = {str(ev.need): ev.score for ev in current.need_evidence}
    base_by_need: dict[str, float] = {str(ev.need): ev.score for ev in baseline.need_evidence}
    deltas: dict[str, float] = {}
    for n in SDT_NEEDS:
        c = float(curr_by_need.get(n, 0.0))
        b = float(base_by_need.get(n, 0.0))
        deltas[n] = round(c - b, 4)

    undermined_changed = current.most_undermined_need != baseline.most_undermined_need
    profile_changed = current.profile_pattern != baseline.profile_pattern
    severity = _drift_severity(deltas, undermined_changed, profile_changed)

    notes_parts: list[str] = []
    if undermined_changed:
        notes_parts.append(
            f"most_undermined_need shifted {baseline.most_undermined_need} -> "
            f"{current.most_undermined_need}"
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
        baseline_most_undermined_need=baseline.most_undermined_need,
        baseline_profile_pattern=baseline.profile_pattern,
        need_score_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = ["compare_to_baseline", "load_baseline", "record_baseline"]
