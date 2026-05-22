"""
Unit tests for the AAR Generator's command-line interface.

Verifies:
  - `agentcity --version` prints a version string
  - `agentcity aar` reads a trace from a file and produces markdown output
  - `agentcity aar` reads from stdin when --trace is - or omitted
  - The CLI rejects invalid client names cleanly (non-zero exit code)
  - JSON output mode is selectable via --format
"""

from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_PATTERN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PATTERN_ROOT))

from lib import cli  # noqa: E402


def _trace_dict() -> dict[str, object]:
    return {
        "goal": "Test the CLI",
        "outcome": "It works",
        "success": True,
        "steps": [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "message",
                "content": "hello",
            }
        ],
    }


class TestCLI:
    def test_version_subcommand_prints_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli.main(["version"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "agentcity" in captured.out
        # Version follows semver-ish pattern: starts with digit.
        version_tail = captured.out.strip().split()[-1]
        assert version_tail[0].isdigit()

    def test_aar_subcommand_reads_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(_trace_dict()))
        rc = cli.main(["aar", "--trace", str(trace_file), "--client", "stub"])
        captured = capsys.readouterr()
        assert rc == 0
        # Stub client returns empty Lessons / NextSteps but the AAR sections
        # are still rendered.
        assert "After-Action Review" in captured.out
        assert "## 1. Goal" in captured.out
        assert "## 2. Results" in captured.out

    def test_aar_subcommand_reads_stdin(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_trace_dict())))
        rc = cli.main(["aar", "--client", "stub"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "After-Action Review" in captured.out

    def test_aar_json_output_mode_returns_valid_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(_trace_dict()))
        rc = cli.main(
            [
                "aar",
                "--trace",
                str(trace_file),
                "--client",
                "stub",
                "--format",
                "json",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 0
        # Output should be parseable JSON.
        parsed = json.loads(captured.out)
        assert "goal" in parsed
        assert "results" in parsed
        assert "lessons" in parsed
        assert "next_steps" in parsed

    def test_aar_rejects_unknown_client(self) -> None:
        # argparse rejects choices via SystemExit; we use 'choices=' so it's
        # parser-level.
        with pytest.raises(SystemExit):
            cli.main(["aar", "--client", "not-a-real-client"])

    def test_aar_rejects_malformed_trace_file(self, tmp_path: Path) -> None:
        trace_file = tmp_path / "trace.json"
        trace_file.write_text("not valid json{{{")
        with pytest.raises(SystemExit):
            cli.main(["aar", "--trace", str(trace_file), "--client", "stub"])

    def test_aar_rejects_trace_with_empty_goal(self, tmp_path: Path) -> None:
        bad = _trace_dict()
        bad["goal"] = ""
        trace_file = tmp_path / "trace.json"
        trace_file.write_text(json.dumps(bad))
        # AgentTrace itself accepts empty goal in pydantic; the validator
        # is in the generator. CLI returns a non-zero exit code via the
        # ValueError propagating to main → SystemExit on the user side.
        # We catch the ValueError directly here.
        with pytest.raises((ValueError, SystemExit)):
            cli.main(["aar", "--trace", str(trace_file), "--client", "stub"])
