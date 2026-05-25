"""Tests for ``vstack.doctor``."""

from __future__ import annotations

import json

import pytest

import vstack.doctor as doctor
from vstack.doctor._doctor import (
    HealthStatus,
    _check_api_security_posture,
    _check_cli_on_path,
    _check_home_dir,
    _check_pattern_registry,
    _check_python_version,
    _check_vstack_version,
    run_all_checks,
)
from vstack.doctor.cli import main as cli_main


def test_python_version_ok() -> None:
    result = _check_python_version()
    assert result.status == HealthStatus.OK
    assert "Python" in result.summary


def test_vstack_version_ok() -> None:
    result = _check_vstack_version()
    assert result.status == HealthStatus.OK
    assert "valanistack" in result.summary


def test_pattern_registry_ok() -> None:
    result = _check_pattern_registry()
    assert result.status == HealthStatus.OK
    assert "34" in result.summary


def test_home_dir_writable(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("VSTACK_HOME", str(tmp_path))
    result = _check_home_dir()
    assert result.status == HealthStatus.OK


def test_cli_on_path_missing() -> None:
    result = _check_cli_on_path("definitely-not-a-real-cli-zzz")
    assert result.status == HealthStatus.ERROR


def test_api_security_warns_on_require_without_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VSTACK_API_REQUIRE_AUTH", "true")
    monkeypatch.delenv("VSTACK_API_KEYS", raising=False)
    monkeypatch.delenv("VSTACK_API_KEYS_FILE", raising=False)
    result = _check_api_security_posture()
    assert result.status == HealthStatus.ERROR


def test_api_security_ok_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VSTACK_API_REQUIRE_AUTH", raising=False)
    monkeypatch.delenv("VSTACK_API_KEYS", raising=False)
    monkeypatch.delenv("VSTACK_API_KEYS_FILE", raising=False)
    result = _check_api_security_posture()
    assert result.status == HealthStatus.OK


def test_run_all_checks_returns_report() -> None:
    report = run_all_checks(skip_network=True)
    assert report.checks
    # Every check has a name + status + summary.
    for c in report.checks:
        assert c.name
        assert isinstance(c.status, HealthStatus)
        assert c.summary


def test_run_all_checks_skip_network_excludes_pypi() -> None:
    report = run_all_checks(skip_network=True)
    names = {c.name for c in report.checks}
    assert "pypi_upgrade" not in names


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_cli_default_text_output(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    rc = cli_main(["--skip-network"])
    # rc is 0 when no ERROR-level findings; rc is 1 when there are.
    # Either is fine for this test; we just check the format.
    assert rc in (0, 1)
    out = capsys.readouterr().out
    assert "vstack_version" in out


def test_cli_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["--skip-network", "--json"])
    assert rc in (0, 1)
    body = json.loads(capsys.readouterr().out)
    assert "checks" in body
    assert "has_errors" in body
    assert "has_warnings" in body
    assert any(c["name"] == "vstack_version" for c in body["checks"])


def test_cli_only_errors(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["--skip-network", "--only-errors"])
    assert rc in (0, 1)
    # No assertion on stdout content -- some environments will have
    # zero errors and others (e.g. missing optional extras as the
    # default state) won't actually error -- just verify it doesn't
    # crash.


def test_module_exports() -> None:
    for name in ("CheckResult", "DoctorReport", "HealthStatus", "run_all_checks"):
        assert name in doctor.__all__
    assert doctor.__version__
