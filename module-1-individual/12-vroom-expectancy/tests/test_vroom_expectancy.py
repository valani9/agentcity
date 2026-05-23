"""Tests for the Vroom Expectancy Calculator."""

from __future__ import annotations

import json

import pytest

from agentcity.vroom_expectancy import (
    VROOM_TERMS,
    AgentExpectancyTrace,
    VroomDetection,
    VroomExpectancyCalculator,
    VroomIntervention,
    VroomTermScore,
)


def _trace(**overrides: object) -> AgentExpectancyTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        task="default task",
        task_class="code_generation",
        system_prompt="some prompt",
        observed_behaviors=["did the thing"],
        effort_signals=["quit early"],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return AgentExpectancyTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _t(name: str, score: float) -> dict[str, object]:
    return {
        "term": name,
        "score": score,
        "explanation": f"{name} explanation",
        "evidence_quotes": [],
    }


def _payload(
    expectancy: float = 0.15,
    instrumentality: float = 0.2,
    valence: float = 0.3,
    quality: str | None = None,
    bottleneck: str | None = None,
) -> str:
    # Default values produce a collapsed/expectancy bottleneck
    return json.dumps(
        {
            "terms": [
                _t("expectancy", expectancy),
                _t("instrumentality", instrumentality),
                _t("valence", valence),
            ],
            "motivation_score": expectancy * instrumentality * valence,
            "motivation_quality": quality or "collapsed",
            "bottleneck_term": bottleneck or "expectancy",
        }
    )


class TestDeterministicComputation:
    def test_product_computed_in_python_not_llm(self) -> None:
        # LLM reports a wrong score; calculator should ignore it and compute its own
        payload = json.dumps(
            {
                "terms": [
                    _t("expectancy", 0.5),
                    _t("instrumentality", 0.5),
                    _t("valence", 0.5),
                ],
                "motivation_score": 0.99,  # LLM lies
                "motivation_quality": "motivated",
                "bottleneck_term": "none",
            }
        )
        calc = VroomExpectancyCalculator(_Stub([payload]))
        detection = calc.run(_trace())
        # Real product: 0.5 * 0.5 * 0.5 = 0.125
        assert abs(detection.motivation_score - 0.125) < 0.01

    def test_negative_valence_produces_negative_score(self) -> None:
        payload = _payload(
            expectancy=0.8,
            instrumentality=0.8,
            valence=-0.5,
            quality="collapsed",
            bottleneck="valence",
        )
        calc = VroomExpectancyCalculator(_Stub([payload, "[]"]))
        detection = calc.run(_trace())
        # 0.8 * 0.8 * -0.5 = -0.32
        assert detection.motivation_score < 0

    def test_zero_term_collapses_product(self) -> None:
        payload = _payload(expectancy=0.0, instrumentality=0.9, valence=0.9)
        calc = VroomExpectancyCalculator(_Stub([payload, "[]"]))
        detection = calc.run(_trace())
        assert detection.motivation_score == 0.0
        assert detection.motivation_quality == "collapsed"


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentExpectancyTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown(self) -> None:
        detection = VroomDetection(
            agent_id="t",
            task_class="code_generation",
            terms=[
                VroomTermScore(
                    term=t,  # type: ignore[arg-type]
                    score=0.3,
                    explanation=f"{t} explanation",
                )
                for t in VROOM_TERMS
            ],
            motivation_score=0.027,
            bottleneck_term="expectancy",
            motivation_quality="collapsed",
            interventions=[
                VroomIntervention(
                    target_term="expectancy",
                    intervention_type="scaffold_subtasks",
                    description="scaffold",
                    suggested_implementation="prompt",
                    estimated_impact="high",
                    rationale="lifts E",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "Vroom Expectancy" in md
        assert "COLLAPSED" in md
        assert "expectancy" in md
        assert "E × I × V" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        calc = VroomExpectancyCalculator(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="task"):
            calc.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        calc = VroomExpectancyCalculator(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            calc.run(_trace(outcome=""))

    def test_no_evidence_rejected(self) -> None:
        calc = VroomExpectancyCalculator(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="system_prompt"):
            calc.run(_trace(system_prompt="", observed_behaviors=[], effort_signals=[]))


class TestDetectionPipeline:
    def test_collapsed_triggers_interventions(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_term": "expectancy",
                    "intervention_type": "scaffold_subtasks",
                    "description": "scaffold",
                    "suggested_implementation": "spec",
                    "estimated_impact": "high",
                    "rationale": "lifts E",
                }
            ]
        )
        stub = _Stub([_payload(), interventions])
        calc = VroomExpectancyCalculator(stub, model="test-model")
        detection = calc.run(_trace())
        assert len(stub.calls) == 2
        assert detection.motivation_quality == "collapsed"
        assert detection.bottleneck_term == "expectancy"
        assert len(detection.interventions) == 1

    def test_motivated_skips_interventions(self) -> None:
        payload = _payload(
            expectancy=0.9,
            instrumentality=0.9,
            valence=0.8,
            quality="motivated",
            bottleneck="none",
        )
        stub = _Stub([payload])
        calc = VroomExpectancyCalculator(stub, model="test-model")
        detection = calc.run(_trace())
        assert len(stub.calls) == 1
        assert detection.motivation_quality == "motivated"
        assert detection.interventions == []

    def test_missing_terms_filled(self) -> None:
        partial = json.dumps(
            {
                "terms": [_t("expectancy", 0.1)],
                "motivation_score": 0.0,
                "motivation_quality": "collapsed",
                "bottleneck_term": "expectancy",
            }
        )
        calc = VroomExpectancyCalculator(_Stub([partial, "[]"]))
        detection = calc.run(_trace())
        present = {t.term for t in detection.terms}
        assert present == set(VROOM_TERMS)

    def test_garbage_bottleneck_falls_back_to_lowest_term(self) -> None:
        bad = json.dumps(
            {
                "terms": [
                    _t("expectancy", 0.15),  # lowest
                    _t("instrumentality", 0.7),
                    _t("valence", 0.7),
                ],
                "motivation_score": 0.07,
                "motivation_quality": "weak",
                "bottleneck_term": "totally-fake",
            }
        )
        calc = VroomExpectancyCalculator(_Stub([bad, "[]"]))
        detection = calc.run(_trace())
        assert detection.bottleneck_term == "expectancy"

    def test_garbage_bottleneck_all_high_falls_back_to_none(self) -> None:
        bad = json.dumps(
            {
                "terms": [
                    _t("expectancy", 0.8),
                    _t("instrumentality", 0.8),
                    _t("valence", 0.8),
                ],
                "motivation_score": 0.512,
                "motivation_quality": "motivated",
                "bottleneck_term": "totally-fake",
            }
        )
        calc = VroomExpectancyCalculator(_Stub([bad]))
        detection = calc.run(_trace())
        assert detection.bottleneck_term == "none"


class TestMotivationQualityThresholds:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.5, "motivated"),
            (0.4, "motivated"),
            (0.3, "weak"),
            (0.06, "weak"),
            (0.05, "collapsed"),
            (0.0, "collapsed"),
            (-0.5, "collapsed"),
        ],
    )
    def test_threshold(self, score: float, expected: str) -> None:
        calc = VroomExpectancyCalculator(_Stub([]))
        assert calc._motivation_quality(score, "") == expected
