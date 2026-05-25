"""``vstack-analytics`` CLI."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from typing import Any, Sequence

from ._aggregate import default_aggregator


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vstack-analytics",
        description=(
            "Aggregate the LLM-call telemetry vstack patterns emit "
            "via record_llm_call. Reads from "
            "~/.vstack/analytics/telemetry.jsonl by default."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    summary = sub.add_parser(
        "summary",
        help="Print per-pattern, per-model, and per-day usage rollups.",
    )
    summary.add_argument(
        "--by",
        default="pattern",
        choices=("pattern", "model", "day"),
        help="Which dimension to roll up by (default: pattern).",
    )
    summary.add_argument("--json", dest="as_json", action="store_true", help="Emit JSON.")

    top = sub.add_parser("top-costs", help="Print the N most expensive individual calls.")
    top.add_argument("-n", type=int, default=10)
    top.add_argument("--json", dest="as_json", action="store_true", help="Emit JSON.")

    cost = sub.add_parser("cost", help="Print the total estimated cost in USD.")
    cost.add_argument("--json", dest="as_json", action="store_true", help="Emit JSON.")

    sub.add_parser("path", help="Print the resolved telemetry.jsonl path.")

    sub.add_parser("raw", help="Print every event as one JSON line on stdout.")

    args = parser.parse_args(argv)
    cmd = args.command or "summary"
    agg = default_aggregator()

    if cmd == "summary":
        rows: list[Any]
        if args.by == "pattern":
            rows = list(agg.per_pattern())
        elif args.by == "model":
            rows = list(agg.per_model())
        else:
            rows = list(agg.per_day())
        if args.as_json:
            print(json.dumps([dataclasses.asdict(r) for r in rows], indent=2))
            return 0
        if not rows:
            print(f"(no telemetry events yet at {agg.path})")
            return 0
        for row in rows:
            d = dataclasses.asdict(row)
            label = d.get("pattern") or d.get("model") or d.get("day") or "?"
            print(
                f"{label:<28}  calls={d['calls']:<5}  "
                f"in={d['input_tokens']:<8}  out={d['output_tokens']:<8}  "
                f"ms={int(d['elapsed_ms']):<7}  "
                f"$={d['estimated_cost_usd']:.4f}"
            )
        return 0

    if cmd == "top-costs":
        rows = agg.top_costs(args.n)
        if args.as_json:
            print(json.dumps(rows, indent=2))
            return 0
        if not rows:
            print(f"(no telemetry events yet at {agg.path})")
            return 0
        for r in rows:
            print(
                f"${r['estimated_cost_usd']:.4f}  {r.get('pattern') or '?':<24}  "
                f"{r.get('model') or '?':<20}  in={r.get('input_tokens') or 0}  "
                f"out={r.get('output_tokens') or 0}  ts={r.get('timestamp') or '-'}"
            )
        return 0

    if cmd == "cost":
        total = agg.total_cost()
        if args.as_json:
            print(json.dumps({"total_cost_usd": total}, indent=2))
        else:
            print(f"Total estimated cost: ${total:.4f}")
        return 0

    if cmd == "path":
        print(agg.path)
        return 0

    if cmd == "raw":
        for event in agg.iter_events():
            print(json.dumps(event))
        return 0

    parser.error(f"Unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
