"""``vstack-learn`` CLI -- inspect, record, and aggregate learnings."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from ._store import LearningRecord, default_store


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vstack-learn",
        description=(
            "Inspect, record, and aggregate vstack learning entries "
            "stored at ~/.vstack/learnings.jsonl."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    p_record = sub.add_parser(
        "record",
        help="Append a learning record (pattern run + interventions + outcome).",
    )
    p_record.add_argument("pattern", help="Pattern import name, e.g. 'lewin'.")
    p_record.add_argument("--mode", default="standard")
    p_record.add_argument("--agent-id", default=None)
    p_record.add_argument("--crew-id", default=None)
    p_record.add_argument("--severity", default=None)
    p_record.add_argument("--profile-pattern", default=None)
    p_record.add_argument("--dominant-finding", default=None)
    p_record.add_argument(
        "--intervention",
        action="append",
        default=[],
        dest="interventions",
        help="Intervention identifier (repeat the flag for multiple).",
    )
    p_record.add_argument("--notes", default="")

    p_recall = sub.add_parser(
        "recall", help="Print the most recent matching records (newest first)."
    )
    p_recall.add_argument("--pattern", default=None)
    p_recall.add_argument("--agent-id", default=None)
    p_recall.add_argument("--crew-id", default=None)
    p_recall.add_argument("--limit", type=int, default=25)
    p_recall.add_argument("--json", dest="as_json", action="store_true")

    p_outcome = sub.add_parser(
        "outcome", help="Mark a follow-up outcome on the latest matching record."
    )
    p_outcome.add_argument("pattern")
    p_outcome.add_argument(
        "outcome",
        choices=("improved", "no_change", "worse", "unknown"),
    )
    p_outcome.add_argument("--agent-id", default=None)
    p_outcome.add_argument("--crew-id", default=None)
    p_outcome.add_argument("--notes", default="")

    p_agg = sub.add_parser(
        "outcomes",
        help=(
            "Aggregate (pattern, intervention) -> outcomes counts. Useful "
            "for 'which interventions actually worked?' queries."
        ),
    )
    p_agg.add_argument("--pattern", default=None)
    p_agg.add_argument("--json", dest="as_json", action="store_true")

    sub.add_parser("path", help="Print the resolved learnings.jsonl path.")
    sub.add_parser("clear", help="Delete the learnings.jsonl file (irreversible).")

    args = parser.parse_args(argv)
    cmd = args.command or "recall"
    store = default_store()

    if cmd == "record":
        record = LearningRecord(
            pattern=args.pattern,
            mode=args.mode,
            agent_id=args.agent_id,
            crew_id=args.crew_id,
            severity=args.severity,
            profile_pattern=args.profile_pattern,
            dominant_finding=args.dominant_finding,
            interventions_applied=list(args.interventions),
            notes=args.notes,
        )
        store.record(record)
        print(record.model_dump_json(indent=2))
        return 0

    if cmd == "recall":
        records = store.recall(
            pattern=args.pattern,
            agent_id=args.agent_id,
            crew_id=args.crew_id,
            limit=args.limit,
        )
        if args.as_json:
            print(json.dumps([r.model_dump(mode="json") for r in records], indent=2))
            return 0
        if not records:
            print("(no matching records)")
            return 0
        for r in records:
            interventions = ", ".join(r.interventions_applied) or "-"
            outcome = r.follow_up_outcome or "(no follow-up)"
            print(
                f"{r.timestamp.isoformat()}  {r.pattern}  sev={r.severity or '-'}  "
                f"profile={r.profile_pattern or '-'}  outcome={outcome}\n"
                f"    finding: {r.dominant_finding or '-'}\n"
                f"    interventions: {interventions}\n"
                f"    notes: {r.notes or '-'}\n"
            )
        return 0

    if cmd == "outcome":
        updated = store.update_outcome(
            pattern=args.pattern,
            agent_id=args.agent_id,
            crew_id=args.crew_id,
            outcome=args.outcome,
            notes=args.notes,
        )
        if updated is None:
            print(
                f"vstack-learn: no open record found for pattern={args.pattern}",
                file=sys.stderr,
            )
            return 1
        print(updated.model_dump_json(indent=2))
        return 0

    if cmd == "outcomes":
        rows = store.outcomes(pattern=args.pattern)
        if args.as_json:
            print(json.dumps([r.model_dump(mode="json") for r in rows], indent=2))
            return 0
        if not rows:
            print("(no aggregated rows)")
            return 0
        for row in rows:
            print(
                f"{row.pattern}::{row.intervention}  runs={row.runs}  "
                f"improved={row.improved}  no_change={row.no_change}  "
                f"worse={row.worse}  unknown={row.unknown}  "
                f"rate={row.improvement_rate:.0%}"
            )
        return 0

    if cmd == "path":
        print(store.path)
        return 0

    if cmd == "clear":
        store.clear()
        return 0

    parser.error(f"Unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
