"""Resolve and lazily create vstack's home directory.

The home directory holds calibration baselines, session history,
user-preference config, and optional telemetry analytics. Tests
override the root via the ``VSTACK_HOME`` environment variable so
nothing leaks into a developer's real ``~/.vstack/`` during a run.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULT_HOME_ENV = "VSTACK_HOME"
"""Name of the environment variable consulted before falling back to
``~/.vstack/``. Tests should set this in a tmp_path fixture."""


def get_home(*, create: bool = True, env: dict[str, str] | None = None) -> Path:
    """Return the vstack home directory.

    Parameters
    ----------
    create:
        If true (the default), creates the directory if it does not
        exist. Callers that only want to *test* for existence should
        pass ``create=False``.
    env:
        Environment dict (defaults to ``os.environ``). Made injectable
        so tests can exercise ``VSTACK_HOME`` resolution without
        mutating the global environment.
    """
    env = env if env is not None else dict(os.environ)
    raw = env.get(DEFAULT_HOME_ENV)
    if raw:
        home = Path(raw).expanduser().resolve()
    else:
        home = Path.home() / ".vstack"
    if create:
        home.mkdir(parents=True, exist_ok=True)
    return home


def get_baselines_dir(*, create: bool = True) -> Path:
    """Return ``~/.vstack/baselines/``.

    Each vstack pattern that supports calibration writes its baseline
    JSON under this directory. The per-pattern filename follows
    :func:`baseline_path_for`.
    """
    path = get_home(create=create) / "baselines"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def get_sessions_dir(*, create: bool = True) -> Path:
    """Return ``~/.vstack/sessions/``.

    Reserved for session-history JSONL files. v0.3.0 ships the
    directory and helpers; no callers populate it yet. The directory
    is created lazily so users who never opt into session logging
    don't end up with empty folders.
    """
    path = get_home(create=create) / "sessions"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def get_analytics_dir(*, create: bool = True) -> Path:
    """Return ``~/.vstack/analytics/``.

    Reserved for opt-in telemetry sink output. Off by default; the
    directory is created on demand by callers that wire a sink to
    write here.
    """
    path = get_home(create=create) / "analytics"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_path() -> Path:
    """Return ``~/.vstack/config.json`` (file is created on first write)."""
    return get_home() / "config.json"


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def baseline_path_for(pattern_name: str) -> Path:
    """Return the canonical baseline path for one pattern.

    Use the pattern's ``import_name`` (e.g. ``"lewin"``,
    ``"schein_culture"``). Path is ``~/.vstack/baselines/<name>.json``.
    Validates that the pattern name is a safe identifier so callers
    can't slip a path-traversal segment into the baselines dir.
    """
    if not pattern_name or not _SAFE_NAME.fullmatch(pattern_name):
        raise ValueError(
            f"Unsafe pattern name for baseline path: {pattern_name!r}. "
            "Pattern names must match [A-Za-z0-9_-]+."
        )
    return get_baselines_dir() / f"{pattern_name}.json"
