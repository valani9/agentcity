"""Baseline comparison + drift detection for the Goleman EI Audit.

Production deployments often want to know "is this agent showing the
same EI profile as last month?" The calibration layer answers that.

Drift severity buckets (deterministic, conservative — tuned for
stochastic LLM outputs in the 0.0-1.0 score range):

  - **none** -- every domain delta has |delta| <= 0.10 AND weakest
    unchanged AND profile_pattern unchanged.
  - **minor** -- some domain delta in (0.10, 0.20], dominant unchanged.
  - **moderate** -- some delta in (0.20, 0.40], or weakest_domain
    changed, or profile_pattern shifted within the same family
    (balanced_developing <-> balanced_low; self_strong <-> other_strong
    by themselves).
  - **severe** -- some delta > 0.40, or profile_pattern flipped between
    very different shapes (self_strong_other_weak <->
    other_strong_self_weak directly; recognition_strong_regulation_weak
    <-> regulation_strong_recognition_weak).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import EI_DOMAINS, EIBaselineComparison, EIDetection


def record_baseline(detection: EIDetection, path: str | Path) -> Path:
    """Write ``detection`` to ``path`` as a baseline."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    baseline_id = detection.run_id or detection.generated_at.isoformat()
    payload: dict[str, Any] = {
        "schema_version": "goleman-ei-baseline/v1",
        "baseline_id": baseline_id,
        "detection": json.loads(detection.model_dump_json()),
    }
    p.write_text(json.dumps(payload, indent=2, default=str))
    return p


def load_baseline(path: str | Path) -> EIDetection:
    """Read a baseline written by :func:`record_baseline`."""
    p = Path(path)
    raw = json.loads(p.read_text())
    if "detection" not in raw:
        return EIDetection.model_validate(raw)
    return EIDetection.model_validate(raw["detection"])


def _drift_severity(
    deltas: dict[str, float],
    weakest_changed: bool,
    profile_changed: bool,
    profile_flip: bool,
) -> str:
    """Map deltas + categorical moves to a severity bucket."""
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if profile_flip:
        return "severe"
    if abs_max > 0.40:
        return "severe"
    if weakest_changed or profile_changed:
        return "moderate"
    if abs_max > 0.20:
        return "moderate"
    if abs_max > 0.10:
        return "minor"
    return "none"


def _is_profile_flip(prev: str, curr: str) -> bool:
    """A flip is a direct swap between opposite-shape patterns."""
    pair = {prev, curr}
    flips = (
        {"self_strong_other_weak", "other_strong_self_weak"},
        {"recognition_strong_regulation_weak", "regulation_strong_recognition_weak"},
        {"balanced_high", "balanced_low"},
    )
    return any(pair == f for f in flips)


def compare_to_baseline(current: EIDetection, baseline: EIDetection) -> EIBaselineComparison:
    """Compute a :class:`EIBaselineComparison`."""
    deltas: dict[str, float] = {}
    curr_by_domain: dict[str, float] = {
        str(d.domain): d.score for d in current.domains
    }
    base_by_domain: dict[str, float] = {
        str(d.domain): d.score for d in baseline.domains
    }
    for domain in EI_DOMAINS:
        c = float(curr_by_domain.get(domain, 0.0))
        b = float(base_by_domain.get(domain, 0.0))
        deltas[domain] = round(c - b, 4)

    weakest_changed = current.weakest_domain != baseline.weakest_domain
    profile_changed = current.profile_pattern != baseline.profile_pattern
    profile_flip = _is_profile_flip(baseline.profile_pattern, current.profile_pattern)
    severity = _drift_severity(deltas, weakest_changed, profile_changed, profile_flip)

    notes_parts: list[str] = []
    if weakest_changed:
        notes_parts.append(
            f"weakest domain shifted {baseline.weakest_domain} -> {current.weakest_domain}"
        )
    if profile_changed:
        notes_parts.append(
            f"profile pattern shifted {baseline.profile_pattern} -> {current.profile_pattern}"
        )
    if profile_flip:
        notes_parts.append("profile-pattern FLIP -- review urgently")
    abs_max = max((abs(v) for v in deltas.values()), default=0.0)
    if abs_max > 0.20:
        worst = max(deltas, key=lambda k: abs(deltas[k]))
        notes_parts.append(f"largest delta on {worst}: {deltas[worst]:+.2f}")

    return EIBaselineComparison(
        historical_baseline_id=baseline.run_id
        or (
            baseline.generated_at.isoformat()
            if isinstance(baseline.generated_at, datetime)
            else None
        ),
        historical_generated_at=baseline.generated_at,
        baseline_weakest_domain=baseline.weakest_domain,
        baseline_profile_pattern=baseline.profile_pattern,
        domain_score_deltas=deltas,
        drift_severity=severity,  # type: ignore[arg-type]
        notes="; ".join(notes_parts),
    )


__all__ = [
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
]
