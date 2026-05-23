"""CLI smoke tests for the Johari self-audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentcity.johari.cli import main as cli_main


def _write_trace(tmp_path: Path) -> Path:
    path = tmp_path / "trace.json"
    payload = {
        "agent_id": "t",
        "model_name": "m",
        "task": "Research trials.",
        "turns": [
            {"role": "user", "content": "Find recent trials."},
            {"role": "tool", "content": "pubmed.search"},
            {"role": "agent", "content": "I searched 3 databases."},
        ],
        "self_report": "I searched 3 databases comprehensively.",
        "outcome": "User found discrepancy.",
        "success": False,
    }
    path.write_text(json.dumps(payload))
    return path


def _write_stub(tmp_path: Path) -> Path:
    quadrants = json.dumps(
        {
            "quadrants": [
                {"quadrant": "open", "weight": 0.3, "explanation": "x", "evidence_quotes": []},
                {"quadrant": "blind", "weight": 0.6, "explanation": "x", "evidence_quotes": []},
                {"quadrant": "hidden", "weight": 0.1, "explanation": "x", "evidence_quotes": []},
                {"quadrant": "unknown", "weight": 0.05, "explanation": "x", "evidence_quotes": []},
            ],
            "blind_spot_register": ["claimed 3 databases, searched 1"],
            "hidden_content_register": [],
        }
    )
    interventions = json.dumps(
        [
            {
                "target_quadrant": "blind",
                "intervention_type": "feedback_loop",
                "description": "Add user-feedback loop.",
                "suggested_implementation": "Ask user.",
                "estimated_impact": "high",
            }
        ]
    )
    path = tmp_path / "stub.json"
    path.write_text(json.dumps([quadrants, interventions]))
    return path


class TestAnalyze:
    def test_markdown(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        trace = _write_trace(tmp_path)
        stub = _write_stub(tmp_path)
        rc = cli_main(
            [
                "analyze",
                "--trace",
                str(trace),
                "--client",
                "stub",
                "--stub-responses",
                str(stub),
                "--mode",
                "standard",
                "--format",
                "markdown",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 0
        assert "Johari Window" in captured.out

    def test_json(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        trace = _write_trace(tmp_path)
        stub = _write_stub(tmp_path)
        rc = cli_main(
            [
                "analyze",
                "--trace",
                str(trace),
                "--client",
                "stub",
                "--stub-responses",
                str(stub),
                "--format",
                "json",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 0
        obj = json.loads(captured.out)
        assert obj["dominant_quadrant"] == "blind"
        assert obj["mode"] == "standard"


class TestValidate:
    def test_ok(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        trace = _write_trace(tmp_path)
        rc = cli_main(["validate", "--trace", str(trace)])
        captured = capsys.readouterr()
        assert rc == 0
        assert "OK" in captured.out


class TestSchema:
    def test_trace_schema(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["schema", "--target", "trace"])
        captured = capsys.readouterr()
        assert rc == 0
        schema = json.loads(captured.out)
        assert "properties" in schema

    def test_audit_schema(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["schema", "--target", "audit"])
        captured = capsys.readouterr()
        assert rc == 0
        schema = json.loads(captured.out)
        assert "dominant_quadrant" in schema["properties"]


class TestPlaybooks:
    def test_markdown(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["playbooks", "--format", "markdown"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "Failure-Mode Playbooks" in captured.out

    def test_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["playbooks", "--format", "json"])
        captured = capsys.readouterr()
        assert rc == 0
        payload = json.loads(captured.out)
        assert isinstance(payload, list)
        assert len(payload) == 12


class TestCompose:
    def test_outputs_manifest(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["compose"])
        captured = capsys.readouterr()
        assert rc == 0
        obj = json.loads(captured.out)
        assert "downstream_by_quadrant" in obj


class TestReplay:
    def test_renders(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        audit_path = tmp_path / "audit.json"
        audit_path.write_text(
            json.dumps(
                {
                    "dominant_quadrant": "blind",
                    "quadrant_weights": {
                        "open": 0.2,
                        "blind": 0.7,
                        "hidden": 0.05,
                        "unknown": 0.05,
                    },
                    "quadrants": [],
                    "self_awareness_score": 0.3,
                    "interventions": [],
                }
            )
        )
        rc = cli_main(["replay", "--audit", str(audit_path)])
        captured = capsys.readouterr()
        assert rc == 0
        assert "Johari Window" in captured.out
