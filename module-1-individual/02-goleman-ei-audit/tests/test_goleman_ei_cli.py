"""CLI smoke tests for the Goleman EI Audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vstack.goleman_ei.cli import main as cli_main


def _write_trace(tmp_path: Path) -> Path:
    path = tmp_path / "trace.json"
    payload = {
        "agent_id": "t",
        "model_name": "m",
        "task": "Handle frustrated user.",
        "interaction_class": "customer_support",
        "system_prompt": "",
        "observed_behaviors": ["Long technical response."],
        "user_signals": ["User typed in caps."],
        "self_reports": [],
        "outcome": "User escalated.",
        "success": False,
    }
    path.write_text(json.dumps(payload))
    return path


def _write_stub(tmp_path: Path) -> Path:
    domains = json.dumps(
        {
            "domains": [
                {
                    "domain": "self_awareness",
                    "score": 0.85,
                    "explanation": "x",
                    "evidence_quotes": [],
                },
                {
                    "domain": "self_management",
                    "score": 0.8,
                    "explanation": "x",
                    "evidence_quotes": [],
                },
                {
                    "domain": "social_awareness",
                    "score": 0.1,
                    "explanation": "x",
                    "evidence_quotes": [],
                },
                {
                    "domain": "relationship_management",
                    "score": 0.15,
                    "explanation": "x",
                    "evidence_quotes": [],
                },
            ],
            "overall_ei": 0.475,
            "ei_quality": "developing",
            "weakest_domain": "social_awareness",
        }
    )
    interventions = json.dumps(
        [
            {
                "target_domain": "social_awareness",
                "intervention_type": "add_emotion_reading_step",
                "description": "Add emotion reading.",
                "suggested_implementation": "Append to prompt.",
                "estimated_impact": "high",
            }
        ]
    )
    path = tmp_path / "stub.json"
    path.write_text(json.dumps([domains, interventions]))
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
        assert "EI Audit" in captured.out
        assert "social_awareness" in captured.out

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
        assert obj["weakest_domain"] == "social_awareness"
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

    def test_detection_schema(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["schema", "--target", "detection"])
        captured = capsys.readouterr()
        assert rc == 0
        schema = json.loads(captured.out)
        assert "weakest_domain" in schema["properties"]


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
        assert len(payload) >= 15


class TestCompose:
    def test_outputs_manifest(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cli_main(["compose"])
        captured = capsys.readouterr()
        assert rc == 0
        obj = json.loads(captured.out)
        assert "downstream_by_domain" in obj


class TestReplay:
    def test_renders(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        det_path = tmp_path / "det.json"
        det_path.write_text(
            json.dumps(
                {
                    "domains": [
                        {
                            "domain": "social_awareness",
                            "score": 0.1,
                            "severity": "critical",
                            "explanation": "x",
                            "evidence_quotes": [],
                        }
                    ],
                    "overall_ei": 0.3,
                    "ei_quality": "low-ei",
                    "weakest_domain": "social_awareness",
                    "interventions": [],
                }
            )
        )
        rc = cli_main(["replay", "--detection", str(det_path)])
        captured = capsys.readouterr()
        assert rc == 0
        assert "EI Audit" in captured.out
