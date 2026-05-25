"""Tests for the SDT Intrinsic Reward Shaping Diagnostic."""

from __future__ import annotations

import json

import pytest

from vstack.sdt_reward import (
    SDT_NEEDS,
    AgentSDTTrace,
    NeedScore,
    SDTDetection,
    SDTIntervention,
    SDTRewardDetector,
)


def _trace(**overrides: object) -> AgentSDTTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        task="default task",
        task_class="research_exploration",
        system_prompt="some prompt",
        extrinsic_signals=["threat: X"],
        observed_behaviors=["did the thing"],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return AgentSDTTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _need(name: str, score: float = 0.5) -> dict[str, object]:
    return {
        "need": name,
        "score": score,
        "explanation": f"{name} explanation",
        "evidence_quotes": [],
    }


def _payload(
    quality: str = "controlled",
    score: float = 0.3,
    undermined: str = "autonomy",
) -> str:
    return json.dumps(
        {
            "need_evidence": [
                _need("autonomy", 0.1),
                _need("competence", 0.5),
                _need("relatedness", 0.3),
            ],
            "intrinsic_motivation_score": score,
            "motivation_quality": quality,
            "most_undermined_need": undermined,
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentSDTTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = SDTDetection(
            agent_id="t",
            task_class="research_exploration",
            need_evidence=[
                NeedScore(
                    need=n,  # type: ignore[arg-type]
                    score=0.5,
                    explanation=f"{n} explanation",
                )
                for n in SDT_NEEDS
            ],
            intrinsic_motivation_score=0.5,
            motivation_quality="mixed",
            most_undermined_need="autonomy",
            interventions=[
                SDTIntervention(
                    target_need="autonomy",
                    intervention_type="remove_external_reward_threat",
                    description="strip threat",
                    suggested_implementation="rewrite",
                    estimated_impact="high",
                    rationale="restores autonomy",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "SDT Intrinsic Reward Diagnostic" in md
        assert "MIXED" in md
        assert "autonomy" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = SDTRewardDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = SDTRewardDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_no_inputs_rejected(self) -> None:
        det = SDTRewardDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="system_prompt"):
            det.run(_trace(system_prompt="", extrinsic_signals=[], observed_behaviors=[]))


class TestDetectionPipeline:
    def test_controlled_with_undermined(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_need": "autonomy",
                    "intervention_type": "remove_external_reward_threat",
                    "description": "strip",
                    "suggested_implementation": "rewrite",
                    "estimated_impact": "high",
                    "rationale": "restores",
                }
            ]
        )
        stub = _Stub([_payload(), interventions])
        det = SDTRewardDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.motivation_quality == "controlled"
        assert detection.most_undermined_need == "autonomy"
        assert len(detection.need_evidence) == 3
        assert len(detection.interventions) == 1

    def test_intrinsic_skips_interventions(self) -> None:
        payload = _payload(quality="intrinsic", score=0.85, undermined="none")
        stub = _Stub([payload])
        det = SDTRewardDetector(stub, model="test-model")
        detection = det.run(_trace())
        assert len(stub.calls) == 1
        assert detection.motivation_quality == "intrinsic"
        assert detection.most_undermined_need == "none"
        assert detection.interventions == []

    def test_missing_needs_filled(self) -> None:
        partial = json.dumps(
            {
                "need_evidence": [_need("autonomy", 0.1)],
                "intrinsic_motivation_score": 0.4,
                "motivation_quality": "mixed",
                "most_undermined_need": "autonomy",
            }
        )
        det = SDTRewardDetector(_Stub([partial, "[]"]))
        detection = det.run(_trace())
        present = {ev.need for ev in detection.need_evidence}
        assert present == set(SDT_NEEDS)

    def test_garbage_undermined_falls_back_to_lowest(self) -> None:
        bad = json.dumps(
            {
                "need_evidence": [
                    _need("autonomy", 0.1),  # lowest
                    _need("competence", 0.5),
                    _need("relatedness", 0.6),
                ],
                "intrinsic_motivation_score": 0.4,
                "motivation_quality": "mixed",
                "most_undermined_need": "totally-fake",
            }
        )
        det = SDTRewardDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        assert detection.most_undermined_need == "autonomy"

    def test_garbage_undermined_all_high_falls_back_to_none(self) -> None:
        bad = json.dumps(
            {
                "need_evidence": [
                    _need("autonomy", 0.8),
                    _need("competence", 0.85),
                    _need("relatedness", 0.75),
                ],
                "intrinsic_motivation_score": 0.8,
                "motivation_quality": "intrinsic",
                "most_undermined_need": "totally-fake",
            }
        )
        det = SDTRewardDetector(_Stub([bad]))
        detection = det.run(_trace())
        assert detection.most_undermined_need == "none"


class TestQualityThresholds:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.9, "intrinsic"),
            (0.7, "intrinsic"),
            (0.69, "mixed"),
            (0.4, "mixed"),
            (0.39, "controlled"),
            (0.0, "controlled"),
        ],
    )
    def test_threshold(self, score: float, expected: str) -> None:
        det = SDTRewardDetector(_Stub([]))
        assert det._motivation_quality(score, "") == expected
