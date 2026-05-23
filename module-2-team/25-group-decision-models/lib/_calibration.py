"""Baseline + drift detection for the Group Decision Models generator."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import BaselineComparison, DecisionProtocol


def record_baseline(protocol: DecisionProtocol, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = protocol.run_id or protocol.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "group-decision-baseline/v1",
        "baseline_id": baseline_id,
        "protocol": json.loads(protocol.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> DecisionProtocol:
    p = Path(path)
    raw = json.loads(p.read_text())
    if "protocol" not in raw:
        return DecisionProtocol.model_validate(raw)
    return DecisionProtocol.model_validate(raw["protocol"])


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
    current: DecisionProtocol, baseline: DecisionProtocol
) -> BaselineComparison:
    deltas: dict[str, float] = {
        "fit_score": round(current.fit_score - baseline.fit_score, 4),
        "model_changed": 0.0 if current.recommended_model == baseline.recommended_model else 1.0,
    }
    profile_changed = current.profile_pattern != baseline.profile_pattern
    severity = _drift_severity({"fit_score": deltas["fit_score"]}, profile_changed)
    notes_parts: list[str] = []
    if profile_changed:
        notes_parts.append(
            f"profile_pattern shifted {baseline.profile_pattern} -> {current.profile_pattern}"
        )
    if deltas["model_changed"]:
        notes_parts.append(
            f"recommended_model shifted {baseline.recommended_model} -> {current.recommended_model}"
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
