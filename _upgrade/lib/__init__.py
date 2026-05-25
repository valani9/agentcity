"""vstack.upgrade -- check PyPI for newer valanistack releases and
print human-readable migration notes.

Three functions back the ``vstack-upgrade`` CLI:

* :func:`get_current_version` -- the runtime ``vstack.__version__``
* :func:`fetch_latest_version` -- the highest non-pre-release version
  on PyPI for the ``valanistack`` distribution. Performs a single
  HTTPS GET against ``https://pypi.org/pypi/valanistack/json``.
* :func:`migration_notes_for` -- the relevant CHANGELOG.md section
  between two versions.

The default CLI flow is dry-run only -- it prints what would happen
and points the user at the right ``pip install`` invocation. We
intentionally do NOT exec pip ourselves; package managers vary
(pipx vs. user-site vs. uv vs. system) and the right thing to do is
let the user run it.
"""

from ._upgrade import (
    DEFAULT_PYPI_INDEX_URL,
    UpgradeCheckError,
    UpgradeReport,
    fetch_latest_version,
    get_current_version,
    is_newer,
    migration_notes_for,
    parse_changelog_sections,
    run_upgrade_check,
)

__all__ = [
    "DEFAULT_PYPI_INDEX_URL",
    "UpgradeCheckError",
    "UpgradeReport",
    "fetch_latest_version",
    "get_current_version",
    "is_newer",
    "migration_notes_for",
    "parse_changelog_sections",
    "run_upgrade_check",
]

__version__ = "0.3.0"
