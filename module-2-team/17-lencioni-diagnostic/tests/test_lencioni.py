"""Tests for the Lencioni Diagnostic.

Covers:
  - Schema construction and JSON round-trip
  - Markdown renderer structure
  - Validation rejects single-agent traces, empty goals, empty messages
  - End-to-end diagnostic pipeline with the stub client
  - Pyramid-order tie-break in dominant-dysfunction selection
  - Health-label thresholds
  - Pyramid-completeness (missing dysfunctions filled with zero-severity)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_PATTERN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PATTERN_ROOT))

from vstack.lencioni.generator import LencioniDiagnostic  # noqa: E402
from vstack.lencioni.schema import (  # noqa: E402
    DYSFUNCTIONS,
    AgentMessage,
    DysfunctionEvidence,
    Intervention,
    LencioniDiagnosis,
    MultiAgentTrace,
)


def _msg(i: int, frm: str, content: str, mt: str = "task") -> AgentMessage:
    return AgentMessage(
        timestamp=datetime(2026, 5, 22, 14, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=i * 5),
        from_agent=frm,
        to_agent=None,
        content=content,
        message_type=mt,  # type: ignore[arg-type]
    )


def _trace(**overrides: object) -> MultiAgentTrace:
    base: dict[str, object] = dict(
        team_id="test-team",
        goal="default goal",
        agents=["a", "b"],
        messages=[_msg(0, "a", "hello")],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return MultiAgentTrace(**base)  # type: ignore[arg-type]


class _Stub:
    """Local stub LLM client. Returns canned responses for each pass."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


class TestSchemaRoundtrip:
    def test_multi_agent_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = MultiAgentTrace.model_validate_json(trace.model_dump_json())
        assert restored.goal == trace.goal
        assert restored.agents == trace.agents
        assert len(restored.messages) == 1

    def test_diagnosis_markdown_has_all_sections(self) -> None:
        diagnosis = LencioniDiagnosis(
            team_id="test",
            dominant_dysfunction="fear-of-conflict",
            pyramid_score={d: 0.5 for d in DYSFUNCTIONS},
            dysfunctions=[
                DysfunctionEvidence(
                    dysfunction="fear-of-conflict",
                    severity="high",
                    score=0.9,
                    explanation="example",
                    evidence_quotes=["agent X agreed without challenge"],
                )
            ],
            interventions=[
                Intervention(
                    target_dysfunction="fear-of-conflict",
                    intervention_type="role_assignment",
                    description="Assign a devil's advocate",
                    suggested_implementation="Edit critic system prompt",
                    estimated_impact="high",
                    rationale="forces conflict",
                )
            ],
            overall_team_health="dysfunctional",
            generator_model="test-model",
            success=False,
        )
        md = diagnosis.to_markdown()
        assert "Lencioni Five Dysfunctions Diagnostic" in md
        assert "Pyramid Score" in md
        assert "Evidence by Dysfunction" in md
        assert "Recommended Interventions" in md
        assert "fear-of-conflict" in md


class TestValidation:
    def test_single_agent_trace_rejected(self) -> None:
        diag = LencioniDiagnostic(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="at least 2 agents"):
            diag.run(_trace(agents=["solo-agent"]))

    def test_empty_goal_rejected(self) -> None:
        diag = LencioniDiagnostic(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="goal"):
            diag.run(_trace(goal=""))

    def test_empty_outcome_rejected(self) -> None:
        diag = LencioniDiagnostic(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            diag.run(_trace(outcome=""))

    def test_no_messages_rejected(self) -> None:
        diag = LencioniDiagnostic(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="messages"):
            diag.run(_trace(messages=[]))


class TestDiagnosticPipeline:
    def test_end_to_end_with_canned_responses(self) -> None:
        scores = json.dumps(
            [
                {
                    "dysfunction": "fear-of-conflict",
                    "severity": "high",
                    "score": 0.9,
                    "explanation": "team converged on first proposal in 30s",
                    "evidence_quotes": ["agent agreed without challenge"],
                }
            ]
        )
        interventions = json.dumps(
            [
                {
                    "target_dysfunction": "fear-of-conflict",
                    "intervention_type": "role_assignment",
                    "description": "devil's advocate role",
                    "suggested_implementation": "edit critic prompt",
                    "estimated_impact": "high",
                    "rationale": "forces structural conflict",
                }
            ]
        )
        stub = _Stub([scores, interventions])
        diag = LencioniDiagnostic(stub, model="test-model")
        diagnosis = diag.run(_trace())

        assert len(stub.calls) == 2
        assert diagnosis.dominant_dysfunction == "fear-of-conflict"
        assert diagnosis.overall_team_health == "dysfunctional"
        assert diagnosis.pyramid_score["fear-of-conflict"] == 0.9
        assert len(diagnosis.dysfunctions) == 5
        assert len(diagnosis.interventions) == 1

    def test_missing_dysfunctions_filled_with_zero(self) -> None:
        scores = json.dumps(
            [
                {
                    "dysfunction": "fear-of-conflict",
                    "severity": "high",
                    "score": 0.9,
                    "explanation": "only one dysfunction reported",
                    "evidence_quotes": [],
                }
            ]
        )
        stub = _Stub([scores, "[]"])
        diag = LencioniDiagnostic(stub)
        diagnosis = diag.run(_trace())
        present = {ev.dysfunction for ev in diagnosis.dysfunctions}
        assert present == set(DYSFUNCTIONS)
        for d in DYSFUNCTIONS:
            if d == "fear-of-conflict":
                continue
            ev = next(ev for ev in diagnosis.dysfunctions if ev.dysfunction == d)
            assert ev.score == 0.0
            assert ev.severity == "none"

    def test_pyramid_tie_break_favors_foundation(self) -> None:
        """When two dysfunctions are tied (within 0.05), the lower
        dysfunction in the pyramid wins, per Lencioni's model."""
        scores = json.dumps(
            [
                {
                    "dysfunction": "absence-of-trust",
                    "severity": "high",
                    "score": 0.8,
                    "explanation": "tied with fear-of-conflict",
                    "evidence_quotes": [],
                },
                {
                    "dysfunction": "fear-of-conflict",
                    "severity": "high",
                    "score": 0.8,
                    "explanation": "tied with absence-of-trust",
                    "evidence_quotes": [],
                },
            ]
        )
        diag = LencioniDiagnostic(_Stub([scores, "[]"]))
        diagnosis = diag.run(_trace())
        # absence-of-trust is lower in the pyramid, so it should win the tie.
        assert diagnosis.dominant_dysfunction == "absence-of-trust"

    def test_no_dysfunction_observed_when_scores_low(self) -> None:
        scores = json.dumps(
            [
                {
                    "dysfunction": d,
                    "severity": "none",
                    "score": 0.05,
                    "explanation": "no evidence",
                    "evidence_quotes": [],
                }
                for d in DYSFUNCTIONS
            ]
        )
        diag = LencioniDiagnostic(_Stub([scores, "[]"]))
        diagnosis = diag.run(_trace(success=True, outcome="Team did fine."))
        assert diagnosis.dominant_dysfunction == "none-observed"
        assert diagnosis.overall_team_health == "healthy"
        # Interventions empty when no dysfunction observed.
        assert diagnosis.interventions == []


class TestHealthLabels:
    @pytest.mark.parametrize(
        "max_score,expected",
        [
            (0.1, "healthy"),
            (0.3, "healthy"),
            (0.31, "stressed"),
            (0.6, "stressed"),
            (0.61, "dysfunctional"),
            (0.9, "dysfunctional"),
        ],
    )
    def test_health_threshold(self, max_score: float, expected: str) -> None:
        diag = LencioniDiagnostic(_Stub([]))
        scores = {d: 0.0 for d in DYSFUNCTIONS}
        scores["fear-of-conflict"] = max_score
        assert diag._team_health(scores) == expected
