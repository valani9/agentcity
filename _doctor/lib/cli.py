"""``vstack-doctor`` CLI."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from ._doctor import HealthStatus, run_all_checks


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vstack-doctor",
        description=(
            "Audit your vstack install. Walks the registered surfaces, "
            "optional extras, env vars, and PyPI version; prints a "
            "status report with actionable hints for anything not OK."
        ),
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit a machine-readable JSON report instead of pretty text.",
    )
    parser.add_argument(
        "--skip-network",
        action="store_true",
        help="Skip the PyPI upgrade check (useful for offline / CI runs).",
    )
    parser.add_argument(
        "--only-errors",
        action="store_true",
        help="Print only checks with status=error.",
    )
    args = parser.parse_args(argv)

    report = run_all_checks(skip_network=args.skip_network)

    if args.as_json:
        body = {
            "has_errors": report.has_errors,
            "has_warnings": report.has_warnings,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "summary": c.summary,
                    "hint": c.hint,
                    "detail": c.detail,
                }
                for c in report.checks
            ],
        }
        print(json.dumps(body, indent=2))
        return 0 if not report.has_errors else 1

    icons = {
        HealthStatus.OK: "OK ",
        HealthStatus.WARNING: "WARN",
        HealthStatus.ERROR: "ERR ",
    }
    width = max((len(c.name) for c in report.checks), default=0)
    for check in report.checks:
        if args.only_errors and check.status != HealthStatus.ERROR:
            continue
        line = f"  [{icons[check.status]}] {check.name:<{width}}  {check.summary}"
        print(line)
        if check.hint:
            print(f"         hint: {check.hint}")
    print()
    if report.has_errors:
        print("Doctor found ERROR-level issues; fix them before relying on vstack.")
        return 1
    if report.has_warnings:
        print("Doctor found warnings (optional extras / advisory items).")
        return 0
    print("Doctor: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
