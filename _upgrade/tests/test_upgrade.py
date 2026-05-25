"""Tests for ``vstack.upgrade``.

All HTTP traffic is mocked at the ``urllib.request.urlopen`` boundary
so the suite never touches the public PyPI.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest import mock

import pytest

import vstack.upgrade as upgrade
from vstack.upgrade.cli import main as cli_main


def _make_pypi_response(versions: dict[str, list[dict]], info_version: str | None = None) -> bytes:
    """Return a bytes blob shaped like the PyPI JSON index response."""
    return json.dumps(
        {
            "info": {"name": "valanistack", "version": info_version or ""},
            "releases": versions,
        }
    ).encode("utf-8")


def _patch_urlopen(body: bytes):
    return mock.patch("urllib.request.urlopen", return_value=io.BytesIO(body))


def test_get_current_version_returns_string() -> None:
    v = upgrade.get_current_version()
    assert isinstance(v, str)
    assert v  # non-empty


def test_is_newer_simple() -> None:
    assert upgrade.is_newer("0.1.0", "0.2.0")
    assert upgrade.is_newer("0.2.0", "0.2.1")
    assert upgrade.is_newer("0.2.0", "1.0.0")
    assert not upgrade.is_newer("0.2.0", "0.2.0")
    assert not upgrade.is_newer("0.3.0", "0.2.0")


def test_fetch_latest_picks_highest_stable() -> None:
    payload = _make_pypi_response(
        {
            "0.1.0": [{"filename": "x"}],
            "0.2.0": [{"filename": "y"}],
            "0.3.0rc1": [{"filename": "z"}],
            "0.2.1": [{"filename": "w"}],
        }
    )
    with _patch_urlopen(payload):
        latest = upgrade.fetch_latest_version()
    assert latest == "0.2.1"


def test_fetch_latest_allow_prereleases() -> None:
    payload = _make_pypi_response(
        {
            "0.2.0": [{"filename": "y"}],
            "0.3.0rc1": [{"filename": "z"}],
        }
    )
    with _patch_urlopen(payload):
        latest = upgrade.fetch_latest_version(allow_prereleases=True)
    assert latest == "0.3.0rc1"


def test_fetch_latest_skips_yanked_releases() -> None:
    payload = _make_pypi_response(
        {
            "0.1.0": [{"filename": "x"}],
            "0.2.0": [],  # yanked / empty
            "0.1.1": [{"filename": "y"}],
        }
    )
    with _patch_urlopen(payload):
        latest = upgrade.fetch_latest_version()
    assert latest == "0.1.1"


def test_fetch_latest_falls_back_to_info_version() -> None:
    payload = _make_pypi_response({}, info_version="0.9.9")
    with _patch_urlopen(payload):
        latest = upgrade.fetch_latest_version()
    assert latest == "0.9.9"


def test_fetch_latest_raises_on_http_failure() -> None:
    import urllib.error

    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("boom")):
        with pytest.raises(upgrade.UpgradeCheckError):
            upgrade.fetch_latest_version()


def test_parse_changelog_sections() -> None:
    text = (
        "# Changelog\n\n"
        "Intro.\n\n"
        "## [0.3.0] -- 2026-05-26\n"
        "Added thing A.\n\n"
        "## [0.2.0] -- 2026-05-25\n"
        "Added thing B.\n"
    )
    sections = upgrade.parse_changelog_sections(text)
    assert [v for v, _ in sections] == ["0.3.0", "0.2.0"]
    assert "thing A" in sections[0][1]
    assert "thing B" in sections[1][1]


def test_migration_notes_filters_to_relevant_range() -> None:
    text = (
        "## [0.5.0] -- 2026-06-01\nNew 0.5\n\n"
        "## [0.4.0] -- 2026-05-30\nNew 0.4\n\n"
        "## [0.3.0] -- 2026-05-26\nNew 0.3\n\n"
        "## [0.2.0] -- 2026-05-25\nNew 0.2\n"
    )
    notes = upgrade.migration_notes_for("0.2.0", "0.4.0", changelog_text=text)
    assert "New 0.3" in notes
    assert "New 0.4" in notes
    assert "New 0.5" not in notes
    assert "New 0.2" not in notes


def test_migration_notes_empty_when_changelog_missing(tmp_path: Path) -> None:
    notes = upgrade.migration_notes_for("0.1.0", "0.2.0", changelog_path=tmp_path / "absent.md")
    assert notes == ""


def test_run_upgrade_check_combines_outputs(tmp_path: Path) -> None:
    payload = _make_pypi_response({"0.99.0": [{"filename": "y"}]})
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## [0.99.0] -- 2026-12-01\nBig changes.\n", encoding="utf-8")
    with _patch_urlopen(payload):
        report = upgrade.run_upgrade_check(changelog_path=changelog)
    assert report.upgrade_available is True
    assert report.latest == "0.99.0"
    assert "Big changes" in report.migration_notes
    assert "pip install --upgrade 'valanistack==0.99.0'" in report.install_command


def test_cli_no_upgrade(capsys: pytest.CaptureFixture[str]) -> None:
    payload = _make_pypi_response({"0.0.0": [{"filename": "x"}]})
    with _patch_urlopen(payload):
        rc = cli_main([])
    assert rc == 0
    assert "up to date" in capsys.readouterr().out


def test_cli_upgrade_available_returns_1(capsys: pytest.CaptureFixture[str]) -> None:
    payload = _make_pypi_response({"99.0.0": [{"filename": "x"}]})
    with _patch_urlopen(payload):
        rc = cli_main([])
    assert rc == 1
    out = capsys.readouterr().out
    assert "upgrade available" in out
    assert "pip install --upgrade" in out


def test_cli_quiet_no_upgrade_silent(capsys: pytest.CaptureFixture[str]) -> None:
    payload = _make_pypi_response({"0.0.0": [{"filename": "x"}]})
    with _patch_urlopen(payload):
        rc = cli_main(["--quiet"])
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_cli_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    payload = _make_pypi_response({"99.0.0": [{"filename": "x"}]})
    with _patch_urlopen(payload):
        rc = cli_main(["--json"])
    assert rc == 1
    body = json.loads(capsys.readouterr().out)
    assert body["latest"] == "99.0.0"
    assert body["upgrade_available"] is True


def test_cli_handles_http_error(capsys: pytest.CaptureFixture[str]) -> None:
    import urllib.error

    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("boom")):
        rc = cli_main([])
    assert rc == 2
    assert "vstack-upgrade" in capsys.readouterr().err
