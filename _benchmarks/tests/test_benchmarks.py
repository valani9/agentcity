"""Tests for ``vstack.benchmarks``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import vstack.benchmarks as benchmarks
from vstack.aar import StubClient
from vstack.benchmarks._comparative import (
    ComparativeCase,
    _dominant_for,
    comparative_table,
    run_comparative,
)
from vstack.benchmarks._harness import (
    BenchmarkCase,
    BenchmarkRunner,
    BenchmarkSuite,
    canonical_suite,
    load_suite,
    save_report,
)
from vstack.benchmarks.cli import main as cli_main


def _stub() -> StubClient:
    return StubClient([])


# ----------------------------------------------------------------------
# canonical suite
# ----------------------------------------------------------------------


def test_canonical_suite_has_three_cases() -> None:
    suite = canonical_suite()
    assert suite.name == "canonical"
    assert len(suite.cases) == 3
    patterns = {c.pattern for c in suite.cases}
    assert patterns == {"lewin", "aar", "schein_culture"}


def test_canonical_cases_have_expectations() -> None:
    suite = canonical_suite()
    case_by_pattern = {c.pattern: c for c in suite.cases}
    assert case_by_pattern["lewin"].expected_dominant_field == "dominant_locus"
    assert case_by_pattern["aar"].expected_severity_set
    # Schein case is a smoke test only, no expectations.
    assert case_by_pattern["schein_culture"].expected_severity_set == ()


# ----------------------------------------------------------------------
# BenchmarkRunner: behaviour under the stub LLM
# ----------------------------------------------------------------------


def test_runner_produces_report_with_stub() -> None:
    runner = BenchmarkRunner(llm_client_factory=_stub)
    report = runner.run(canonical_suite())
    assert report.total == 3
    # Stub LLM means analyzers either validation-error or return
    # canned empty content -> most cases will fail expectations but
    # the harness itself never crashes.
    assert report.total == report.passed + report.failed + report.errors
    assert report.severity_distribution


def test_runner_unknown_pattern_records_error() -> None:
    suite = BenchmarkSuite(
        name="x",
        cases=[BenchmarkCase(case_id="bogus", pattern="does_not_exist", trace={"x": 1})],
    )
    runner = BenchmarkRunner(llm_client_factory=_stub)
    report = runner.run(suite)
    assert report.errors == 1
    assert "unknown_pattern" in (report.cases[0].error or "")


def test_runner_callback_fires_per_case() -> None:
    seen: list[str] = []
    runner = BenchmarkRunner(
        llm_client_factory=_stub,
        on_case_complete=lambda r: seen.append(r.case_id),
    )
    runner.run(canonical_suite())
    assert len(seen) == 3
    assert seen == [c.case_id for c in canonical_suite().cases]


# ----------------------------------------------------------------------
# load_suite + save_report IO
# ----------------------------------------------------------------------


def test_load_suite_from_json(tmp_path: Path) -> None:
    body = {
        "name": "custom",
        "description": "a tiny custom suite",
        "cases": [
            {
                "case_id": "c1",
                "pattern": "lewin",
                "mode": "quick",
                "trace": {
                    "task": "x",
                    "steps": [{"type": "input", "content": "y"}],
                    "outcome": "z",
                    "success": False,
                },
                "tags": ["smoke"],
            }
        ],
    }
    src = tmp_path / "suite.json"
    src.write_text(json.dumps(body), encoding="utf-8")
    suite = load_suite(src)
    assert suite.name == "custom"
    assert suite.cases[0].case_id == "c1"
    assert suite.cases[0].tags == ("smoke",)


def test_save_report_writes_summary_and_cases(tmp_path: Path) -> None:
    runner = BenchmarkRunner(llm_client_factory=_stub)
    report = runner.run(canonical_suite())
    summary_path = save_report(report, tmp_path / "run")
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text())
    assert summary["total"] == 3
    cases_dir = tmp_path / "run" / "cases"
    assert cases_dir.exists()
    files = list(cases_dir.glob("*.json"))
    assert len(files) == 3


# ----------------------------------------------------------------------
# Comparative harness
# ----------------------------------------------------------------------


def test_dominant_for_picks_locus() -> None:
    assert (
        _dominant_for({"dominant_locus": "environmental", "severity": "high"}, "lewin")
        == "environmental"
    )
    assert _dominant_for({"severity": "high"}, "lewin") == "high"
    assert _dominant_for({}, "lewin") is None
    assert _dominant_for("not a dict", "lewin") is None


def test_run_comparative_iterates_modes() -> None:
    cases = [
        ComparativeCase(
            case_id="c1",
            pattern="lewin",
            trace={
                "task": "x",
                "steps": [{"type": "input", "content": "y"}],
                "outcome": "z",
                "success": False,
            },
            modes=("quick", "standard"),
        )
    ]
    reports = run_comparative(cases, llm_client_factory=_stub)
    assert len(reports) == 1
    # Both modes are valid for lewin; harness ran both even though
    # they error out under the stub.
    assert {r.mode for r in reports[0].rows} == {"quick", "standard"}


def test_run_comparative_skips_invalid_modes() -> None:
    cases = [
        ComparativeCase(
            case_id="c1",
            pattern="lewin",
            trace={"task": "x", "steps": [], "outcome": "z", "success": False},
            modes=("bogus", "standard"),
        )
    ]
    reports = run_comparative(cases, llm_client_factory=_stub)
    assert {r.mode for r in reports[0].rows} == {"standard"}


def test_run_comparative_unknown_pattern() -> None:
    cases = [ComparativeCase(case_id="c1", pattern="does_not_exist", trace={}, modes=("standard",))]
    reports = run_comparative(cases, llm_client_factory=_stub)
    assert reports[0].rows == []


def test_comparative_table_flattens() -> None:
    cases = [
        ComparativeCase(
            case_id="c1",
            pattern="lewin",
            trace={"task": "x", "steps": [], "outcome": "z", "success": False},
            modes=("quick", "standard"),
        )
    ]
    reports = run_comparative(cases, llm_client_factory=_stub)
    rows = comparative_table(reports)
    assert {row["mode"] for row in rows} == {"quick", "standard"}


def test_comparative_report_agreement() -> None:
    cases = [
        ComparativeCase(
            case_id="c1",
            pattern="lewin",
            trace={"task": "x", "steps": [], "outcome": "z", "success": False},
            modes=("quick", "standard"),
        )
    ]
    reports = run_comparative(cases, llm_client_factory=_stub)
    agree = reports[0].agreement()
    assert "fully_consistent" in agree
    assert "modes_run" in agree


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def test_cli_list(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "canonical" in out
    assert "lewin/pluto-stale-rag" in out


def test_cli_run_with_stub_emits_summary(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    rc = cli_main(["run", "canonical", "--out", str(tmp_path / "run"), "--stub"])
    # rc is 1 because stub-mode cases fail/err -- still a successful invocation.
    assert rc in (0, 1)
    out = capsys.readouterr().out
    # CLI prints the pretty-printed JSON summary followed by an
    # optional "\nFull report written to: ..." trailer. Slice out the
    # JSON block before any trailer.
    json_block = out.split("\nFull report", 1)[0].strip()
    summary = json.loads(json_block)
    assert summary["suite"] == "canonical"
    assert summary["total"] == 3


def test_cli_compare_table(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["compare", "canonical", "--mode", "quick", "--stub"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "case_id" in out
    assert "lewin/pluto-stale-rag" in out


def test_cli_compare_json(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["compare", "canonical", "--mode", "quick", "--stub", "--json"])
    assert rc == 0
    body = json.loads(capsys.readouterr().out)
    assert "table" in body
    assert "agreements" in body


def test_cli_run_missing_suite_returns_2(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli_main(["run", "does/not/exist.json"])
    assert rc == 2


def test_module_exports() -> None:
    assert "BenchmarkSuite" in benchmarks.__all__
    assert "canonical_suite" in benchmarks.__all__
    assert "run_comparative" in benchmarks.__all__
