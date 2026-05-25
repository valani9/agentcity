"""Tests for the Org-Structure Matrix Analyzer."""

from __future__ import annotations

import json

import pytest

from vstack.org_structure import (
    STRUCTURE_DIMENSIONS,
    AgentRole,
    CrewStructureTrace,
    StructureAnalysis,
    StructureDimensionScore,
    StructureIntervention,
    StructureMatrixAnalyzer,
)


def _trace(**overrides: object) -> CrewStructureTrace:
    base: dict[str, object] = dict(
        crew_id="test",
        task="default task",
        task_class="incident_response",
        agents=[
            AgentRole(agent_id="a1", role_name="generalist"),
            AgentRole(agent_id="a2", role_name="generalist"),
        ],
        observed_behaviors=["did the thing"],
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return CrewStructureTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _dim(
    name: str, observed: float = 0.5, target: float = 0.5, fit: float = 1.0
) -> dict[str, object]:
    return {
        "dimension": name,
        "observed_score": observed,
        "target_score": target,
        "fit_score": fit,
        "explanation": f"{name} explanation",
        "evidence_quotes": [],
    }


def _payload(
    quality: str = "partial-fit",
    overall_fit: float = 0.58,
    gap: str = "centralization",
    archetype: str = "flat-peer",
) -> str:
    return json.dumps(
        {
            "archetype": archetype,
            "dimensions": [
                _dim("specialization", 0.1, 0.7, 0.4),
                _dim("formalization", 0.2, 0.3, 0.9),
                _dim("centralization", 0.1, 0.9, 0.2),
                _dim("hierarchy", 0.0, 0.5, 0.5),
                _dim("span_of_control", 0.5, 0.5, 1.0),
                _dim("departmentalization", 0.1, 0.6, 0.5),
            ],
            "overall_fit": overall_fit,
            "fit_quality": quality,
            "biggest_gap": gap,
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = CrewStructureTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task
        assert len(restored.agents) == 2

    def test_analysis_markdown_all_sections(self) -> None:
        analysis = StructureAnalysis(
            crew_id="t",
            task_class="incident_response",
            archetype="flat-peer",
            dimensions=[
                StructureDimensionScore(
                    dimension=d,  # type: ignore[arg-type]
                    observed_score=0.5,
                    target_score=0.5,
                    fit_score=1.0,
                    explanation=f"{d} explanation",
                )
                for d in STRUCTURE_DIMENSIONS
            ],
            overall_fit=0.5,
            fit_quality="partial-fit",
            biggest_gap="centralization",
            interventions=[
                StructureIntervention(
                    target_dimension="centralization",
                    direction="increase",
                    intervention_type="add_supervisor_layer",
                    description="add a commander",
                    suggested_implementation="new role",
                    estimated_impact="high",
                    rationale="closes gap",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = analysis.to_markdown()
        assert "Org-Structure Matrix Analysis" in md
        assert "PARTIAL-FIT" in md
        assert "flat-peer" in md
        assert "centralization" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        analyzer = StructureMatrixAnalyzer(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="task"):
            analyzer.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        analyzer = StructureMatrixAnalyzer(_Stub([_payload(), "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            analyzer.run(_trace(outcome=""))

    def test_empty_agents_rejected(self) -> None:
        # Pydantic catches min_length=1 before reaching the generator
        with pytest.raises(Exception):
            _trace(agents=[])


class TestAnalysisPipeline:
    def test_partial_fit_with_gap(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_dimension": "centralization",
                    "direction": "increase",
                    "intervention_type": "add_supervisor_layer",
                    "description": "add commander",
                    "suggested_implementation": "spec",
                    "estimated_impact": "high",
                    "rationale": "closes gap",
                }
            ]
        )
        stub = _Stub([_payload(), interventions])
        analyzer = StructureMatrixAnalyzer(stub, model="test-model")
        analysis = analyzer.run(_trace())

        assert len(stub.calls) == 2
        assert analysis.fit_quality == "partial-fit"
        assert analysis.biggest_gap == "centralization"
        assert analysis.archetype == "flat-peer"
        assert len(analysis.dimensions) == 6
        assert len(analysis.interventions) == 1

    def test_well_fit_skips_interventions(self) -> None:
        payload = _payload(quality="well-fit", overall_fit=0.9, gap="none")
        stub = _Stub([payload])
        analyzer = StructureMatrixAnalyzer(stub, model="test-model")
        analysis = analyzer.run(_trace())
        assert len(stub.calls) == 1
        assert analysis.fit_quality == "well-fit"
        assert analysis.biggest_gap == "none"
        assert analysis.interventions == []

    def test_missing_dimensions_filled(self) -> None:
        partial = json.dumps(
            {
                "archetype": "flat-peer",
                "dimensions": [_dim("centralization", 0.1, 0.9, 0.2)],
                "overall_fit": 0.5,
                "fit_quality": "partial-fit",
                "biggest_gap": "centralization",
            }
        )
        analyzer = StructureMatrixAnalyzer(_Stub([partial, "[]"]))
        analysis = analyzer.run(_trace())
        present = {d.dimension for d in analysis.dimensions}
        assert present == set(STRUCTURE_DIMENSIONS)

    def test_garbage_archetype_falls_back_to_mixed(self) -> None:
        bad = json.dumps(
            {
                "archetype": "totally-fake",
                "dimensions": [_dim("centralization", 0.1, 0.9, 0.2)],
                "overall_fit": 0.4,
                "fit_quality": "misfit",
                "biggest_gap": "centralization",
            }
        )
        analyzer = StructureMatrixAnalyzer(_Stub([bad, "[]"]))
        analysis = analyzer.run(_trace())
        assert analysis.archetype == "mixed"

    def test_garbage_gap_falls_back_to_largest(self) -> None:
        bad = json.dumps(
            {
                "archetype": "flat-peer",
                "dimensions": [
                    _dim("specialization", 0.1, 0.7, 0.4),  # |delta| = 0.6
                    _dim("formalization", 0.5, 0.5, 1.0),
                    _dim("centralization", 0.1, 0.9, 0.2),  # |delta| = 0.8
                    _dim("hierarchy", 0.5, 0.5, 1.0),
                    _dim("span_of_control", 0.5, 0.5, 1.0),
                    _dim("departmentalization", 0.5, 0.5, 1.0),
                ],
                "overall_fit": 0.6,
                "fit_quality": "partial-fit",
                "biggest_gap": "garbage_value",
            }
        )
        analyzer = StructureMatrixAnalyzer(_Stub([bad, "[]"]))
        analysis = analyzer.run(_trace())
        assert analysis.biggest_gap == "centralization"


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
        analyzer = StructureMatrixAnalyzer(_Stub([]))
        assert analyzer._fit_quality(overall_fit, "") == expected
