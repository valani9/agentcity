"""``vstack-upgrade`` CLI -- print whether a newer PyPI release exists."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from ._upgrade import (
    DEFAULT_PYPI_INDEX_URL,
    UpgradeCheckError,
    run_upgrade_check,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vstack-upgrade",
        description=(
            "Check PyPI for newer valanistack releases and print "
            "migration notes from CHANGELOG.md. Does NOT run pip; "
            "the user runs the printed install command themselves."
        ),
    )
    parser.add_argument(
        "--index-url",
        default=DEFAULT_PYPI_INDEX_URL,
        help=f"PyPI JSON endpoint (default: {DEFAULT_PYPI_INDEX_URL}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HTTP timeout in seconds (default: 5.0).",
    )
    parser.add_argument(
        "--allow-prereleases",
        action="store_true",
        help="Include 0.x.dev / rc / pre releases when picking the latest.",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit a JSON object instead of human-readable text.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Exit 0 with no output if no upgrade is available (useful in CI).",
    )

    args = parser.parse_args(argv)

    try:
        report = run_upgrade_check(
            index_url=args.index_url,
            timeout=args.timeout,
            allow_prereleases=args.allow_prereleases,
        )
    except UpgradeCheckError as e:
        message = f"vstack-upgrade: {e}"
        if args.as_json:
            print(json.dumps({"error": str(e)}))
        else:
            print(message, file=sys.stderr)
        return 2

    if args.as_json:
        print(
            json.dumps(
                {
                    "current": report.current,
                    "latest": report.latest,
                    "upgrade_available": report.upgrade_available,
                    "install_command": report.install_command,
                    "migration_notes": report.migration_notes,
                },
                indent=2,
            )
        )
        return 0 if not report.upgrade_available else 1

    if args.quiet and not report.upgrade_available:
        return 0

    if not report.upgrade_available:
        print(f"valanistack {report.current} is up to date (latest on PyPI: {report.latest}).")
        return 0

    print(
        f"valanistack upgrade available: {report.current} -> {report.latest}\n"
        f"Install command:\n  {report.install_command}\n"
    )
    if report.migration_notes:
        print("Migration notes:\n")
        print(report.migration_notes)
    else:
        print(
            "(No CHANGELOG entries found between the installed version and the latest "
            "release. Check https://github.com/valani9/vstack/releases for context.)"
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
