"""``vstack-gbrain`` CLI."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from ._search import (
    PatternMatch,
    indexed_corpus,
    is_available,
    search_patterns,
    sync_corpus,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vstack-gbrain",
        description=(
            "Optional gbrain (semantic memory) integration for the "
            "34-pattern catalogue. When gbrain is installed + configured, "
            "search returns semantic hits; otherwise falls back to a "
            "keyword scan over the same corpus."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    p_status = sub.add_parser("status", help="Show whether gbrain is reachable.")
    p_status.add_argument("--json", dest="as_json", action="store_true")

    p_sync = sub.add_parser(
        "sync",
        help="Write the 34 pattern documents into gbrain. Idempotent.",
    )
    p_sync.add_argument("--dry-run", action="store_true")
    p_sync.add_argument("--json", dest="as_json", action="store_true")

    p_search = sub.add_parser(
        "search", help="Search the pattern catalogue with semantic-or-keyword fallback."
    )
    p_search.add_argument("query", help="Free-form natural-language query.")
    p_search.add_argument("--limit", type=int, default=5)
    p_search.add_argument("--json", dest="as_json", action="store_true")

    sub.add_parser("corpus", help="Dump the indexed corpus as JSON (debug).")

    args = parser.parse_args(argv)
    cmd = args.command or "status"

    if cmd == "status":
        avail = is_available()
        payload = {"gbrain_available": avail, "patterns_in_corpus": len(indexed_corpus())}
        if args.as_json:
            print(json.dumps(payload, indent=2))
        else:
            print(
                f"gbrain on PATH: {'yes' if avail else 'no'}\n"
                f"corpus size:    {payload['patterns_in_corpus']} patterns"
            )
        return 0

    if cmd == "sync":
        result = sync_corpus(dry_run=args.dry_run)
        if args.as_json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("dry_run"):
                print(
                    f"DRY RUN: would sync {result['would_sync']} documents "
                    f"(gbrain available: {result['available']})"
                )
            elif not result.get("available"):
                print(
                    "gbrain isn't on PATH; nothing to sync. "
                    f"Would have synced {result.get('would_sync', 0)} documents."
                )
            else:
                synced = result.get("synced", 0)
                errors = result.get("errors", []) or []
                print(f"Synced {synced} documents; {len(errors)} errors.")
                for e in errors:
                    print(f"  ! {e['id']} ({e['title']})")
        return 0

    if cmd == "search":
        results = search_patterns(args.query, limit=args.limit)
        if args.as_json:
            print(json.dumps([_as_dict(m) for m in results], indent=2))
            return 0
        if not results:
            print(f"(no matches for {args.query!r})")
            return 0
        for r in results:
            print(
                f"  {r.score:.3f}  [{r.source}]  {r.tool:<28}  {r.friendly}\n"
                f"           {r.summary}\n"
            )
        return 0

    if cmd == "corpus":
        print(json.dumps(indexed_corpus(), indent=2, default=str))
        return 0

    parser.error(f"Unknown command: {cmd}")
    return 2


def _as_dict(match: PatternMatch) -> dict[str, object]:
    return {
        "name": match.name,
        "friendly": match.friendly,
        "summary": match.summary,
        "tool": match.tool,
        "score": match.score,
        "source": match.source,
        "extra": match.extra,
    }


if __name__ == "__main__":
    sys.exit(main())
