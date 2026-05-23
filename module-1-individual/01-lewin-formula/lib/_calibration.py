"""Baseline comparison + drift detection for the Lewin diagnostic.

Production deployments often want to know: "is this run different from
last week's run, on the same agent, with the same kind of failure?"
The calibration layer answers that.

Three operations:

  - :func:`record_baseline` — write a :class:`LewinDetection` to disk
    in a stable, forward-compatible JSON shape.
  - :func:`load_baseline` — read it back.
  - :func:`compare_to_baseline` — compute per-locus score deltas + a
    drift severity bucket.

The drift severity bucket is deterministic and conservative:

  - **none** — every locus delta has |Δ| ≤ 0.10 *and* the dominant
    locus did not change.
  - **minor** — some locus delta has 0.10 < |Δ| ≤ 0.20, dominant locus
    unchanged.
  - **moderate** — some locus delta has 0.20 < |Δ| ≤ 0.40, or the
    dominant locus shifted within the same dominant-side family
    (internal ↔ interactional, environmental ↔ interactional).
  - **severe** — some locus delta has |Δ| > 0.40, or the dominant
    locus flipped internal ↔ environmental directly.

The thresholds are tuned for the score range used by the LLM
diagnostic (0.0–1.0); they're conservative — a 0.10 swing is genuinely
within run-to-run noise on stochastic LLM outputs.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import BaselineComparison, LewinDetection


def record_baseline(detection: LewinDetection, path: str | Path) -> Path:
    """Write ``detection`` to ``path`` as a baseline for future comparison.

    The on-disk format is the pydantic ``model_dump_json`` of the
    detection plus a small header recording schema version + a stable
    baseline id derived from the run id (when present) or the
    generated_at timestamp.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = detection.run_id or detection.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "lewin-baseline/v1",
        "baseline_id": baseline_id,
        "detection": json.loads(detection.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> LewinDetection:
    """Read a baseline previously written by :func:`record_baseline`."""
    p = Path(path)
    raw = json.loads(p.read_text())
    if "detection" not in raw:
        # Allow loading a raw LewinDetection JSON without the wrapper
        # (e.g. when a user piped `--format json` output into a file).
        return LewinDetection.model_validate(raw)
    return LewinDetection.model_validate(raw["detection"])


def _drift_severity(deltas: dict[str, float], dominant_changed: bool, flip: bool) -> str:
    """Map deltas + dominant-locus movement to a severity bucket."""
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if flip:
        return "severe"
    if abs_max > 0.40:
        return "severe"
    if dominant_changed:
        return "moderate"
    if abs_max > 0.20:
        return "moderate"
    if abs_max > 0.10:
        return "minor"
    return "none"


def _is_flip(prev_dominant: str, curr_dominant: str) -> bool:
    """A flip is internal ↔ environmental directly (not via interactional)."""
    pair = {prev_dominant, curr_dominant}
    return pair == {"internal", "environmental"}


def compare_to_baseline(current: LewinDetection, baseline: LewinDetection) -> BaselineComparison:
    """Compute a :class:`BaselineComparison` between ``current`` and ``baseline``.

    The baseline's ``run_id`` is used as the comparison id when available;
    otherwise the baseline's ``generated_at`` ISO string is used.
    """
    deltas: dict[str, float] = {}
    for locus in ("internal", "environmental", "interactional"):
        c = float(current.locus_scores.get(locus, 0.0))
        b = float(baseline.locus_scores.get(locus, 0.0))
        deltas[locus] = round(c - b, 4)

    dominant_changed = current.dominant_locus != baseline.dominant_locus
    flip = _is_flip(baseline.dominant_locus, current.dominant_locus)
    severity = _drift_severity(deltas, dominant_changed, flip)

    notes_parts: list[str] = []
    if dominant_changed:
        notes_parts.append(
            f"dominant locus shifted {baseline.dominant_locus} → {current.dominant_locus}"
        )
    if flip:
        notes_parts.append("INTERNAL ↔ ENVIRONMENTAL direct flip — review urgently")
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if abs_max > 0.20:
        worst = max(deltas, key=lambda k: abs(deltas[k]))
        notes_parts.append(f"largest score drift on {worst}: {deltas[worst]:+.2f}")

    return BaselineComparison(
        historical_baseline_id=baseline.run_id
        or (
            baseline.generated_at.isoformat()
            if isinstance(baseline.generated_at, datetime)
            else None
        ),
        historical_generated_at=baseline.generated_at,
        baseline_dominant_locus=baseline.dominant_locus,
        locus_score_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = [
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
]
