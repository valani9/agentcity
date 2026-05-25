"""Tests for the Johari Window Self-Audit.

Covers:
  - Schema construction and JSON round-trip
  - Markdown renderer structure
  - Validation rejects empty task / outcome / turns / self-report
  - End-to-end audit pipeline with the stub client
  - Tie-break in dominant-quadrant selection (BLIND wins ties)
  - Self-awareness score thresholds
  - Quadrants missing from LLM output filled with zero weight
  - No interventions when dominant is OPEN
"""

from __future__ import annotations

import json

import pytest

from vstack.johari import (
    QUADRANTS,
    AgentSelfReportTrace,
    InteractionTurn,
    JohariIntervention,
    JohariSelfAudit,
    JohariSelfAuditor,
    QuadrantContent,
)


def _turn(role: str, content: str) -> InteractionTurn:
    return InteractionTurn(role=role, content=content)  # type: ignore[arg-type]


def _trace(**overrides: object) -> AgentSelfReportTrace:
    base: dict[str, object] = dict(
        agent_id="test-agent",
        model_name="test-model",
        task="default task",
        turns=[_turn("user", "hi"), _turn("agent", "hello")],
        self_report="I said hello.",
        outcome="default outcome",
        success=True,
    )
    base.update(overrides)
    return AgentSelfReportTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentSelfReportTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task
        assert restored.self_report == trace.self_report

    def test_markdown_has_all_sections(self) -> None:
        audit = JohariSelfAudit(
            agent_id="t",
            model_name="m",
            dominant_quadrant="blind",
            quadrant_weights={q: 0.25 for q in QUADRANTS},
            quadrants=[
                QuadrantContent(
                    quadrant="blind",
                    weight=0.6,
                    explanation="agent claimed X, trace shows Y",
                    evidence_quotes=["self-report: claimed 4 results; trace: 2"],
                )
            ],
            self_awareness_score=0.4,
            blind_spot_register=["claimed 4 results when 2 returned"],
            hidden_content_register=[],
            interventions=[
                JohariIntervention(
                    target_quadrant="blind",
                    intervention_type="self_consistency_check",
                    description="cross-check self-report against trace",
                    suggested_implementation="add a final pass to compare claims to tool returns",
                    estimated_impact="high",
                    rationale="directly addresses BLIND",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = audit.to_markdown()
        assert "Johari Window Self-Audit" in md
        assert "Quadrant Weights" in md
        assert "Per-Quadrant Findings" in md
        assert "Blind Spots" in md
        assert "Recommended Interventions" in md
        assert "self_consistency_check" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        auditor = JohariSelfAuditor(_Stub(["{}", "[]"]))
        with pytest.raises(ValueError, match="task"):
            auditor.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        auditor = JohariSelfAuditor(_Stub(["{}", "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            auditor.run(_trace(outcome=""))

    def test_empty_turns_rejected(self) -> None:
        auditor = JohariSelfAuditor(_Stub(["{}", "[]"]))
        with pytest.raises(ValueError, match="turns"):
            auditor.run(_trace(turns=[]))

    def test_empty_self_report_rejected(self) -> None:
        auditor = JohariSelfAuditor(_Stub(["{}", "[]"]))
        with pytest.raises(ValueError, match="self_report"):
            auditor.run(_trace(self_report=""))


class TestAuditPipeline:
    def test_end_to_end_with_canned_responses(self) -> None:
        analysis = json.dumps(
            {
                "quadrants": [
                    {
                        "quadrant": "open",
                        "weight": 0.2,
                        "explanation": "some matching content",
                        "evidence_quotes": [],
                    },
                    {
                        "quadrant": "blind",
                        "weight": 0.6,
                        "explanation": "agent claimed X, trace shows Y",
                        "evidence_quotes": ["divergence example"],
                    },
                    {
                        "quadrant": "hidden",
                        "weight": 0.15,
                        "explanation": "minor uncertainty withheld",
                        "evidence_quotes": [],
                    },
                    {
                        "quadrant": "unknown",
                        "weight": 0.05,
                        "explanation": "no obvious latent content",
                        "evidence_quotes": [],
                    },
                ],
                "blind_spot_register": ["claimed N results when M returned"],
                "hidden_content_register": ["did not surface confidence interval"],
            }
        )
        interventions = json.dumps(
            [
                {
                    "target_quadrant": "blind",
                    "intervention_type": "self_consistency_check",
                    "description": "force the agent to cross-check",
                    "suggested_implementation": "add a final review pass",
                    "estimated_impact": "high",
                    "rationale": "closes BLIND",
                }
            ]
        )
        stub = _Stub([analysis, interventions])
        auditor = JohariSelfAuditor(stub, model="test-model")
        audit = auditor.run(_trace(success=False))

        assert len(stub.calls) == 2
        assert audit.dominant_quadrant == "blind"
        assert audit.quadrant_weights["blind"] == 0.6
        assert len(audit.quadrants) == 4
        assert len(audit.interventions) == 1
        assert audit.blind_spot_register == ["claimed N results when M returned"]
        assert audit.hidden_content_register == ["did not surface confidence interval"]

    def test_missing_quadrants_filled_with_zero(self) -> None:
        analysis = json.dumps(
            {
                "quadrants": [
                    {
                        "quadrant": "blind",
                        "weight": 0.7,
                        "explanation": "single quadrant reported",
                        "evidence_quotes": [],
                    }
                ],
                "blind_spot_register": [],
                "hidden_content_register": [],
            }
        )
        auditor = JohariSelfAuditor(_Stub([analysis, "[]"]))
        audit = auditor.run(_trace())
        present = {qc.quadrant for qc in audit.quadrants}
        assert present == set(QUADRANTS)

    def test_dominant_open_yields_no_interventions(self) -> None:
        analysis = json.dumps(
            {
                "quadrants": [
                    {
                        "quadrant": "open",
                        "weight": 0.9,
                        "explanation": "healthy alignment",
                        "evidence_quotes": [],
                    },
                    {
                        "quadrant": "blind",
                        "weight": 0.05,
                        "explanation": "minor",
                        "evidence_quotes": [],
                    },
                    {
                        "quadrant": "hidden",
                        "weight": 0.05,
                        "explanation": "minor",
                        "evidence_quotes": [],
                    },
                    {
                        "quadrant": "unknown",
                        "weight": 0.0,
                        "explanation": "none",
                        "evidence_quotes": [],
                    },
                ],
                "blind_spot_register": [],
                "hidden_content_register": [],
            }
        )
        auditor = JohariSelfAuditor(_Stub([analysis, "[]"]))
        audit = auditor.run(_trace(success=True))
        assert audit.dominant_quadrant == "open"
        assert audit.interventions == []

    def test_blind_wins_tie_break(self) -> None:
        """BLIND is the diagnostically-most-urgent quadrant per the
        framework. When tied with HIDDEN within 0.05, BLIND should win.
        """
        analysis = json.dumps(
            {
                "quadrants": [
                    {
                        "quadrant": "hidden",
                        "weight": 0.4,
                        "explanation": "tied",
                        "evidence_quotes": [],
                    },
                    {
                        "quadrant": "blind",
                        "weight": 0.4,
                        "explanation": "tied",
                        "evidence_quotes": [],
                    },
                ],
                "blind_spot_register": [],
                "hidden_content_register": [],
            }
        )
        auditor = JohariSelfAuditor(_Stub([analysis, "[]"]))
        audit = auditor.run(_trace())
        assert audit.dominant_quadrant == "blind"


class TestSelfAwarenessScore:
    def test_high_open_yields_high_awareness(self) -> None:
        auditor = JohariSelfAuditor(_Stub([]))
        score = auditor._self_awareness_score(
            {"open": 0.9, "blind": 0.05, "hidden": 0.05, "unknown": 0.0}
        )
        assert score >= 0.85

    def test_high_blind_yields_low_awareness(self) -> None:
        auditor = JohariSelfAuditor(_Stub([]))
        score = auditor._self_awareness_score(
            {"open": 0.1, "blind": 0.8, "hidden": 0.05, "unknown": 0.05}
        )
        assert score <= 0.25

    def test_all_zero_returns_midpoint(self) -> None:
        auditor = JohariSelfAuditor(_Stub([]))
        score = auditor._self_awareness_score(
            {"open": 0.0, "blind": 0.0, "hidden": 0.0, "unknown": 0.0}
        )
        assert score == 0.5
