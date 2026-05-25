"""Tests for the Lewin Formula Diagnostic (B = f(I, E))."""

from __future__ import annotations

import json

import pytest

from vstack.lewin import (
    LOCI,
    AgentFailureTrace,
    EnvironmentalFactor,
    FailureStep,
    IndividualFactor,
    LewinAttributionDetector,
    LewinDetection,
    LewinIntervention,
    LocusEvidence,
)


def _step(content: str, type_: str = "output") -> FailureStep:
    return FailureStep(type=type_, content=content)  # type: ignore[arg-type]


def _trace(**overrides: object) -> AgentFailureTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        model_name="test-model",
        task="default task",
        steps=[_step("output 1")],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return AgentFailureTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace(
            individual_factors=[IndividualFactor(factor="base_model", description="X")],
            environmental_factors=[EnvironmentalFactor(factor="rag_context", description="stale")],
        )
        restored = AgentFailureTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task
        assert len(restored.individual_factors) == 1
        assert len(restored.environmental_factors) == 1

    def test_detection_markdown_all_sections(self) -> None:
        detection = LewinDetection(
            agent_id="t",
            dominant_locus="environmental",
            locus_scores={locus: 0.25 for locus in LOCI},
            loci=[
                LocusEvidence(
                    locus="environmental",
                    score=0.8,
                    severity="high",
                    explanation="stale rag",
                    evidence_quotes=["Factor: rag_context — stale 2024 PDF"],
                )
            ],
            interventions=[
                LewinIntervention(
                    target_locus="environmental",
                    intervention_type="change_rag_index",
                    description="refresh index",
                    suggested_implementation="reindex weekly",
                    estimated_impact="high",
                    rationale="addresses root cause",
                )
            ],
            attribution_quality="well-attributed",
            initial_attribution_correct=False,
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "Lewin Diagnostic" in md
        assert "Locus Scores" in md
        assert "Evidence by Locus" in md
        assert "Recommended Interventions" in md
        assert "environmental" in md
        assert "OVERTURNS" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = LewinAttributionDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = LewinAttributionDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_empty_steps_rejected(self) -> None:
        det = LewinAttributionDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="steps"):
            det.run(_trace(steps=[]))


class TestDetectionPipeline:
    def test_environmental_dominant(self) -> None:
        scores = json.dumps(
            [
                {
                    "locus": "internal",
                    "score": 0.1,
                    "severity": "low",
                    "explanation": "model behaved correctly",
                    "evidence_quotes": [],
                },
                {
                    "locus": "environmental",
                    "score": 0.9,
                    "severity": "high",
                    "explanation": "stale RAG",
                    "evidence_quotes": ["pricing-2024.pdf in index"],
                },
            ]
        )
        interventions = json.dumps(
            [
                {
                    "target_locus": "environmental",
                    "intervention_type": "change_rag_index",
                    "description": "refresh index",
                    "suggested_implementation": "weekly reindex",
                    "estimated_impact": "high",
                    "rationale": "addresses root cause",
                }
            ]
        )
        stub = _Stub([scores, interventions])
        det = LewinAttributionDetector(stub, model="test-model")
        detection = det.run(_trace(initial_attribution="model is bad"))

        assert len(stub.calls) == 2
        assert detection.dominant_locus == "environmental"
        assert detection.attribution_quality == "well-attributed"
        assert detection.locus_scores["environmental"] == 0.9
        assert detection.initial_attribution_correct is False
        assert len(detection.loci) == 3
        assert len(detection.interventions) == 1

    def test_missing_loci_filled(self) -> None:
        scores = json.dumps(
            [
                {
                    "locus": "environmental",
                    "score": 0.8,
                    "severity": "high",
                    "explanation": "only one locus reported",
                    "evidence_quotes": [],
                }
            ]
        )
        det = LewinAttributionDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace())
        present = {ev.locus for ev in detection.loci}
        assert present == set(LOCI)

    def test_environmental_wins_tiebreak(self) -> None:
        """Tie-break favors environmental over internal — the systematic
        bias to correct is over-attribution to the model."""
        scores = json.dumps(
            [
                {
                    "locus": "internal",
                    "score": 0.7,
                    "severity": "high",
                    "explanation": "tied",
                    "evidence_quotes": [],
                },
                {
                    "locus": "environmental",
                    "score": 0.7,
                    "severity": "high",
                    "explanation": "tied",
                    "evidence_quotes": [],
                },
            ]
        )
        det = LewinAttributionDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace())
        assert detection.dominant_locus == "environmental"

    def test_indeterminate_when_low(self) -> None:
        scores = json.dumps(
            [
                {
                    "locus": locus,
                    "score": 0.05,
                    "severity": "none",
                    "explanation": "no evidence",
                    "evidence_quotes": [],
                }
                for locus in LOCI
            ]
        )
        det = LewinAttributionDetector(_Stub([scores, "[]"]))
        detection = det.run(_trace())
        assert detection.dominant_locus == "indeterminate"
        assert detection.attribution_quality == "miscalibrated"
        assert detection.interventions == []


class TestInitialAttributionCheck:
    def test_no_initial_returns_none(self) -> None:
        det = LewinAttributionDetector(_Stub([]))
        result = det._check_initial_attribution(_trace(), "environmental")
        assert result is None

    def test_exact_match(self) -> None:
        det = LewinAttributionDetector(_Stub([]))
        result = det._check_initial_attribution(
            _trace(initial_attribution="environmental"), "environmental"
        )
        assert result is True

    def test_keyword_model_maps_internal(self) -> None:
        det = LewinAttributionDetector(_Stub([]))
        result = det._check_initial_attribution(
            _trace(initial_attribution="the model is bad at math"), "internal"
        )
        assert result is True

    def test_keyword_prompt_maps_environmental(self) -> None:
        det = LewinAttributionDetector(_Stub([]))
        result = det._check_initial_attribution(
            _trace(initial_attribution="our prompt is wrong"), "environmental"
        )
        assert result is True

    def test_overturned_attribution(self) -> None:
        det = LewinAttributionDetector(_Stub([]))
        result = det._check_initial_attribution(
            _trace(initial_attribution="model is bad"), "environmental"
        )
        assert result is False


class TestAttributionQuality:
    def test_well_attributed_large_gap(self) -> None:
        det = LewinAttributionDetector(_Stub([]))
        scores = {"internal": 0.1, "environmental": 0.8, "interactional": 0.2}
        assert det._attribution_quality(scores) == "well-attributed"

    def test_ambiguous_small_gap(self) -> None:
        det = LewinAttributionDetector(_Stub([]))
        scores = {"internal": 0.6, "environmental": 0.5, "interactional": 0.3}
        assert det._attribution_quality(scores) == "ambiguous"

    def test_miscalibrated_low_top(self) -> None:
        det = LewinAttributionDetector(_Stub([]))
        scores = {"internal": 0.1, "environmental": 0.1, "interactional": 0.1}
        assert det._attribution_quality(scores) == "miscalibrated"
