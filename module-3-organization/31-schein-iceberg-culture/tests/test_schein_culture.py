"""Tests for the Schein Iceberg Culture Audit."""

from __future__ import annotations

import json

import pytest

from vstack.schein_culture import (
    CULTURE_LAYERS,
    AgentCultureTrace,
    CultureAuditDetection,
    CultureAuditDetector,
    CultureIntervention,
    LayerEvidence,
)


def _trace(**overrides: object) -> AgentCultureTrace:
    base: dict[str, object] = dict(
        agent_id="test",
        model_name="test-model",
        task="default task",
        system_prompt="Be helpful and concise.",
        observed_behaviors=["agent did the thing"],
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


def _layer(name: str, coherence: float = 0.5) -> dict[str, object]:
    return {
        "layer": name,
        "summary": f"{name} summary",
        "coherence_score": coherence,
        "observations": [],
    }


def _payload(
    drift: str = "espoused_vs_assumptions",
    alignment: float = 0.25,
    quality: str = "incoherent",
) -> str:
    return json.dumps(
        {
            "layers": [
                _layer("artifacts", 0.2),
                _layer("espoused_values", 0.3),
                _layer("underlying_assumptions", 0.9),
            ],
            "alignment_score": alignment,
            "dominant_drift": drift,
            "culture_quality": quality,
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = AgentCultureTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = CultureAuditDetection(
            agent_id="t",
            layers=[
                LayerEvidence(
                    layer=cl,  # type: ignore[arg-type]
                    summary=f"{cl} summary",
                    coherence_score=0.5,
                    observations=[f"{cl} obs"],
                )
                for cl in CULTURE_LAYERS
            ],
            alignment_score=0.25,
            dominant_drift="espoused_vs_assumptions",
            culture_quality="incoherent",
            interventions=[
                CultureIntervention(
                    target_layer="underlying_assumptions",
                    intervention_type="scaffold_around_assumption",
                    description="add a scaffold",
                    suggested_implementation="pipeline",
                    estimated_impact="high",
                    rationale="counters training prior",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "Schein Iceberg" in md
        assert "INCOHERENT" in md
        assert "artifacts" in md
        assert "espoused_values" in md
        assert "underlying_assumptions" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = CultureAuditDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = CultureAuditDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_both_prompt_and_behaviors_empty_rejected(self) -> None:
        det = CultureAuditDetector(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="system_prompt"):
            det.run(_trace(system_prompt="", observed_behaviors=[]))


class TestDetectionPipeline:
    def test_incoherent_drift(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_layer": "underlying_assumptions",
                    "intervention_type": "scaffold_around_assumption",
                    "description": "scaffold",
                    "suggested_implementation": "pipeline",
                    "estimated_impact": "high",
                    "rationale": "counters training",
                }
            ]
        )
        stub = _Stub([_payload(), interventions])
        det = CultureAuditDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 2
        assert detection.dominant_drift == "espoused_vs_assumptions"
        assert detection.culture_quality == "incoherent"
        assert len(detection.layers) == 3
        assert len(detection.interventions) == 1

    def test_aligned_skips_interventions(self) -> None:
        payload = _payload(drift="none-observed", alignment=0.9, quality="aligned")
        stub = _Stub([payload])
        det = CultureAuditDetector(stub, model="test-model")
        detection = det.run(_trace())
        # aligned => single call only
        assert len(stub.calls) == 1
        assert detection.culture_quality == "aligned"
        assert detection.interventions == []

    def test_missing_layers_filled(self) -> None:
        partial = json.dumps(
            {
                "layers": [_layer("artifacts", 0.5)],
                "alignment_score": 0.4,
                "dominant_drift": "artifacts_vs_espoused",
                "culture_quality": "drifting",
            }
        )
        det = CultureAuditDetector(_Stub([partial, "[]"]))
        detection = det.run(_trace())
        present = {layer_ev.layer for layer_ev in detection.layers}
        assert present == set(CULTURE_LAYERS)

    def test_garbage_drift_falls_back_to_none(self) -> None:
        bad = json.dumps(
            {
                "layers": [_layer(cl, 0.5) for cl in CULTURE_LAYERS],
                "alignment_score": 0.4,
                "dominant_drift": "garbage_value",
                "culture_quality": "garbage",
            }
        )
        # Even though LLM returned a garbage drift label, generator coerces to none-observed
        # but the alignment_score 0.4 still puts quality at "drifting"
        det = CultureAuditDetector(_Stub([bad, "[]"]))
        detection = det.run(_trace())
        assert detection.dominant_drift == "none-observed"
        assert detection.culture_quality == "drifting"


class TestCultureQualityThresholds:
    @pytest.mark.parametrize(
        "alignment,drift,expected",
        [
            (0.9, "none-observed", "aligned"),
            (0.75, "none-observed", "aligned"),
            (0.5, "artifacts_vs_espoused", "drifting"),
            (0.4, "artifacts_vs_espoused", "drifting"),
            (0.2, "espoused_vs_assumptions", "incoherent"),
            (0.0, "espoused_vs_assumptions", "incoherent"),
        ],
    )
    def test_threshold(self, alignment: float, drift: str, expected: str) -> None:
        det = CultureAuditDetector(_Stub([]))
        assert det._culture_quality(alignment, drift, "") == expected
