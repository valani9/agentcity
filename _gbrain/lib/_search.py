"""Implementation for ``vstack.gbrain``.

gbrain ships as both a Python library and an MCP server. We never
import it at module-load time -- the check happens inside :func:`is_available`
and uses a subprocess `gbrain --version` probe so we don't pin a
version. If gbrain isn't installed, search degrades to a keyword
scan over the in-memory corpus.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

from vstack.mcp._registry import PATTERNS, PatternEntry, tool_name_for

logger = logging.getLogger(__name__)

NAMESPACE = "vstack/patterns"
"""gbrain namespace prefix for pattern documents."""


@dataclass(frozen=True)
class PatternMatch:
    """One search hit."""

    name: str
    """Pattern import name (e.g. ``"lewin"``)."""

    friendly: str
    """Friendly label (e.g. ``"Lewin Attribution"``)."""

    summary: str
    """One-sentence summary from the registry."""

    score: float
    """0.0-1.0 relevance score. From gbrain when available, else
    a token-overlap heuristic for the keyword fallback."""

    source: str
    """``"gbrain"`` or ``"keyword_fallback"``."""

    tool: str = ""
    """The matching MCP tool name (vstack_<name>)."""

    extra: dict[str, Any] = field(default_factory=dict)


def is_available() -> bool:
    """Return ``True`` iff a ``gbrain`` executable resolves on PATH.

    We don't try to import gbrain as a Python package -- the canonical
    distribution is the CLI; users who installed only its MCP server
    still have it on PATH.
    """
    return shutil.which("gbrain") is not None


def indexed_corpus() -> list[dict[str, Any]]:
    """Return the documents that get indexed in gbrain.

    One per pattern. Each document carries enough text for semantic
    search to discriminate between patterns -- summary, group,
    analyzer / input / output class names, mode set, playbook keys,
    and composition recommendations.
    """
    out: list[dict[str, Any]] = []
    for pattern in PATTERNS:
        resolved = pattern.load()
        playbook_keys = _playbook_key_strings(resolved.playbooks)
        composition = _composition_one_liner(resolved.composition)
        body = _build_body(pattern, resolved, playbook_keys, composition)
        out.append(
            {
                "id": f"{NAMESPACE}/{pattern.name}",
                "title": pattern.friendly,
                "body": body,
                "metadata": {
                    "pattern": pattern.name,
                    "friendly": pattern.friendly,
                    "group": pattern.group,
                    "tool": tool_name_for(pattern),
                    "summary": pattern.summary,
                    "input_class": pattern.input_cls,
                    "output_class": pattern.output_cls,
                    "modes": list(resolved.mode_values),
                    "playbook_keys": playbook_keys,
                    "composition_summary": composition,
                },
            }
        )
    return out


def sync_corpus(*, dry_run: bool = False) -> dict[str, Any]:
    """Write the 34 pattern documents into gbrain.

    Idempotent: writing the same document id twice replaces it.
    Returns a summary dict ``{"synced": N, "skipped": ..., "errors": ...}``.

    When ``dry_run=True`` or gbrain isn't installed, returns a
    summary describing what *would* have been synced without
    touching the brain.
    """
    docs = indexed_corpus()
    if dry_run or not is_available():
        return {
            "would_sync": len(docs),
            "available": is_available(),
            "dry_run": dry_run,
        }

    synced = 0
    errors: list[dict[str, Any]] = []
    for doc in docs:
        ok = _gbrain_put_document(doc)
        if ok:
            synced += 1
        else:
            errors.append({"id": doc["id"], "title": doc["title"]})
    return {"synced": synced, "errors": errors, "available": True}


def search_patterns(
    query: str,
    *,
    limit: int = 5,
) -> list[PatternMatch]:
    """Return the top-K patterns matching ``query`` semantically.

    Uses gbrain when available; falls back to a token-overlap
    keyword scan otherwise. The result list is always present and
    deterministic for the fallback path -- callers can treat
    ``source != "gbrain"`` as "this ranking is brittle, take with a grain of salt."
    """
    if is_available():
        results = _gbrain_search(query, limit=limit)
        if results:
            return results
        # gbrain installed but returned nothing -- still useful to
        # surface fallback hits so the user gets *something* back.
        logger.debug("gbrain returned no hits; falling back to keyword scan")
    return _keyword_search(query, limit=limit)


# ----------------------------------------------------------------------
# internals
# ----------------------------------------------------------------------


def _playbook_key_strings(playbooks: Any) -> list[str]:
    """Best-effort flatten of a pattern's playbook dict keys.

    Most patterns key on ``(locus, factor)`` tuples; some use single
    strings. We render either as a flat list of ``"locus::factor"``
    or just the string form.
    """
    if not playbooks:
        return []
    out: list[str] = []
    try:
        for key in playbooks.keys():
            if isinstance(key, tuple):
                out.append("::".join(str(k) for k in key))
            else:
                out.append(str(key))
    except Exception:
        return []
    return out


def _composition_one_liner(composition: Any) -> str:
    """Squeeze a composition manifest into one line of text."""
    if composition is None:
        return ""
    rec_up = getattr(composition, "recommended_upstream", None) or []
    rec_dn = getattr(composition, "recommended_downstream", None) or []
    if not rec_up and not rec_dn:
        return repr(composition)[:200]

    def _names(seq: Any) -> list[str]:
        out: list[str] = []
        try:
            for item in seq:
                if isinstance(item, dict):
                    name = item.get("pattern") or item.get("name")
                else:
                    name = getattr(item, "pattern", None) or getattr(item, "name", None)
                if name:
                    out.append(str(name))
        except Exception:
            return out
        return out

    return f"upstream={', '.join(_names(rec_up)) or '-'}; downstream={', '.join(_names(rec_dn)) or '-'}"


def _build_body(
    pattern: PatternEntry,
    resolved: Any,
    playbook_keys: list[str],
    composition: str,
) -> str:
    return (
        f"{pattern.friendly}\n"
        f"Group: {pattern.group}\n"
        f"Summary: {pattern.summary}\n\n"
        f"Input model: {pattern.input_cls}\n"
        f"Output model: {pattern.output_cls}\n"
        f"Modes: {', '.join(resolved.mode_values)}\n"
        f"Playbook keys: {', '.join(playbook_keys) or '(none)'}\n"
        f"Composition: {composition or '(none)'}\n"
    )


def _gbrain_put_document(doc: dict[str, Any]) -> bool:
    """Best-effort: feed one document into gbrain via the CLI.

    Tries several common command shapes; if none work, returns False
    and the caller falls back to a no-op. We never raise -- gbrain's
    CLI surface varies across versions and we'd rather degrade than
    block the user's release flow.
    """
    payload = json.dumps(doc)
    candidates: list[list[str]] = [
        ["gbrain", "put-page", "--id", doc["id"], "--title", doc["title"], "--stdin"],
        ["gbrain", "put", "--id", doc["id"], "--stdin"],
        ["gbrain", "ingest", "--namespace", NAMESPACE, "--stdin"],
    ]
    for cmd in candidates:
        try:
            proc = subprocess.run(  # noqa: S603 - explicit command list
                cmd,
                input=payload,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            if proc.returncode == 0:
                return True
        except FileNotFoundError:
            return False
        except subprocess.TimeoutExpired:
            logger.warning("gbrain put timed out for %s", doc["id"])
            return False
    return False


def _gbrain_search(query: str, *, limit: int) -> list[PatternMatch]:
    """Best-effort gbrain semantic search via the CLI.

    Same defensive shape as :func:`_gbrain_put_document` -- try the
    likely command lines, return [] if none work.
    """
    candidates: list[list[str]] = [
        ["gbrain", "search", "--namespace", NAMESPACE, "--limit", str(limit), "--json", query],
        ["gbrain", "search", "--limit", str(limit), "--json", query],
        ["gbrain", "query", "--limit", str(limit), "--json", query],
    ]
    for cmd in candidates:
        try:
            proc = subprocess.run(  # noqa: S603 - explicit command list
                cmd,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        if proc.returncode != 0:
            continue
        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError:
            continue
        hits = _normalize_gbrain_hits(parsed, limit=limit)
        if hits:
            return hits
    return []


def _normalize_gbrain_hits(parsed: Any, *, limit: int) -> list[PatternMatch]:
    if isinstance(parsed, dict):
        rows = parsed.get("results") or parsed.get("hits") or parsed.get("data") or []
    elif isinstance(parsed, list):
        rows = parsed
    else:
        return []
    out: list[PatternMatch] = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata") or row.get("meta") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        name = metadata.get("pattern") or _extract_name_from_id(row.get("id") or "")
        if not name:
            continue
        out.append(
            PatternMatch(
                name=str(name),
                friendly=str(metadata.get("friendly") or name),
                summary=str(metadata.get("summary") or row.get("title") or ""),
                score=float(row.get("score") or row.get("similarity") or 0.0),
                source="gbrain",
                tool=str(metadata.get("tool") or f"vstack_{name}"),
                extra={"id": row.get("id")},
            )
        )
    return out


def _extract_name_from_id(doc_id: str) -> str:
    if doc_id.startswith(f"{NAMESPACE}/"):
        return doc_id[len(NAMESPACE) + 1 :]
    return ""


def _keyword_search(query: str, *, limit: int) -> list[PatternMatch]:
    """Token-overlap fallback when gbrain isn't available."""
    tokens = [t for t in _tokenize(query.lower()) if t]
    if not tokens:
        return []
    scored: list[tuple[float, PatternMatch]] = []
    docs = indexed_corpus()
    for doc in docs:
        body = (doc["title"] + "\n" + doc["body"]).lower()
        hits = sum(1 for t in tokens if t in body)
        if hits == 0:
            continue
        score = hits / float(len(tokens))
        scored.append(
            (
                score,
                PatternMatch(
                    name=str(doc["metadata"]["pattern"]),
                    friendly=str(doc["metadata"]["friendly"]),
                    summary=str(doc["metadata"]["summary"]),
                    score=round(score, 4),
                    source="keyword_fallback",
                    tool=str(doc["metadata"]["tool"]),
                ),
            )
        )
    scored.sort(key=lambda p: p[0], reverse=True)
    return [m for _s, m in scored[:limit]]


def _tokenize(text: str) -> list[str]:
    out: list[str] = []
    current: list[str] = []
    for ch in text:
        if ch.isalnum() or ch == "_":
            current.append(ch)
        else:
            if current:
                out.append("".join(current))
                current = []
    if current:
        out.append("".join(current))
    return [t for t in out if len(t) > 2]
