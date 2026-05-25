#!/usr/bin/env python3
"""Render a GitHub Release body from RELEASE_TEMPLATE.md + CHANGELOG.md.

Looks up the section matching the version (``## [0.7.0] ...`` or
``## [Unreleased]`` as a fallback) and substitutes it into the
template's ``{{ changelog_section }}`` placeholder. ``{{ version }}``
is also substituted.

Intended to run inside release.yml; no external dependencies.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _extract_section(changelog: str, version: str) -> str:
    """Return the body of the ``## [{version}] ...`` section, stripped.

    Falls back to ``## [Unreleased]`` if the exact version section is
    not found (so a release tagged before the changelog is updated
    still gets reasonable notes).
    """

    patterns = [
        rf"^##\s*\[{re.escape(version)}\][^\n]*\n",
        r"^##\s*\[Unreleased\][^\n]*\n",
    ]
    for pat in patterns:
        m = re.search(pat, changelog, flags=re.MULTILINE)
        if m is None:
            continue
        start = m.end()
        end_match = re.search(r"^##\s+", changelog[start:], flags=re.MULTILINE)
        end = start + end_match.start() if end_match else len(changelog)
        body = changelog[start:end].strip()
        if body:
            return body
    return (
        f"See [CHANGELOG.md](https://github.com/valani9/vstack/blob/main/"
        f"CHANGELOG.md) for full notes on {version}."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--changelog", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    template = args.template.read_text(encoding="utf-8")
    changelog = args.changelog.read_text(encoding="utf-8")

    section = _extract_section(changelog, args.version)
    rendered = template.replace("{{ version }}", args.version).replace(
        "{{ changelog_section }}", section
    )

    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output} ({len(rendered)} chars)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
