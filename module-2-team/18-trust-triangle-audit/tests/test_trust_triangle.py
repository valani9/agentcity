"""Tests for the Trust Triangle Audit.

Covers:
  - Schema construction and JSON round-trip
  - Markdown renderer structure
  - Validation rejects empty task / outcome / no turns
  - End-to-end audit pipeline with the stub client
  - Tie-break in dominant-wobble selection
  - Trust-level thresholds
  - Legs missing from LLM output are filled with zero wobble
"""

from __future__ import annotations

import json

import pytest

from agentcity.trust_triangle import (
    LEGS,
    AgentInteractionTrace,
    InteractionTurn,
    LegEvidence,
    TrustIntervention,
    TrustTriangleAudit,
    TrustTriangleAuditor,
)


def _turn(role: str, content: str) -> InteractionTurn:
    return InteractionTurn(role=role, content=content)  # type: ignore[arg-type]


def _trace(**overrides: object) -> AgentInteractionTrace:
    base: dict[str, object] = dict(
        agent_id="test-agent",
        model_name="test-model",
        task="default task",
        turns=[_turn("user", "hi"), _turn("agent", "hello")],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return AgentInteractionTrace(**base)  # type: ignore[arg-type]


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
        restored = AgentInteractionTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task
        assert len(restored.turns) == len(trace.turns)

    def test_markdown_has_all_sections(self) -> None:
        audit = TrustTriangleAudit(
            agent_id="t",
            model_name="m",
            dominant_wobble="empathy",
            leg_scores={leg: 0.3 for leg in LEGS},
            legs=[
                LegEvidence(
                    leg="empathy",
                    wobble_score=0.7,
                    severity="high",
                    explanation="generic responses",
                    evidence_quotes=["agent ignored user time pressure"],
                )
            ],
            interventions=[
                TrustIntervention(
                    target_leg="empathy",
                    intervention_type="prompt_patch",
                    description="acknowledge user context first",
                    suggested_implementation="prepend empathy step",
                    estimated_impact="high",
                    rationale="closes the dominant wobble",
                )
            ],
            overall_trust_level="low-trust",
            generator_model="test-model",
            success=False,
        )
        md = audit.to_markdown()
        assert "Trust Triangle Audit" in md
        assert "Leg Scores" in md
        assert "Evidence by Leg" in md
        assert "Recommended Interventions" in md
        assert "empathy" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        auditor = TrustTriangleAuditor(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="task"):
            auditor.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        auditor = TrustTriangleAuditor(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            auditor.run(_trace(outcome=""))

    def test_empty_turns_rejected(self) -> None:
        auditor = TrustTriangleAuditor(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="turns"):
            auditor.run(_trace(turns=[]))


class TestAuditPipeline:
    def test_end_to_end_with_canned_responses(self) -> None:
        scores = json.dumps(
            [
                {
                    "leg": "empathy",
                    "wobble_score": 0.85,
                    "severity": "high",
                    "explanation": "ignored user emotional state",
                    "evidence_quotes": ["agent missed time pressure"],
                }
            ]
        )
        interventions = json.dumps(
            [
                {
                    "target_leg": "empathy",
                    "intervention_type": "prompt_patch",
                    "description": "acknowledge user emotion first",
                    "suggested_implementation": "prepend empathy step in system prompt",
                    "estimated_impact": "high",
                    "rationale": "closes the dominant wobble",
                }
            ]
        )
        stub = _Stub([scores, interventions])
        auditor = TrustTriangleAuditor(stub, model="test-model")
        audit = auditor.run(_trace())

        assert len(stub.calls) == 2
        assert audit.dominant_wobble == "empathy"
        assert audit.overall_trust_level == "low-trust"
        assert audit.leg_scores["empathy"] == 0.85
        assert len(audit.legs) == 3
        assert len(audit.interventions) == 1

    def test_missing_legs_filled_with_zero(self) -> None:
        scores = json.dumps(
            [
                {
                    "leg": "logic",
                    "wobble_score": 0.7,
                    "severity": "high",
                    "explanation": "math error",
                    "evidence_quotes": [],
                }
            ]
        )
        stub = _Stub([scores, "[]"])
        auditor = TrustTriangleAuditor(stub)
        audit = auditor.run(_trace())
        present = {ev.leg for ev in audit.legs}
        assert present == set(LEGS)

    def test_dominant_tiebreak_favors_logic(self) -> None:
        scores = json.dumps(
            [
                {
                    "leg": "logic",
                    "wobble_score": 0.7,
                    "severity": "high",
                    "explanation": "tied",
                    "evidence_quotes": [],
                },
                {
                    "leg": "empathy",
                    "wobble_score": 0.7,
                    "severity": "high",
                    "explanation": "tied",
                    "evidence_quotes": [],
                },
            ]
        )
        auditor = TrustTriangleAuditor(_Stub([scores, "[]"]))
        audit = auditor.run(_trace())
        # Logic is first in LEGS, wins ties within 0.05.
        assert audit.dominant_wobble == "logic"

    def test_none_observed_when_all_solid(self) -> None:
        scores = json.dumps(
            [
                {
                    "leg": leg,
                    "wobble_score": 0.05,
                    "severity": "none",
                    "explanation": "solid",
                    "evidence_quotes": [],
                }
                for leg in LEGS
            ]
        )
        auditor = TrustTriangleAuditor(_Stub([scores, "[]"]))
        audit = auditor.run(_trace(success=True, outcome="user satisfied"))
        assert audit.dominant_wobble == "none-observed"
        assert audit.overall_trust_level == "high-trust"
        assert audit.interventions == []


class TestTrustLevels:
    @pytest.mark.parametrize(
        "max_score,expected",
        [
            (0.1, "high-trust"),
            (0.3, "high-trust"),
            (0.31, "moderate-trust"),
            (0.6, "moderate-trust"),
            (0.61, "low-trust"),
            (0.9, "low-trust"),
        ],
    )
    def test_trust_level_threshold(self, max_score: float, expected: str) -> None:
        auditor = TrustTriangleAuditor(_Stub([]))
        scores = {leg: 0.0 for leg in LEGS}
        scores["empathy"] = max_score
        assert auditor._trust_level(scores) == expected
