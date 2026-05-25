"""Append-only JSONL store for vstack learning records.

Records are small Pydantic models written one-per-line to
``~/.vstack/learnings.jsonl``. Recall is a streaming filter (no
in-memory index) so the file can grow large without affecting startup
latency; the typical query touches the last few hundred records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal

from pydantic import BaseModel, Field

from vstack.memory import get_home

Outcome = Literal["improved", "no_change", "worse", "unknown"]


class LearningRecord(BaseModel):
    """One pattern-run + intervention + follow-up entry."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pattern: str
    """Pattern import name, e.g. ``"lewin"``."""

    mode: str = "standard"
    """Pipeline mode used (quick / standard / forensic)."""

    agent_id: str | None = None
    """Single-agent runs: the agent identifier."""

    crew_id: str | None = None
    """Multi-agent runs: the crew identifier."""

    severity: str | None = None
    """Severity from the detection (none / trace / low / moderate / medium / high / critical)."""

    profile_pattern: str | None = None
    """Profile-pattern label from the detection (varies per analyzer)."""

    dominant_finding: str | None = None
    """One-line summary of the analyzer's headline (e.g. dominant locus
    for Lewin, dominant dysfunction for Lencioni)."""

    interventions_applied: list[str] = Field(default_factory=list)
    """The intervention identifiers the user committed to."""

    follow_up_outcome: Outcome | None = None
    """Outcome of the next run on the same artifact: 'improved' /
    'no_change' / 'worse' / 'unknown'. Set when a follow-up run is
    recorded against this entry."""

    follow_up_record_id: str | None = None
    """Reference (timestamp ISO string) to the follow-up record, if any."""

    notes: str = ""
    """Free-form user notes."""

    extra: dict[str, Any] = Field(default_factory=dict)
    """Forward-compat slot for fields downstream skills might add."""


class OutcomeAggregate(BaseModel):
    """Aggregate view returned by :meth:`LearningStore.outcomes`."""

    pattern: str
    intervention: str
    runs: int
    improved: int
    no_change: int
    worse: int
    unknown: int

    @property
    def improvement_rate(self) -> float:
        decided = self.improved + self.no_change + self.worse
        if decided == 0:
            return 0.0
        return self.improved / decided


class LearningStore:
    """Append-only JSONL learning store.

    Construct directly with a path for tests, or call
    :func:`default_store` to get one rooted at ``~/.vstack/``.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    # ------------------------------------------------------------------
    # write
    # ------------------------------------------------------------------

    def record(self, entry: LearningRecord) -> LearningRecord:
        """Append a record to the JSONL file. Returns the record.

        Uses an advisory file lock so concurrent vstack processes
        never interleave bytes on the same line. The lock is held
        only for the duration of the append; readers via
        :meth:`iter_records` see consistent lines.
        """
        from vstack.memory._fs_atomic import append_locked

        with append_locked(self.path) as f:
            f.write(entry.model_dump_json())
            f.write("\n")
        return entry

    def update_outcome(
        self,
        *,
        pattern: str,
        agent_id: str | None = None,
        crew_id: str | None = None,
        outcome: Outcome,
        follow_up_record_id: str | None = None,
        notes: str = "",
    ) -> LearningRecord | None:
        """Update the most recent matching record's follow_up_outcome.

        Rewrites the JSONL file in place because we want to keep the
        history append-only-by-default but allow correcting an
        ambiguous outcome later. Returns the updated record (or None
        if no matching record was found).
        """
        records = list(self.iter_records())
        target_idx: int | None = None
        for i in range(len(records) - 1, -1, -1):
            r = records[i]
            if r.pattern != pattern:
                continue
            if agent_id is not None and r.agent_id != agent_id:
                continue
            if crew_id is not None and r.crew_id != crew_id:
                continue
            if r.follow_up_outcome is None:
                target_idx = i
                break
        if target_idx is None:
            return None
        updated = records[target_idx].model_copy(
            update={
                "follow_up_outcome": outcome,
                "follow_up_record_id": follow_up_record_id,
                "notes": (records[target_idx].notes + ("\n" + notes if notes else "")).strip(),
            }
        )
        records[target_idx] = updated
        from vstack.memory._fs_atomic import atomic_write_text

        atomic_write_text(
            self.path,
            "\n".join(r.model_dump_json() for r in records) + ("\n" if records else ""),
        )
        return updated

    # ------------------------------------------------------------------
    # read
    # ------------------------------------------------------------------

    def iter_records(self) -> Iterator[LearningRecord]:
        """Stream every record (no in-memory cap)."""
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield LearningRecord.model_validate_json(line)
                except Exception:
                    # Skip malformed lines rather than abort the whole
                    # stream; surface in CLI as a warning eventually.
                    continue

    def recall(
        self,
        *,
        pattern: str | None = None,
        agent_id: str | None = None,
        crew_id: str | None = None,
        limit: int = 25,
    ) -> list[LearningRecord]:
        """Return the most recent matching records (newest first).

        ``limit`` caps the result set. Calling with no filters returns
        the last ``limit`` records overall.
        """
        out: list[LearningRecord] = []
        for r in self.iter_records():
            if pattern and r.pattern != pattern:
                continue
            if agent_id and r.agent_id != agent_id:
                continue
            if crew_id and r.crew_id != crew_id:
                continue
            out.append(r)
        out.reverse()
        return out[:limit]

    def outcomes(self, pattern: str | None = None) -> list[OutcomeAggregate]:
        """Aggregate ``(pattern, intervention) -> outcomes`` tallies.

        Useful for "we've tried intervention X seven times; it
        improved the next run in 5 of 7. Try it again."
        """
        counts: dict[tuple[str, str], dict[str, int]] = {}
        for r in self.iter_records():
            if pattern and r.pattern != pattern:
                continue
            for intervention in r.interventions_applied:
                key = (r.pattern, intervention)
                slot = counts.setdefault(
                    key,
                    {"runs": 0, "improved": 0, "no_change": 0, "worse": 0, "unknown": 0},
                )
                slot["runs"] += 1
                slot[r.follow_up_outcome or "unknown"] += 1
        return [
            OutcomeAggregate(
                pattern=p,
                intervention=intv,
                runs=v["runs"],
                improved=v["improved"],
                no_change=v["no_change"],
                worse=v["worse"],
                unknown=v["unknown"],
            )
            for (p, intv), v in sorted(counts.items())
        ]

    def clear(self) -> None:
        """Remove the underlying JSONL file (tests use this)."""
        if self.path.exists():
            self.path.unlink()


def default_store() -> LearningStore:
    """The learning store rooted at ``~/.vstack/learnings.jsonl``."""
    return LearningStore(path=get_home() / "learnings.jsonl")
