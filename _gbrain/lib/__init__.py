"""vstack.gbrain -- optional semantic search over vstack's pattern
catalogue using gbrain (the semantic memory tool).

The 34 patterns each carry a rich docstring + summary + composition
manifest + per-(locus, factor) playbooks. With gbrain configured,
this module lets a caller ask in plain English -- "which pattern
catches an agent that confidently makes things up?" -- and get the
top-K matching patterns ranked by semantic similarity rather than
keyword overlap.

gbrain itself is an external tool (not a vstack dependency). When
it isn't configured or installed, this module degrades gracefully:
search falls back to a substring scan over the same corpus, and
``is_available()`` returns ``False`` so callers can branch.

Programmatic surface
--------------------

* :func:`is_available` -- does this machine have a configured gbrain?
* :func:`indexed_corpus` -- the pattern documents that get indexed:
  per-pattern summary + docstring + composition + playbook keys
* :func:`sync_corpus` -- write the corpus into gbrain (one document
  per pattern). Idempotent; safe to re-run.
* :func:`search_patterns` -- semantic search; returns
  ``[{name, friendly, summary, score, source}, ...]`` ranked by
  relevance. Source is ``"gbrain"`` or ``"keyword_fallback"``.

CLI
---

::

    vstack-gbrain status      # is gbrain configured + corpus synced?
    vstack-gbrain sync        # write the 34 pattern docs into gbrain
    vstack-gbrain search "<query>"  # semantic search
"""

from ._search import (
    PatternMatch,
    indexed_corpus,
    is_available,
    search_patterns,
    sync_corpus,
)

__all__ = [
    "PatternMatch",
    "indexed_corpus",
    "is_available",
    "search_patterns",
    "sync_corpus",
]

__version__ = "0.5.0"
