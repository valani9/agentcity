"""``vstack-bench`` CLI -- run benchmark + comparative-eval suites."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

from ._comparative import ComparativeCase, comparative_table, run_comparative
from ._harness import (
    BenchmarkRunner,
    BenchmarkSuite,
    canonical_suite,
    load_suite,
    save_report,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vstack-bench",
        description=(
            "Run vstack benchmark + comparative-eval suites. Real LLM "
            "spend happens unless you set VSTACK_MCP_LLM=stub or pass "
            "--stub (intended for CI / sanity checks)."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="Run a benchmark suite end-to-end.")
    p_run.add_argument(
        "suite",
        default="canonical",
        nargs="?",
        help="Suite name ('canonical') or path to a suite JSON file.",
    )
    p_run.add_argument(
        "--out",
        default=None,
        help="Directory to write the run report into (default: stdout-only).",
    )
    p_run.add_argument(
        "--stub",
        action="store_true",
        help="Use a no-LLM stub client (most patterns will validation-error; useful as a smoke test).",
    )

    p_compare = sub.add_parser(
        "compare",
        help="Run a suite across quick / standard / forensic and print the cost-quality table.",
    )
    p_compare.add_argument("suite", default="canonical", nargs="?")
    p_compare.add_argument(
        "--mode",
        action="append",
        default=None,
        help="Restrict to these modes (repeat flag). Default: quick + standard + forensic.",
    )
    p_compare.add_argument("--stub", action="store_true")
    p_compare.add_argument("--json", dest="as_json", action="store_true")

    sub.add_parser("list", help="List the cases in the canonical suite.")

    args = parser.parse_args(argv)
    cmd = args.command or "list"

    if cmd == "list":
        return _cmd_list()
    if cmd == "run":
        return _cmd_run(args.suite, args.out, args.stub)
    if cmd == "compare":
        return _cmd_compare(args.suite, args.mode, args.stub, args.as_json)

    parser.error(f"Unknown command: {cmd}")
    return 2


def _resolve_suite(name: str) -> "BenchmarkSuite":
    if name == "canonical":
        return canonical_suite()
    return load_suite(name)


def _client_factory(stub: bool) -> "Callable[[], Any] | None":
    if stub:
        from vstack.aar import StubClient

        return lambda: StubClient([])
    return None  # falls back to vstack.mcp.resolve_llm_client


def _cmd_list() -> int:
    suite = canonical_suite()
    print(f"Suite: {suite.name}  ({suite.description})")
    for case in suite.cases:
        print(f"  {case.case_id:<48}  pattern={case.pattern:<18}  mode={case.mode}")
    return 0


def _cmd_run(suite_name: str, out: str | None, stub: bool) -> int:
    try:
        suite = _resolve_suite(suite_name)
    except FileNotFoundError:
        print(f"vstack-bench: suite not found: {suite_name}", file=sys.stderr)
        return 2
    runner = BenchmarkRunner(llm_client_factory=_client_factory(stub))
    report = runner.run(suite)
    summary = report.to_summary_dict()
    print(json.dumps(summary, indent=2))
    if out:
        path = save_report(report, Path(out))
        print(f"\nFull report written to: {path.parent}")
    return 0 if report.failed == 0 and report.errors == 0 else 1


def _cmd_compare(
    suite_name: str,
    modes: list[str] | None,
    stub: bool,
    as_json: bool,
) -> int:
    try:
        suite = _resolve_suite(suite_name)
    except FileNotFoundError:
        print(f"vstack-bench: suite not found: {suite_name}", file=sys.stderr)
        return 2

    chosen_modes = tuple(modes) if modes else ("quick", "standard", "forensic")
    comparative_cases = [
        ComparativeCase(case_id=c.case_id, pattern=c.pattern, trace=c.trace, modes=chosen_modes)
        for c in suite.cases
    ]
    reports = run_comparative(comparative_cases, llm_client_factory=_client_factory(stub))
    table = comparative_table(reports)
    if as_json:
        print(
            json.dumps(
                {
                    "table": table,
                    "agreements": [{"case_id": r.case_id, **r.agreement()} for r in reports],
                },
                indent=2,
                default=str,
            )
        )
        return 0
    print(f"{'case_id':<48} {'pattern':<20} {'mode':<10} {'ms':>8} {'sev':<10} {'dom':<28}")
    for row in table:
        print(
            f"{row['case_id']:<48} {row['pattern']:<20} {row['mode']:<10} "
            f"{int(row['elapsed_ms']):>8} {(row['severity'] or '-'):<10} "
            f"{(row['dominant'] or '-'):<28}"
        )
    print()
    for r in reports:
        agree = r.agreement()
        flag = "OK" if agree["fully_consistent"] else "DRIFT"
        print(
            f"  [{flag}] {r.case_id}  unique_dominant_findings={agree['unique_dominant_findings']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
