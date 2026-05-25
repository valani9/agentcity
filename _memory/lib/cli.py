"""``vstack-config`` CLI -- read / write user preferences in ``~/.vstack/``.

Mirrors the shape of ``gstack-config``: get / set / list / unset /
path. Stays intentionally small -- complex flows (telemetry sink
configuration, plugin enablement) earn their own subcommand when
they exist, not before.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Sequence

from ._config import (
    KNOWN_KEYS,
    ConfigError,
    delete_key,
    get_key,
    list_config,
    set_key,
)
from ._home import (
    get_analytics_dir,
    get_baselines_dir,
    get_home,
    get_sessions_dir,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vstack-config",
        description=(
            "Read / write vstack user preferences stored at "
            "~/.vstack/config.json (override via VSTACK_HOME)."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    p_get = sub.add_parser("get", help="Print the value of one config key.")
    p_get.add_argument("key", help="Config key to read.")
    p_get.add_argument(
        "--default",
        default=None,
        help="Fallback to print if the key is unset (defaults vary per key).",
    )

    p_set = sub.add_parser("set", help="Set a config key.")
    p_set.add_argument("key", help="Config key to set.")
    p_set.add_argument("value", help="New value (stored as a JSON string).")

    sub.add_parser("list", help="Print every known config key and its current value.")

    p_unset = sub.add_parser("unset", help="Delete one config key.")
    p_unset.add_argument("key", help="Config key to remove.")

    p_path = sub.add_parser(
        "path", help="Print the resolved ~/.vstack/ home directory or a subpath."
    )
    p_path.add_argument(
        "kind",
        nargs="?",
        default="home",
        choices=("home", "baselines", "sessions", "analytics", "config"),
        help="Which path to print (default: home).",
    )

    sub.add_parser("keys", help="List documented config keys and their descriptions.")

    p_install = sub.add_parser(
        "install-skills",
        help=(
            "Copy the bundled vstack Claude Code skills into the directory "
            "configured by 'skills_install_path' (default: ~/.claude/skills/vstack)."
        ),
    )
    p_install.add_argument(
        "--source",
        default=None,
        help=(
            "Source directory to copy from. Defaults to the _skills/ folder "
            "shipped alongside the installed vstack wheel."
        ),
    )
    p_install.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files at the destination.",
    )
    p_install.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned copies without touching the filesystem.",
    )

    p_gen = sub.add_parser(
        "gen-platform",
        help=(
            "Print a ready-to-paste config snippet for a non-MCP-default "
            "AI client (cursor / cline / continue / roo-code / windsurf / "
            "zed / aider / goose / kiro / openclaw / codex-cli / opencode "
            "/ docker-compose)."
        ),
    )
    p_gen.add_argument(
        "platform",
        nargs="?",
        default=None,
        help="Platform identifier. Omit to list available platforms.",
    )
    p_gen.add_argument(
        "--list",
        action="store_true",
        help="List supported platform identifiers and exit.",
    )
    p_gen.add_argument(
        "--write",
        action="store_true",
        help=(
            "Write the snippet to the suggested path (or to --out) "
            "instead of printing it. Refuses to overwrite without --force."
        ),
    )
    p_gen.add_argument(
        "--out",
        default=None,
        help="Override the destination path for --write.",
    )
    p_gen.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing file when --write is set.",
    )

    args = parser.parse_args(argv)
    cmd = args.command or "list"

    try:
        if cmd == "get":
            return _cmd_get(args.key, args.default)
        if cmd == "set":
            return _cmd_set(args.key, args.value)
        if cmd == "list":
            return _cmd_list()
        if cmd == "unset":
            return _cmd_unset(args.key)
        if cmd == "path":
            return _cmd_path(args.kind)
        if cmd == "keys":
            return _cmd_keys()
        if cmd == "install-skills":
            return _cmd_install_skills(source=args.source, force=args.force, dry_run=args.dry_run)
        if cmd == "gen-platform":
            return _cmd_gen_platform(
                platform=args.platform,
                list_only=args.list,
                write=args.write,
                out=args.out,
                force=args.force,
            )
    except ConfigError as e:
        print(f"vstack-config: {e}", file=sys.stderr)
        return 2

    parser.error(f"Unknown command: {cmd}")
    return 2


def _cmd_get(key: str, default: str | None) -> int:
    value = get_key(key)
    if value is None:
        value = default
    if value is None:
        # Unknown + no fallback -> empty stdout, non-zero exit so callers
        # can distinguish "unset" from "set to empty string".
        return 1
    print(_format_value(value))
    return 0


def _cmd_set(key: str, raw_value: str) -> int:
    set_key(key, _coerce_value(raw_value))
    return 0


def _cmd_unset(key: str) -> int:
    removed = delete_key(key)
    return 0 if removed else 1


def _cmd_list() -> int:
    snapshot = list_config()
    width = max((len(k) for k in snapshot), default=0)
    for key in sorted(snapshot):
        value = snapshot[key]
        marker = "  " if key in KNOWN_KEYS else "* "
        print(f"{marker}{key:<{width}}  {_format_value(value)}")
    return 0


def _cmd_path(kind: str) -> int:
    paths = {
        "home": get_home(),
        "baselines": get_baselines_dir(),
        "sessions": get_sessions_dir(),
        "analytics": get_analytics_dir(),
        "config": get_home() / "config.json",
    }
    print(paths[kind])
    return 0


def _cmd_keys() -> int:
    width = max(len(k) for k in KNOWN_KEYS)
    for key in sorted(KNOWN_KEYS):
        default, desc = KNOWN_KEYS[key]
        print(f"{key:<{width}}  default={_format_value(default)!s}\n  {desc}\n")
    return 0


def _cmd_install_skills(*, source: str | None, force: bool, dry_run: bool) -> int:
    src_path = _resolve_skills_source(source)
    if src_path is None or not src_path.is_dir():
        print(
            "vstack-config install-skills: bundled _skills/ directory not found. "
            "Clone https://github.com/valani9/vstack and pass "
            "--source path/to/_skills/.",
            file=sys.stderr,
        )
        return 2

    dest_raw = get_key("skills_install_path") or "~/.claude/skills/vstack"
    if not isinstance(dest_raw, str):
        dest_raw = str(dest_raw)
    dest = Path(os.path.expanduser(dest_raw)).resolve()

    plan: list[tuple[Path, Path]] = []
    for child in sorted(src_path.iterdir()):
        target = dest / child.name
        plan.append((child, target))

    print(f"Source: {src_path}")
    print(f"Destination: {dest}")
    print()
    for src, target in plan:
        kind = "DIR " if src.is_dir() else "FILE"
        action = "DRYRUN" if dry_run else (" SKIP " if target.exists() and not force else " COPY ")
        print(f"  {action} {kind} {src.name}")

    if dry_run:
        return 0

    dest.mkdir(parents=True, exist_ok=True)
    for src, target in plan:
        if target.exists() and not force:
            continue
        if src.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
        else:
            shutil.copy2(src, target)

    print()
    print(
        "Done. Restart your Claude Code client to pick up the new skills, "
        "or re-run with --force to overwrite an existing install."
    )
    return 0


def _resolve_skills_source(supplied: str | None) -> Path | None:
    """Find the bundled _skills/ directory.

    Order of resolution:
      1. ``--source`` flag if provided.
      2. ``_skills/`` next to the installed wheel's vstack/ folder.
      3. ``_skills/`` two levels up from the installed wheel (repo checkout).
    """
    if supplied is not None:
        return Path(supplied).expanduser().resolve()
    try:
        import vstack as _v

        wheel_root = Path(_v.__file__).resolve().parent
    except Exception:
        return None
    for candidate in (
        wheel_root.parent / "_skills",
        wheel_root.parent.parent / "_skills",
    ):
        if candidate.is_dir():
            return candidate
    return None


def _cmd_gen_platform(
    *,
    platform: str | None,
    list_only: bool,
    write: bool,
    out: str | None,
    force: bool,
) -> int:
    from ._platforms import generate, list_platforms

    if list_only or platform is None:
        for name in list_platforms():
            print(name)
        return 0
    try:
        snippet = generate(platform)
    except KeyError as e:
        print(f"vstack-config: {e}", file=sys.stderr)
        return 2

    if not write:
        print(f"# Platform: {snippet.platform}")
        print(f"# Suggested path: {snippet.suggested_path}")
        print(f"# Notes: {snippet.notes}")
        print()
        print(snippet.body)
        return 0

    if out is None:
        # Heuristic: take the first whitespace-delimited token as the path
        # when the suggested-path string is multi-clause; users overriding
        # should pass --out explicitly.
        candidate = snippet.suggested_path.split(" ", 1)[0]
        if candidate.startswith("~") or candidate.startswith("/") or candidate.startswith("./"):
            out = candidate
        else:
            print(
                f"vstack-config gen-platform --write needs --out for {platform!r}: "
                f"suggested path '{snippet.suggested_path}' is ambiguous.",
                file=sys.stderr,
            )
            return 2

    dest = Path(os.path.expanduser(out)).resolve()
    if dest.exists() and not force:
        print(
            f"vstack-config: refusing to overwrite {dest}; pass --force to replace.",
            file=sys.stderr,
        )
        return 2
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(snippet.body + "\n", encoding="utf-8")
    print(f"Wrote {dest}")
    return 0


def _format_value(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _coerce_value(raw: str) -> object:
    """Best-effort JSON parse of the CLI value.

    Numbers, booleans, ``null``, and JSON objects round-trip; everything
    else is stored as a string. This matches the user expectation that
    ``vstack-config set api_port 9000`` stores a number, not the string
    ``"9000"``, while ``vstack-config set default_mode forensic`` stores
    the literal token.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


if __name__ == "__main__":
    sys.exit(main())
