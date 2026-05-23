"""Baseline comparison + drift detection for the Johari self-audit.

Drift severity buckets (deterministic, conservative):

  - **none** -- every quadrant weight delta has |delta| <= 0.10 AND
    dominant quadrant unchanged AND profile pattern unchanged.
  - **minor** -- some delta in (0.10, 0.20], dominant unchanged.
  - **moderate** -- some delta in (0.20, 0.40], OR dominant quadrant
    changed, OR profile pattern shifted within the same family.
  - **severe** -- some delta > 0.40, OR direct quadrant flip (BLIND <->
    OPEN, HIDDEN <-> OPEN), OR opposite-shape profile flip.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import QUADRANTS, BaselineComparison, JohariSelfAudit


def record_baseline(audit: JohariSelfAudit, path: str | Path) -> Path:
    """Write ``audit`` to ``path`` as a baseline."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = audit.run_id or audit.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "johari-baseline/v1",
        "baseline_id": baseline_id,
        "audit": json.loads(audit.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> JohariSelfAudit:
    """Read a baseline written by :func:`record_baseline`."""
    p = Path(path)
    raw = json.loads(p.read_text())
    if "audit" not in raw:
        return JohariSelfAudit.model_validate(raw)
    return JohariSelfAudit.model_validate(raw["audit"])


def _drift_severity(
    deltas: dict[str, float],
    dominant_changed: bool,
    profile_changed: bool,
    direct_flip: bool,
    profile_flip: bool,
) -> str:
    """Map deltas + categorical moves to a severity bucket."""
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if direct_flip or profile_flip:
        return "severe"
    if abs_max > 0.40:
        return "severe"
    if dominant_changed or profile_changed:
        return "moderate"
    if abs_max > 0.20:
        return "moderate"
    if abs_max > 0.10:
        return "minor"
    return "none"


def _is_direct_quadrant_flip(prev: str, curr: str) -> bool:
    """A direct flip is BLIND <-> OPEN or HIDDEN <-> OPEN."""
    pair = {prev, curr}
    flips = (
        {"blind", "open"},
        {"hidden", "open"},
        {"blind", "hidden"},
    )
    return any(pair == f for f in flips)


def _is_profile_flip(prev: str, curr: str) -> bool:
    """An opposite-shape profile flip."""
    pair = {prev, curr}
    flips = (
        {"balanced_high", "balanced_low"},
        {"self_unaware_other_aware", "self_aware_other_unaware"},
        {"opaque_to_users", "over_disclosing"},
    )
    return any(pair == f for f in flips)


def compare_to_baseline(current: JohariSelfAudit, baseline: JohariSelfAudit) -> BaselineComparison:
    """Compute a :class:`BaselineComparison`."""
    deltas: dict[str, float] = {}
    for q in QUADRANTS:
        c = float(current.quadrant_weights.get(q, 0.0))
        b = float(baseline.quadrant_weights.get(q, 0.0))
        deltas[q] = round(c - b, 4)

    dominant_changed = current.dominant_quadrant != baseline.dominant_quadrant
    profile_changed = current.profile_pattern != baseline.profile_pattern
    direct_flip = _is_direct_quadrant_flip(baseline.dominant_quadrant, current.dominant_quadrant)
    profile_flip = _is_profile_flip(baseline.profile_pattern, current.profile_pattern)
    severity = _drift_severity(deltas, dominant_changed, profile_changed, direct_flip, profile_flip)

    notes_parts: list[str] = []
    if dominant_changed:
        notes_parts.append(
            f"dominant quadrant shifted {baseline.dominant_quadrant} -> {current.dominant_quadrant}"
        )
    if profile_changed:
        notes_parts.append(
            f"profile pattern shifted {baseline.profile_pattern} -> {current.profile_pattern}"
        )
    if direct_flip:
        notes_parts.append("direct quadrant FLIP -- review urgently")
    if profile_flip:
        notes_parts.append("profile-pattern FLIP -- review urgently")
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
        baseline_dominant_quadrant=baseline.dominant_quadrant,
        baseline_profile_pattern=baseline.profile_pattern,
        quadrant_weight_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = [
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
]
