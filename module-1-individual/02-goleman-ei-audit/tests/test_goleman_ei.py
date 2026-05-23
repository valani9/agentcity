"""Tests for the Goleman 4-Domain EI Audit."""

from __future__ import annotations

import json

import pytest

from agentcity.goleman_ei import (
    EI_DOMAINS,
    AgentEITrace,
    DomainScore,
    EIAuditDetector,
    EIDetection,
    EIIntervention,
)


def _trace(**overrides: object) -> AgentEITrace:
    base: dict[str, object] = dict(
        agent_id="test",
        task="default task",
        interaction_class="customer_support",
        observed_behaviors=["did the thing"],
        user_signals=["user typed in caps"],
        self_reports=["i am confident"],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return AgentEITrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _dom(name: str, score: float = 0.5) -> dict[str, object]:
    return {
        "domain": name,
        "score": score,
        "explanation": f"{name} explanation",
        "evidence_quotes": [],
    }


def _payload(
    quality: str = "developing",
    overall_ei: float = 0.48,
    weakest: str = "social_awareness",
) -> str:
    return json.dumps(
        {
            "domains": [
                _dom("self_awareness", 0.85),
                _dom("self_management", 0.8),
                _dom("social_awareness", 0.1),
                _dom("relationship_management", 0.15),
            ],
            "overall_ei": overall_ei,
            "ei_quality": quality,
            "weakest_domain": weakest,
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentEITrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = EIDetection(
            agent_id="t",
            interaction_class="customer_support",
            domains=[
                DomainScore(
                    domain=d,  # type: ignore[arg-type]
                    score=0.5,
                    explanation=f"{d} explanation",
                )
                for d in EI_DOMAINS
            ],
            overall_ei=0.5,
            ei_quality="developing",
            weakest_domain="social_awareness",
            interventions=[
                EIIntervention(
                    target_domain="social_awareness",
                    intervention_type="add_emotion_reading_step",
                    description="read emotion",
                    suggested_implementation="prompt",
                    estimated_impact="high",
                    rationale="closes gap",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "4-Domain EI Audit" in md
        assert "DEVELOPING" in md
        assert "social_awareness" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = EIAuditDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = EIAuditDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_no_signals_rejected(self) -> None:
        det = EIAuditDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="observed_behaviors"):
            det.run(_trace(observed_behaviors=[], user_signals=[], self_reports=[]))


class TestDetectionPipeline:
    def test_developing_with_weakest(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_domain": "social_awareness",
                    "intervention_type": "add_emotion_reading_step",
                    "description": "read",
                    "suggested_implementation": "spec",
                    "estimated_impact": "high",
                    "rationale": "closes",
                }
            ]
        )
        stub = _Stub([_payload(), interventions])
        det = EIAuditDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.ei_quality == "developing"
        assert detection.weakest_domain == "social_awareness"
        assert len(detection.domains) == 4
        assert len(detection.interventions) == 1

    def test_high_ei_skips_interventions(self) -> None:
        payload = _payload(quality="high-ei", overall_ei=0.85, weakest="none")
        stub = _Stub([payload])
        det = EIAuditDetector(stub, model="test-model")
        detection = det.run(_trace())
        assert len(stub.calls) == 1
        assert detection.ei_quality == "high-ei"
        assert detection.weakest_domain == "none"
        assert detection.interventions == []

    def test_missing_domains_filled(self) -> None:
        partial = json.dumps(
            {
                "domains": [_dom("social_awareness", 0.1)],
                "overall_ei": 0.5,
                "ei_quality": "developing",
                "weakest_domain": "social_awareness",
            }
        )
        det = EIAuditDetector(_Stub([partial, "[]"]))
        detection = det.run(_trace())
        present = {d.domain for d in detection.domains}
        assert present == set(EI_DOMAINS)

    def test_garbage_weakest_falls_back_to_lowest_score(self) -> None:
        bad = json.dumps(
            {
                "domains": [
                    _dom("self_awareness", 0.9),
                    _dom("self_management", 0.85),
                    _dom("social_awareness", 0.1),  # lowest
                    _dom("relationship_management", 0.4),
                ],
                "overall_ei": 0.56,
                "ei_quality": "developing",
                "weakest_domain": "totally-fake",
            }
        )
        det = EIAuditDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        assert detection.weakest_domain == "social_awareness"

    def test_garbage_weakest_all_high_falls_back_to_none(self) -> None:
        bad = json.dumps(
            {
                "domains": [
                    _dom("self_awareness", 0.8),
                    _dom("self_management", 0.85),
                    _dom("social_awareness", 0.75),
                    _dom("relationship_management", 0.8),
                ],
                "overall_ei": 0.8,
                "ei_quality": "high-ei",
                "weakest_domain": "totally-fake",
            }
        )
        det = EIAuditDetector(_Stub([bad]))
        detection = det.run(_trace())
        # all domains >= 0.7 → "none"
        assert detection.weakest_domain == "none"


class TestEIQualityThresholds:
    @pytest.mark.parametrize(
        "overall_ei,expected",
        [
            (0.9, "high-ei"),
            (0.75, "high-ei"),
            (0.74, "developing"),
            (0.4, "developing"),
            (0.39, "low-ei"),
            (0.0, "low-ei"),
        ],
    )
    def test_threshold(self, overall_ei: float, expected: str) -> None:
        det = EIAuditDetector(_Stub([]))
        assert det._ei_quality(overall_ei, "") == expected
