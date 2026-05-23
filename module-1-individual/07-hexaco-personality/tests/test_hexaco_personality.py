"""Tests for the HEXACO Personality Diagnostic."""

from __future__ import annotations

import json

import pytest

from agentcity.hexaco import (
    HEXACO_FACTORS,
    AgentPersonalityTrace,
    FactorScore,
    HEXACODetection,
    HEXACOIntervention,
    HEXACOPersonalityDetector,
)


def _trace(**overrides: object) -> AgentPersonalityTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        task="default task",
        task_class="tool_use",
        observed_behaviors=["did the thing"],
        safety_relevant_events=["bypassed approval"],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return AgentPersonalityTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _f(name: str, score: float = 0.5, target: float = 0.5, fit: float = 1.0) -> dict[str, object]:
    return {
        "factor": name,
        "score": score,
        "target_score": target,
        "fit_score": fit,
        "explanation": f"{name} explanation",
        "evidence_quotes": [],
    }


def _payload(
    quality: str = "developing",
    overall_fit: float = 0.68,
    h_risk: str = "high",
    weakest: str = "honesty_humility",
) -> str:
    return json.dumps(
        {
            "factors": [
                _f("honesty_humility", 0.3, 0.85, 0.45),
                _f("emotionality", 0.3, 0.5, 0.8),
                _f("extraversion", 0.5, 0.4, 0.9),
                _f("agreeableness", 0.9, 0.5, 0.6),
                _f("conscientiousness", 0.3, 0.85, 0.45),
                _f("openness", 0.4, 0.5, 0.9),
            ],
            "overall_fit": overall_fit,
            "h_factor_risk": h_risk,
            "fit_quality": quality,
            "weakest_factor": weakest,
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentPersonalityTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown(self) -> None:
        detection = HEXACODetection(
            agent_id="t",
            task_class="tool_use",
            factors=[
                FactorScore(
                    factor=f,  # type: ignore[arg-type]
                    score=0.5,
                    target_score=0.5,
                    fit_score=1.0,
                    explanation=f"{f} explanation",
                )
                for f in HEXACO_FACTORS
            ],
            overall_fit=0.68,
            h_factor_risk="high",
            fit_quality="developing",
            weakest_factor="honesty_humility",
            interventions=[
                HEXACOIntervention(
                    target_factor="honesty_humility",
                    direction="increase",
                    intervention_type="add_h_factor_guardrail",
                    description="guardrail",
                    suggested_implementation="prompt",
                    estimated_impact="high",
                    rationale="safety",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "HEXACO" in md
        assert "HIGH" in md
        assert "honesty_humility" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = HEXACOPersonalityDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = HEXACOPersonalityDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_no_evidence_rejected(self) -> None:
        det = HEXACOPersonalityDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="observed_behaviors"):
            det.run(_trace(observed_behaviors=[], safety_relevant_events=[]))


class TestDetectionPipeline:
    def test_high_h_risk_triggers_interventions(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_factor": "honesty_humility",
                    "direction": "increase",
                    "intervention_type": "add_h_factor_guardrail",
                    "description": "guardrail",
                    "suggested_implementation": "spec",
                    "estimated_impact": "high",
                    "rationale": "safety",
                }
            ]
        )
        stub = _Stub([_payload(), interventions])
        det = HEXACOPersonalityDetector(stub, model="test-model")
        detection = det.run(_trace())
        assert len(stub.calls) == 2
        assert detection.h_factor_risk == "high"
        assert detection.weakest_factor == "honesty_humility"
        assert len(detection.interventions) == 1

    def test_well_fit_and_low_h_risk_skips_interventions(self) -> None:
        payload = _payload(quality="well-fit", overall_fit=0.9, h_risk="low", weakest="none")
        # Need to also adjust factor scores so H >= 0.7 — modify the payload by
        # parsing and resetting
        data = json.loads(payload)
        for f in data["factors"]:
            if f["factor"] == "honesty_humility":
                f["score"] = 0.85
                f["fit_score"] = 0.95
            else:
                f["fit_score"] = 0.9
        stub = _Stub([json.dumps(data)])
        det = HEXACOPersonalityDetector(stub, model="test-model")
        detection = det.run(_trace())
        assert len(stub.calls) == 1
        assert detection.fit_quality == "well-fit"
        assert detection.h_factor_risk == "low"
        assert detection.interventions == []

    def test_well_fit_but_elevated_h_still_intervenes(self) -> None:
        # Even with well-fit, elevated H-risk should trigger interventions
        data = json.loads(_payload(quality="well-fit", overall_fit=0.8, h_risk="elevated"))
        stub = _Stub([json.dumps(data), "[]"])
        det = HEXACOPersonalityDetector(stub, model="test-model")
        detection = det.run(_trace())
        # well-fit AND elevated → not skipped
        assert len(stub.calls) == 2
        assert detection.h_factor_risk == "elevated"

    def test_missing_factors_filled(self) -> None:
        partial = json.dumps(
            {
                "factors": [_f("honesty_humility", 0.3, 0.85, 0.45)],
                "overall_fit": 0.6,
                "h_factor_risk": "high",
                "fit_quality": "developing",
                "weakest_factor": "honesty_humility",
            }
        )
        det = HEXACOPersonalityDetector(_Stub([partial, "[]"]))
        detection = det.run(_trace())
        present = {f.factor for f in detection.factors}
        assert present == set(HEXACO_FACTORS)

    def test_garbage_h_risk_falls_back_to_h_factor_score(self) -> None:
        bad = json.dumps(
            {
                "factors": [
                    _f("honesty_humility", 0.3, 0.85, 0.45),
                    _f("emotionality", 0.5, 0.5, 1.0),
                    _f("extraversion", 0.5, 0.5, 1.0),
                    _f("agreeableness", 0.5, 0.5, 1.0),
                    _f("conscientiousness", 0.5, 0.5, 1.0),
                    _f("openness", 0.5, 0.5, 1.0),
                ],
                "overall_fit": 0.75,
                "h_factor_risk": "garbage",
                "fit_quality": "developing",
                "weakest_factor": "honesty_humility",
            }
        )
        det = HEXACOPersonalityDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        # H-factor score 0.3 → "high" risk
        assert detection.h_factor_risk == "high"
