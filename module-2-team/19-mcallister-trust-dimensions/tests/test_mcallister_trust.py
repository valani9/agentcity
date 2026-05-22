"""Tests for the McAllister Cognitive/Affective Trust diagnostic."""

from __future__ import annotations

import json

import pytest

from agentcity.mcallister_trust import (
    TRUST_DIMENSIONS,
    ConversationTurn,
    TrustBalanceDetection,
    TrustBalanceDetector,
    TrustConversationTrace,
    TrustDimensionEvidence,
    TrustIntervention,
)


def _turn(content: str, role: str = "user") -> ConversationTurn:
    return ConversationTurn(role=role, content=content)  # type: ignore[arg-type]


def _trace(**overrides: object) -> TrustConversationTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        model_name="test-model",
        task="default task",
        turns=[_turn("hello", "user"), _turn("hi", "agent")],
        outcome="default outcome",
        success=True,
    )
    base.update(overrides)
    return TrustConversationTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _dim(
    dimension: str,
    score: float = 0.7,
    gap: str = "low",
) -> dict[str, object]:
    return {
        "dimension": dimension,
        "score": score,
        "severity_of_gap": gap,
        "explanation": "test",
        "evidence_quotes": [],
    }


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = TrustConversationTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = TrustBalanceDetection(
            agent_id="t",
            dominant_dimension="cognitive",
            dimension_scores={"cognitive": 0.85, "affective": 0.1},
            dimensions=[
                TrustDimensionEvidence(
                    dimension="cognitive",
                    score=0.85,
                    severity_of_gap="low",
                    explanation="competent response",
                    evidence_quotes=["Agent: 'Refund submitted'"],
                )
            ],
            trust_balance=0.75,
            trust_quality="cognitive-only",
            interventions=[
                TrustIntervention(
                    target_dimension="affective",
                    intervention_type="acknowledge_stakes",
                    description="name the stakes",
                    suggested_implementation="prompt patch",
                    estimated_impact="high",
                    rationale="closes affective gap",
                )
            ],
            generator_model="test-model",
            success=True,
        )
        md = detection.to_markdown()
        assert "Trust-Dimensions Detection" in md
        assert "Dimension Scores" in md
        assert "Evidence by Dimension" in md
        assert "Recommended Interventions" in md
        assert "cognitive" in md
        assert "+0.75" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = TrustBalanceDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = TrustBalanceDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_empty_turns_rejected(self) -> None:
        det = TrustBalanceDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="turns"):
            det.run(_trace(turns=[]))


class TestDetectionPipeline:
    def test_cognitive_only(self) -> None:
        scores = json.dumps([_dim("cognitive", 0.85, "low"), _dim("affective", 0.1, "high")])
        interventions = json.dumps(
            [
                {
                    "target_dimension": "affective",
                    "intervention_type": "restate_user_emotion",
                    "description": "restate emotion",
                    "suggested_implementation": "prompt patch",
                    "estimated_impact": "high",
                    "rationale": "closes gap",
                }
            ]
        )
        stub = _Stub([scores, interventions])
        det = TrustBalanceDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.trust_quality == "cognitive-only"
        assert detection.dominant_dimension == "cognitive"
        assert detection.trust_balance == pytest.approx(0.75)
        assert len(detection.dimensions) == 2
        assert len(detection.interventions) == 1

    def test_balanced_trust_skips_interventions(self) -> None:
        scores = json.dumps([_dim("cognitive", 0.8, "none"), _dim("affective", 0.8, "none")])
        stub = _Stub([scores, "[]"])
        det = TrustBalanceDetector(stub, model="test-model")
        detection = det.run(_trace())

        # Balanced => single LLM call only (interventions skipped)
        assert len(stub.calls) == 1
        assert detection.trust_quality == "balanced-trust"
        assert detection.dominant_dimension == "balanced"
        assert detection.interventions == []

    def test_warm_but_incompetent(self) -> None:
        scores = json.dumps([_dim("cognitive", 0.1, "high"), _dim("affective", 0.8, "none")])
        det = TrustBalanceDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace())
        assert detection.trust_quality == "warm-but-incompetent"
        assert detection.dominant_dimension == "affective"
        assert detection.trust_balance < 0

    def test_low_trust(self) -> None:
        scores = json.dumps([_dim("cognitive", 0.1, "high"), _dim("affective", 0.1, "high")])
        det = TrustBalanceDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace())
        assert detection.trust_quality == "low-trust"
        assert detection.dominant_dimension == "neither"

    def test_missing_dimensions_filled(self) -> None:
        scores = json.dumps([_dim("cognitive", 0.7, "low")])
        det = TrustBalanceDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace())
        present = {ev.dimension for ev in detection.dimensions}
        assert present == set(TRUST_DIMENSIONS)


class TestTrustQualityThresholds:
    @pytest.mark.parametrize(
        "cog,aff,expected",
        [
            (0.8, 0.8, "balanced-trust"),
            (0.8, 0.1, "cognitive-only"),
            (0.1, 0.8, "warm-but-incompetent"),
            (0.1, 0.1, "low-trust"),
            (0.4, 0.4, "cognitive-only"),  # mixed: stronger axis wins
        ],
    )
    def test_threshold(self, cog: float, aff: float, expected: str) -> None:
        det = TrustBalanceDetector(_Stub([]))
        assert det._trust_quality({"cognitive": cog, "affective": aff}) == expected
