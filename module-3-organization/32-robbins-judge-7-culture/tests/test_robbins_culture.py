"""Tests for the Robbins & Judge 7-Characteristics Culture Diagnostic."""

from __future__ import annotations

import json

import pytest

from vstack.robbins_culture import (
    CULTURE_CHARACTERISTICS,
    AgentCultureTrace,
    CharacteristicScore,
    CultureIntervention,
    CultureProfileDetection,
    CultureProfileDetector,
)


def _trace(**overrides: object) -> AgentCultureTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        task="default task",
        task_class="research_exploration",
        system_prompt="Some prompt.",
        observed_behaviors=["did the thing"],
        outcome="default outcome",
        success=True,
    )
    base.update(overrides)
    return AgentCultureTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _char(
    name: str, observed: float = 0.5, target: float = 0.5, fit: float = 1.0
) -> dict[str, object]:
    return {
        "characteristic": name,
        "observed_score": observed,
        "target_score": target,
        "fit_score": fit,
        "explanation": f"{name} explanation",
        "evidence_quotes": [],
    }


def _payload(
    quality: str = "partial-fit",
    overall_fit: float = 0.65,
    gap: str = "innovation",
) -> str:
    return json.dumps(
        {
            "characteristics": [
                _char("innovation", 0.1, 0.85, 0.25),
                _char("attention_to_detail", 0.95, 0.5, 0.55),
                _char("outcome", 0.3, 0.4, 0.9),
                _char("people", 0.4, 0.5, 0.9),
                _char("team", 0.3, 0.4, 0.9),
                _char("aggressiveness", 0.1, 0.3, 0.8),
                _char("stability", 0.95, 0.2, 0.25),
            ],
            "overall_fit": overall_fit,
            "fit_quality": quality,
            "biggest_gap": gap,
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentCultureTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = CultureProfileDetection(
            agent_id="t",
            task_class="research_exploration",
            characteristics=[
                CharacteristicScore(
                    characteristic=c,  # type: ignore[arg-type]
                    observed_score=0.5,
                    target_score=0.5,
                    fit_score=1.0,
                    explanation=f"{c} explanation",
                )
                for c in CULTURE_CHARACTERISTICS
            ],
            overall_fit=0.5,
            fit_quality="partial-fit",
            biggest_gap="innovation",
            interventions=[
                CultureIntervention(
                    target_characteristic="innovation",
                    direction="increase",
                    intervention_type="rewrite_system_prompt",
                    description="rewrite prompt",
                    suggested_implementation="new prompt",
                    estimated_impact="high",
                    rationale="closes gap",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "7-Characteristics Culture Profile" in md
        assert "PARTIAL-FIT" in md
        assert "research_exploration" in md
        assert "innovation" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = CultureProfileDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = CultureProfileDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_no_prompt_or_behaviors_rejected(self) -> None:
        det = CultureProfileDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="system_prompt"):
            det.run(_trace(system_prompt="", observed_behaviors=[]))


class TestDetectionPipeline:
    def test_partial_fit_with_gap(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_characteristic": "innovation",
                    "direction": "increase",
                    "intervention_type": "rewrite_system_prompt",
                    "description": "rewrite",
                    "suggested_implementation": "patch",
                    "estimated_impact": "high",
                    "rationale": "closes gap",
                }
            ]
        )
        stub = _Stub([_payload(), interventions])
        det = CultureProfileDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.fit_quality == "partial-fit"
        assert detection.biggest_gap == "innovation"
        assert len(detection.characteristics) == 7
        assert len(detection.interventions) == 1

    def test_well_fit_skips_interventions(self) -> None:
        payload = _payload(quality="well-fit", overall_fit=0.9, gap="none")
        stub = _Stub([payload])
        det = CultureProfileDetector(stub, model="test-model")
        detection = det.run(_trace())
        # well-fit => single call only
        assert len(stub.calls) == 1
        assert detection.fit_quality == "well-fit"
        assert detection.biggest_gap == "none"
        assert detection.interventions == []

    def test_missing_characteristics_filled(self) -> None:
        partial = json.dumps(
            {
                "characteristics": [_char("innovation", 0.1, 0.85, 0.25)],
                "overall_fit": 0.6,
                "fit_quality": "partial-fit",
                "biggest_gap": "innovation",
            }
        )
        det = CultureProfileDetector(_Stub([partial, "[]"]))
        detection = det.run(_trace())
        present = {c.characteristic for c in detection.characteristics}
        assert present == set(CULTURE_CHARACTERISTICS)

    def test_garbage_gap_falls_back_to_largest(self) -> None:
        # LLM returns garbage gap; generator picks largest observed-vs-target delta
        bad = json.dumps(
            {
                "characteristics": [
                    _char("innovation", 0.1, 0.85, 0.25),  # |delta| = 0.75
                    _char("attention_to_detail", 0.95, 0.5, 0.55),  # |delta| = 0.45
                    _char("outcome", 0.5, 0.5, 1.0),
                    _char("people", 0.5, 0.5, 1.0),
                    _char("team", 0.5, 0.5, 1.0),
                    _char("aggressiveness", 0.5, 0.5, 1.0),
                    _char("stability", 0.5, 0.5, 1.0),
                ],
                "overall_fit": 0.65,
                "fit_quality": "partial-fit",
                "biggest_gap": "garbage_value",
            }
        )
        det = CultureProfileDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        # |obs-target| largest for innovation
        assert detection.biggest_gap == "innovation"


class TestFitQualityThresholds:
    @pytest.mark.parametrize(
        "overall_fit,expected",
        [
            (0.9, "well-fit"),
            (0.8, "well-fit"),
            (0.79, "partial-fit"),
            (0.5, "partial-fit"),
            (0.49, "misfit"),
            (0.0, "misfit"),
        ],
    )
    def test_threshold(self, overall_fit: float, expected: str) -> None:
        det = CultureProfileDetector(_Stub([]))
        assert det._fit_quality(overall_fit, "") == expected
