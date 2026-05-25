"""CLI smoke tests for the Lewin diagnostic.

Tests verify each subcommand returns exit 0 on a canned trace + canned
LLM responses, and that the output contains the expected structural
markers (dominant locus name, mode label, etc.).

The CLI is invoked via :func:`vstack.lewin.cli.main` directly (not
via subprocess) so the tests don't depend on entry-point registration
being live in the current venv.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vstack.lewin.cli import main as cli_main


def _write_trace(tmp_path: Path, name: str = "trace.json") -> Path:
    path = tmp_path / name
    payload = {
        "agent_id": "t",
        "model_name": "m",
        "task": "Refactor auth.",
        "steps": [
            {"type": "input", "content": "Refactor auth to JWTs"},
            {"type": "tool_call", "content": "created helpers"},
            {"type": "error", "content": "tests red"},
        ],
        "outcome": "Tests red.",
        "success": False,
    }
    path.write_text(json.dumps(payload))
    return path


def _write_stub_responses(tmp_path: Path, name: str = "stub.json") -> Path:
    """Write canned LLM responses for the stub client."""
    loci = json.dumps(
        [
            {
                "locus": "internal",
                "score": 0.2,
                "severity": "low",
                "confidence": 0.5,
                "explanation": "ok",
                "evidence_quotes": [],
                "factor_citations": [],
            },
            {
                "locus": "environmental",
                "score": 0.85,
                "severity": "high",
                "confidence": 0.85,
                "explanation": "prompt gap",
                "evidence_quotes": [],
                "factor_citations": [],
            },
            {
                "locus": "interactional",
                "score": 0.3,
                "severity": "low",
                "confidence": 0.5,
                "explanation": "minor",
                "evidence_quotes": [],
                "factor_citations": [],
            },
        ]
    )
    interventions = json.dumps(
        [
            {
                "target_locus": "environmental",
                "intervention_type": "change_prompt",
                "description": "add criteria",
                "suggested_implementation": "append",
                "estimated_impact": "high",
                "effort_estimate": "1h",
                "risk": "low",
                "reversibility": "two-way-door",
                "rationale": "closes gap",
            }
        ]
    )
    path = tmp_path / name
    path.write_text(json.dumps([loci, interventions]))
    return path


class TestAnalyze:
    def test_analyze_stub_markdown(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        trace = _write_trace(tmp_path)
        stub = _write_stub_responses(tmp_path)
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
        assert "Lewin Diagnostic" in captured.out
        assert "environmental" in captured.out

    def test_analyze_stub_json(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        trace = _write_trace(tmp_path)
        stub = _write_stub_responses(tmp_path)
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
                "json",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 0
        obj = json.loads(captured.out)
        assert obj["dominant_locus"] == "environmental"
        assert obj["mode"] == "standard"
        assert "composition_handoff" in obj

    def test_analyze_writes_to_file(self, tmp_path: Path) -> None:
        trace = _write_trace(tmp_path)
        stub = _write_stub_responses(tmp_path)
        out = tmp_path / "out.json"
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
                "--out",
                str(out),
            ]
        )
        assert rc == 0
        assert out.exists()
        obj = json.loads(out.read_text())
        assert obj["dominant_locus"] == "environmental"


class TestValidate:
    def test_validate_ok(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        trace = _write_trace(tmp_path)
        rc = cli_main(["validate", "--trace", str(trace)])
        captured = capsys.readouterr()
        assert rc == 0
        assert "OK" in captured.out


class TestSchema:
    def test_schema_trace_emits_jsonschema(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["schema", "--target", "trace"])
        captured = capsys.readouterr()
        assert rc == 0
        schema = json.loads(captured.out)
        assert "properties" in schema
        assert "task" in schema["properties"]

    def test_schema_detection_emits_jsonschema(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["schema", "--target", "detection"])
        captured = capsys.readouterr()
        assert rc == 0
        schema = json.loads(captured.out)
        assert "dominant_locus" in schema["properties"]


class TestReplay:
    def test_replay_renders_markdown(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        det_path = tmp_path / "det.json"
        det_path.write_text(
            json.dumps(
                {
                    "dominant_locus": "environmental",
                    "locus_scores": {
                        "internal": 0.2,
                        "environmental": 0.85,
                        "interactional": 0.3,
                    },
                    "loci": [
                        {
                            "locus": "environmental",
                            "score": 0.85,
                            "severity": "high",
                            "explanation": "p",
                            "evidence_quotes": [],
                        }
                    ],
                    "interventions": [],
                    "attribution_quality": "well-attributed",
                    "success": False,
                }
            )
        )
        rc = cli_main(["replay", "--detection", str(det_path)])
        captured = capsys.readouterr()
        assert rc == 0
        assert "Lewin Diagnostic" in captured.out


class TestPlaybooks:
    def test_playbooks_markdown(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["playbooks", "--format", "markdown"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "Lewin Failure-Mode Playbooks" in captured.out
        assert "rag_context" in captured.out

    def test_playbooks_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["playbooks", "--format", "json"])
        captured = capsys.readouterr()
        assert rc == 0
        payload = json.loads(captured.out)
        assert isinstance(payload, list)
        assert payload, "expected non-empty playbooks list"
        first = payload[0]
        assert "title" in first and "steps" in first


class TestCompose:
    def test_compose_outputs_manifest(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["compose"])
        captured = capsys.readouterr()
        assert rc == 0
        obj = json.loads(captured.out)
        assert "downstream_by_locus" in obj
        assert "framework_overlays" in obj
