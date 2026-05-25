"""vstack.learnings -- append-only JSONL log of pattern runs +
interventions + follow-up outcomes.

Stored at ``~/.vstack/learnings.jsonl`` (overridable via
``VSTACK_HOME``). One JSON line per learning record. Used by the
``vstack-learn`` CLI and by future skill workflows to recall what was
tried before -- "last time you ran Lencioni on this crew, you applied
intervention X. Did it help?"

The record schema is intentionally narrow in v0; downstream features
(skill auto-suggestion, intervention-effectiveness aggregation) will
add fields as they need them, but the existing layout is forward-
compatible since JSONL adds new keys without breaking old readers.
"""

from ._store import (
    LearningRecord,
    LearningStore,
    OutcomeAggregate,
    default_store,
)

__all__ = [
    "LearningRecord",
    "LearningStore",
    "OutcomeAggregate",
    "default_store",
]

__version__ = "0.4.0"
