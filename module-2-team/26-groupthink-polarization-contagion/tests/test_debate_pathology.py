"""Tests for the Groupthink/Polarization/Contagion Detector."""

from __future__ import annotations

import json

import pytest

from vstack.debate_pathology import (
    PATHOLOGIES,
    DebateIntervention,
    DebateMessage,
    DebatePathologyDetection,
    DebatePathologyDetector,
    MultiAgentDebateTrace,
    PathologyEvidence,
)


def _msg(
    from_agent: str,
    round: int = 1,
    content: str = "x",
    position: str = "",
) -> DebateMessage:
    return DebateMessage(  # type: ignore[arg-type]
        round=round,
        from_agent=from_agent,
        position=position,
        content=content,
    )


def _trace(**overrides: object) -> MultiAgentDebateTrace:
    base: dict[str, object] = dict(
        debate_id="test",
        task="default task",
        agents=["a", "b"],
        messages=[_msg("a"), _msg("b")],
        final_decision="default decision",
        outcome="default outcome",
        success=True,
    )
    base.update(overrides)
    return MultiAgentDebateTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _path(name: str, score: float = 0.7, sev: str = "high") -> dict[str, object]:
    return {
        "pathology": name,
        "score": score,
        "severity": sev,
        "explanation": "test",
        "evidence_quotes": [],
    }


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = MultiAgentDebateTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = DebatePathologyDetection(
            debate_id="t",
            dominant_pathology="groupthink",
            pathology_scores={p: 0.25 for p in PATHOLOGIES},
            pathologies=[
                PathologyEvidence(
                    pathology="groupthink",
                    score=0.9,
                    severity="high",
                    explanation="convergence by round 2",
                    evidence_quotes=["round 2 safety: 'never mind'"],
                )
            ],
            debate_quality="pathological",
            convergence_round=2,
            interventions=[
                DebateIntervention(
                    target_pathology="groupthink",
                    intervention_type="require_silent_vote",
                    description="silent vote",
                    suggested_implementation="parallel buffer",
                    estimated_impact="high",
                    rationale="counters conformity",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "Debate-Pathology Detection" in md
        assert "Pathology Scores" in md
        assert "Evidence by Pathology" in md
        assert "Recommended Interventions" in md
        assert "groupthink" in md
        assert "Convergence round: 2" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = DebatePathologyDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_decision_rejected(self) -> None:
        det = DebatePathologyDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="final_decision"):
            det.run(_trace(final_decision=""))

    def test_single_agent_rejected(self) -> None:
        det = DebatePathologyDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="at least 2 agents"):
            det.run(_trace(agents=["a"]))

    def test_single_message_rejected(self) -> None:
        det = DebatePathologyDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="at least 2 messages"):
            det.run(_trace(messages=[_msg("a")]))


class TestDetectionPipeline:
    def test_groupthink_dominant(self) -> None:
        scores = json.dumps(
            [
                _path("groupthink", 0.9, "high"),
                _path("polarization", 0.3, "low"),
                _path("contagion", 0.5, "medium"),
            ]
        )
        interventions = json.dumps(
            [
                {
                    "target_pathology": "groupthink",
                    "intervention_type": "require_silent_vote",
                    "description": "silent vote",
                    "suggested_implementation": "patch",
                    "estimated_impact": "high",
                    "rationale": "counters conformity",
                }
            ]
        )
        stub = _Stub([scores, interventions])
        det = DebatePathologyDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.dominant_pathology == "groupthink"
        assert detection.debate_quality == "pathological"
        assert detection.pathology_scores["groupthink"] == 0.9
        assert len(detection.pathologies) == 3
        assert len(detection.interventions) == 1

    def test_groupthink_wins_tiebreak(self) -> None:
        scores = json.dumps(
            [
                _path("groupthink", 0.7, "high"),
                _path("contagion", 0.7, "high"),
            ]
        )
        det = DebatePathologyDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace())
        assert detection.dominant_pathology == "groupthink"

    def test_none_observed_when_low(self) -> None:
        scores = json.dumps([_path(p, 0.05, "none") for p in PATHOLOGIES])
        det = DebatePathologyDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace(success=True))
        assert detection.dominant_pathology == "none-observed"
        assert detection.debate_quality == "healthy"
        assert detection.interventions == []

    def test_missing_pathologies_filled(self) -> None:
        scores = json.dumps([_path("groupthink", 0.8, "high")])
        det = DebatePathologyDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace())
        present = {ev.pathology for ev in detection.pathologies}
        assert present == set(PATHOLOGIES)


class TestConvergenceRound:
    def test_convergence_detected(self) -> None:
        det = DebatePathologyDetector(_Stub([]))
        trace = _trace(
            messages=[
                _msg("a", round=1, position="ship"),
                _msg("b", round=1, position="hold"),
                _msg("a", round=2, position="ship"),
                _msg("b", round=2, position="ship"),
            ]
        )
        assert det._convergence_round(trace) == 2

    def test_no_convergence(self) -> None:
        det = DebatePathologyDetector(_Stub([]))
        trace = _trace(
            messages=[
                _msg("a", round=1, position="ship"),
                _msg("b", round=1, position="hold"),
                _msg("a", round=2, position="ship"),
                _msg("b", round=2, position="hold"),
            ]
        )
        assert det._convergence_round(trace) is None

    def test_no_positions(self) -> None:
        det = DebatePathologyDetector(_Stub([]))
        # No position fields set
        trace = _trace()
        assert det._convergence_round(trace) is None


class TestDebateQualityThresholds:
    @pytest.mark.parametrize(
        "max_score,expected",
        [
            (0.1, "healthy"),
            (0.3, "healthy"),
            (0.31, "at-risk"),
            (0.6, "at-risk"),
            (0.61, "pathological"),
            (0.9, "pathological"),
        ],
    )
    def test_threshold(self, max_score: float, expected: str) -> None:
        det = DebatePathologyDetector(_Stub([]))
        scores = {p: 0.0 for p in PATHOLOGIES}
        scores["groupthink"] = max_score
        assert det._debate_quality(scores) == expected
