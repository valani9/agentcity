"""Baseline + drift detection for the GRPI Working Agreement."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import BaselineComparison, WorkingAgreement


def record_baseline(agreement: WorkingAgreement, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = agreement.run_id or agreement.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "grpi-baseline/v1",
        "baseline_id": baseline_id,
        "agreement": json.loads(agreement.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> WorkingAgreement:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "agreement" not in raw:
        return WorkingAgreement.model_validate(raw)
    return WorkingAgreement.model_validate(raw["agreement"])


def _drift_severity(completeness_delta: float, profile_changed: bool) -> str:
    abs_delta = abs(completeness_delta)
    if abs_delta > 0.40:
        return "severe"
    if profile_changed:
        return "moderate"
    if abs_delta > 0.20:
        return "moderate"
    if abs_delta > 0.10:
        return "minor"
    return "none"


def compare_to_baseline(
    current: WorkingAgreement, baseline: WorkingAgreement
) -> BaselineComparison:
    delta = round(current.completeness_score - baseline.completeness_score, 4)
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
        completeness_delta=delta,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = ["compare_to_baseline", "load_baseline", "record_baseline"]
