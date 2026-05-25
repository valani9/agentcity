"""Implementation for the ``vstack-upgrade`` CLI.

Stays small and dependency-light. The PyPI lookup hits the JSON index
(no third-party HTTP client required); CHANGELOG parsing is a simple
heading scanner; version comparison uses ``packaging.version`` when
available and a fallback tuple-comparison when not.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PYPI_INDEX_URL = "https://pypi.org/pypi/valanistack/json"
"""PyPI JSON endpoint for the ``valanistack`` distribution."""


class UpgradeCheckError(RuntimeError):
    """Raised when the PyPI lookup fails or the response is malformed."""


@dataclass(frozen=True)
class UpgradeReport:
    """Summary of an upgrade check.

    Returned by :func:`run_upgrade_check`. The CLI renders this to a
    human-readable block; programmatic callers can inspect the fields
    directly.
    """

    current: str
    latest: str
    upgrade_available: bool
    install_command: str
    migration_notes: str
    """Markdown excerpt from CHANGELOG.md spanning every released
    version strictly newer than ``current`` up to and including
    ``latest``. Empty if no notes were found."""


def get_current_version() -> str:
    """Return the runtime ``vstack.__version__`` if importable, else ``"0.0.0"``.

    Failing soft means ``vstack-upgrade`` keeps working if the user
    runs it outside an installed environment (e.g., from a checkout
    on a Python that can't import the wheel for some reason).
    """
    try:
        import vstack

        return getattr(vstack, "__version__", "0.0.0")
    except Exception:
        return "0.0.0"


def fetch_latest_version(
    *,
    index_url: str = DEFAULT_PYPI_INDEX_URL,
    timeout: float = 5.0,
    allow_prereleases: bool = False,
) -> str:
    """Return the highest version string PyPI lists for ``valanistack``.

    Set ``allow_prereleases=True`` to include 0.x.dev / rc tags; the
    default skips them so a stable release never points users at a
    dev build.
    """
    req = urllib.request.Request(
        index_url,
        headers={"User-Agent": "vstack-upgrade/0.3.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - HTTPS PyPI
            body = resp.read()
    except (urllib.error.URLError, TimeoutError) as e:
        raise UpgradeCheckError(f"PyPI lookup failed: {e}") from e

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise UpgradeCheckError(f"PyPI returned non-JSON body: {e}") from e

    releases = payload.get("releases") or {}
    if not isinstance(releases, dict):
        raise UpgradeCheckError("PyPI returned no releases for valanistack.")

    candidates: list[str] = []
    for v, files in releases.items():
        if not files:
            # yanked / empty release; skip.
            continue
        if not allow_prereleases and _is_prerelease(v):
            continue
        candidates.append(v)

    if not candidates:
        # Fall back to the info field if filtering left us empty.
        info_version = (payload.get("info") or {}).get("version")
        if isinstance(info_version, str):
            return info_version
        raise UpgradeCheckError("No suitable valanistack release on PyPI.")

    candidates.sort(key=_version_key, reverse=True)
    return candidates[0]


def is_newer(current: str, candidate: str) -> bool:
    """Return ``True`` iff ``candidate`` sorts above ``current``."""
    return _version_key(candidate) > _version_key(current)


def parse_changelog_sections(text: str) -> list[tuple[str, str]]:
    """Split a Keep-a-Changelog-style CHANGELOG into (version, body) pairs.

    Recognizes headings in the form ``## [X.Y.Z] -- date`` (the format
    the vstack CHANGELOG uses). Returns sections in document order.
    """
    sections: list[tuple[str, str]] = []
    current_version: str | None = None
    current_body: list[str] = []

    header_re = re.compile(r"^##\s+\[?([0-9]+(?:\.[0-9]+){1,3}(?:[a-zA-Z0-9.-]*))\]?")
    for line in text.splitlines():
        m = header_re.match(line)
        if m:
            if current_version is not None:
                sections.append((current_version, "\n".join(current_body).rstrip()))
            current_version = m.group(1)
            current_body = [line]
        else:
            if current_version is not None:
                current_body.append(line)
    if current_version is not None:
        sections.append((current_version, "\n".join(current_body).rstrip()))
    return sections


def migration_notes_for(
    current: str,
    latest: str,
    *,
    changelog_path: Path | str | None = None,
    changelog_text: str | None = None,
) -> str:
    """Return CHANGELOG sections strictly between ``current`` and ``latest``.

    Reads from ``changelog_path`` (defaults to ``CHANGELOG.md`` in the
    installed wheel's parent directory; falls back to the repo root
    relative to ``vstack/__init__.py``) or from ``changelog_text``
    when supplied directly (used by tests). Returns an empty string
    if no matching section is found, which the CLI surfaces as
    "no migration notes available."
    """
    if changelog_text is None:
        path = _resolve_changelog_path(changelog_path)
        if path is None or not path.exists():
            return ""
        changelog_text = path.read_text(encoding="utf-8")
    sections = parse_changelog_sections(changelog_text)
    keep: list[str] = []
    for version, body in sections:
        if is_newer(current, version) and not is_newer(latest, version):
            keep.append(body)
        elif version == latest:
            keep.append(body)
    return "\n\n".join(keep).strip()


def run_upgrade_check(
    *,
    index_url: str = DEFAULT_PYPI_INDEX_URL,
    timeout: float = 5.0,
    allow_prereleases: bool = False,
    changelog_path: Path | str | None = None,
) -> UpgradeReport:
    """High-level entry point used by the CLI.

    Combines :func:`get_current_version`, :func:`fetch_latest_version`,
    and :func:`migration_notes_for` into one call.
    """
    current = get_current_version()
    latest = fetch_latest_version(
        index_url=index_url, timeout=timeout, allow_prereleases=allow_prereleases
    )
    upgrade = is_newer(current, latest)
    notes = migration_notes_for(current, latest, changelog_path=changelog_path) if upgrade else ""
    return UpgradeReport(
        current=current,
        latest=latest,
        upgrade_available=upgrade,
        install_command=f"pip install --upgrade 'valanistack=={latest}'",
        migration_notes=notes,
    )


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _version_key(version: str) -> tuple[object, ...]:
    """Best-effort version key suitable for sorting.

    Prefers ``packaging.version.Version`` when present (handles
    everything PyPI allows); falls back to splitting on dots and
    treating numeric components as ints, non-numeric as strings.
    """
    try:
        from packaging.version import Version

        try:
            return (0, Version(version))
        except Exception:  # noqa: BLE001 - InvalidVersion
            pass
    except ImportError:  # pragma: no cover - packaging always ships with pip
        pass

    parts: list[object] = []
    for piece in re.split(r"[.+-]", version):
        if piece.isdigit():
            parts.append(int(piece))
        else:
            parts.append(piece)
    return (1, tuple(parts))


def _is_prerelease(version: str) -> bool:
    """Conservative pre-release detector for the fallback path."""
    return any(tag in version.lower() for tag in ("a", "b", "rc", "dev", "pre"))


def _resolve_changelog_path(supplied: Path | str | None) -> Path | None:
    """Find CHANGELOG.md relative to the installed wheel or repo root."""
    if supplied is not None:
        return Path(supplied)
    try:
        import vstack as v
    except Exception:
        return None
    init = Path(v.__file__).resolve()
    # ``vstack/__init__.py`` -> wheel root is its parent's parent
    for candidate in (init.parent / "CHANGELOG.md", init.parent.parent / "CHANGELOG.md"):
        if candidate.exists():
            return candidate
    return None
