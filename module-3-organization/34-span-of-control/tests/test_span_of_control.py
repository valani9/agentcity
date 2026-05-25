"""Tests for the Span-of-Control / Centralization Calculator."""

from __future__ import annotations

import json

import pytest

from vstack.span_of_control import (
    AgentNode,
    CrewLoadTrace,
    SpanIntervention,
    SpanLoadAnalysis,
    SpanLoadCalculator,
    SpanMetric,
    centralization_index,
    compute_all_metrics_payload,
    compute_span_counts,
    decision_bottleneck_score,
    hierarchy_depth,
    max_span,
    mean_span,
    span_gini,
)


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _crew_flat(n: int = 4) -> list[AgentNode]:
    return [AgentNode(agent_id=f"peer-{i}", decision_authority="full") for i in range(n)]


def _crew_hub_spoke(n_workers: int = 12) -> list[AgentNode]:
    return [
        AgentNode(agent_id="orchestrator", decision_authority="full"),
        *[
            AgentNode(
                agent_id=f"worker-{i}",
                reports_to=["orchestrator"],
                decision_authority="advisory",
            )
            for i in range(n_workers)
        ],
    ]


def _trace(agents: list[AgentNode], **overrides: object) -> CrewLoadTrace:
    base: dict[str, object] = dict(
        crew_id="test",
        task="default task",
        agents=agents,
        incoming_request_rate=10.0,
        outcome="default outcome",
        success=False,
    )
    base.update(overrides)
    return CrewLoadTrace(**base)  # type: ignore[arg-type]


class TestDeterministicMetrics:
    def test_span_counts_flat(self) -> None:
        agents = _crew_flat(4)
        counts = compute_span_counts(agents)
        assert all(c == 0 for c in counts.values())

    def test_span_counts_hub_spoke(self) -> None:
        agents = _crew_hub_spoke(12)
        counts = compute_span_counts(agents)
        assert counts["orchestrator"] == 12
        assert all(counts[f"worker-{i}"] == 0 for i in range(12))

    def test_max_span(self) -> None:
        assert max_span(_crew_flat(4)) == 0
        assert max_span(_crew_hub_spoke(12)) == 12

    def test_mean_span_no_supervisors(self) -> None:
        # Flat-peer crew: no supervisors → mean_span is 0
        assert mean_span(_crew_flat(4)) == 0.0

    def test_mean_span_hub_spoke(self) -> None:
        assert mean_span(_crew_hub_spoke(12)) == 12.0

    def test_centralization_high_when_hub_spoke(self) -> None:
        cent = centralization_index(_crew_hub_spoke(12))
        # Single full-authority orchestrator dominates
        assert cent > 0.5

    def test_centralization_low_when_flat(self) -> None:
        cent = centralization_index(_crew_flat(4))
        # 4 equal full-authority agents; top 20% = 1 → 1/4 = 0.25
        assert cent <= 0.35

    def test_hierarchy_depth_flat(self) -> None:
        assert hierarchy_depth(_crew_flat(4)) == 1

    def test_hierarchy_depth_chain(self) -> None:
        agents = [
            AgentNode(agent_id="a"),
            AgentNode(agent_id="b", reports_to=["a"]),
            AgentNode(agent_id="c", reports_to=["b"]),
            AgentNode(agent_id="d", reports_to=["c"]),
        ]
        # d -> c -> b -> a : depth 4
        assert hierarchy_depth(agents) == 4

    def test_hierarchy_depth_handles_cycle(self) -> None:
        agents = [
            AgentNode(agent_id="a", reports_to=["b"]),
            AgentNode(agent_id="b", reports_to=["a"]),
        ]
        # Cycle — should not infinite-loop
        d = hierarchy_depth(agents)
        assert d >= 1
        assert d < 100

    def test_span_gini_balanced(self) -> None:
        # 2 supervisors, each with 3 subordinates → perfectly balanced supervisor distribution
        # But the metric is over the FULL counts dict, including 0-span workers.
        # Workers all have count=0 and supervisors have count=3 → some inequality
        agents = [
            AgentNode(agent_id="s1"),
            AgentNode(agent_id="s2"),
            *[AgentNode(agent_id=f"w1-{i}", reports_to=["s1"]) for i in range(3)],
            *[AgentNode(agent_id=f"w2-{i}", reports_to=["s2"]) for i in range(3)],
        ]
        gini = span_gini(agents)
        # 0 for most agents, 3 for 2 supervisors → some inequality, not extreme
        assert 0.0 < gini < 0.8

    def test_span_gini_extreme(self) -> None:
        # Single orchestrator with 12 workers → very high inequality
        gini = span_gini(_crew_hub_spoke(12))
        assert gini > 0.7

    def test_bottleneck_high_load_orchestrator(self) -> None:
        score, ids = decision_bottleneck_score(_crew_hub_spoke(12), incoming_request_rate=100.0)
        assert score > 0.5
        assert "orchestrator" in ids

    def test_bottleneck_low_load_flat(self) -> None:
        score, ids = decision_bottleneck_score(_crew_flat(4), incoming_request_rate=1.0)
        # Flat peers with full authority but 0 span → no bottleneck
        assert score == 0.0
        assert ids == []


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace(_crew_hub_spoke(5))
        restored = CrewLoadTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task
        assert len(restored.agents) == 6

    def test_analysis_markdown(self) -> None:
        analysis = SpanLoadAnalysis(
            crew_id="t",
            metrics=[
                SpanMetric(
                    metric="max_span",
                    value=12.0,
                    normalized_score=1.0,
                    explanation="severe",
                )
            ],
            structural_load_score=0.8,
            structural_load_quality="overloaded",
            bottleneck_agent_ids=["orchestrator"],
            interventions=[
                SpanIntervention(
                    target_metric="max_span",
                    intervention_type="split_supervisor_load",
                    description="split",
                    suggested_implementation="spec",
                    estimated_impact="high",
                    rationale="closes",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = analysis.to_markdown()
        assert "Span-of-Control" in md
        assert "OVERLOADED" in md
        assert "orchestrator" in md
        assert "max_span" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        calc = SpanLoadCalculator(_Stub(["[]"]))
        with pytest.raises(ValueError, match="task"):
            calc.run(_trace(_crew_flat(2), task=""))

    def test_empty_outcome_rejected(self) -> None:
        calc = SpanLoadCalculator(_Stub(["[]"]))
        with pytest.raises(ValueError, match="outcome"):
            calc.run(_trace(_crew_flat(2), outcome=""))

    def test_empty_agents_rejected(self) -> None:
        with pytest.raises(Exception):
            _trace([])


class TestAnalysisPipeline:
    def test_overloaded_with_interventions(self) -> None:
        interventions = json.dumps(
            [
                {
                    "target_metric": "decision_bottleneck",
                    "intervention_type": "delegate_decision_authority",
                    "description": "delegate",
                    "suggested_implementation": "spec",
                    "estimated_impact": "high",
                    "rationale": "closes",
                }
            ]
        )
        stub = _Stub([interventions])
        calc = SpanLoadCalculator(stub, model="test-model")
        analysis = calc.run(_trace(_crew_hub_spoke(12), incoming_request_rate=100.0))

        assert len(stub.calls) == 1
        assert analysis.structural_load_quality == "overloaded"
        assert "orchestrator" in analysis.bottleneck_agent_ids
        assert len(analysis.interventions) == 1
        # All 6 metrics should be present
        assert len(analysis.metrics) == 6

    def test_well_balanced_skips_llm(self) -> None:
        # Small balanced crew, no load → should be well-balanced, no LLM call
        stub = _Stub(["[]"])
        calc = SpanLoadCalculator(stub, model="test-model")
        analysis = calc.run(_trace(_crew_flat(3), incoming_request_rate=0.5))
        assert analysis.structural_load_quality == "well-balanced"
        assert analysis.interventions == []
        # LLM should not have been called
        assert len(stub.calls) == 0

    def test_metrics_payload_includes_all_six(self) -> None:
        trace = _trace(_crew_hub_spoke(8))
        metrics, _ = compute_all_metrics_payload(trace)
        names = set(metrics.keys())
        assert names == {
            "max_span",
            "mean_span",
            "centralization_index",
            "hierarchy_depth",
            "span_gini",
            "decision_bottleneck",
        }


class TestLoadQualityThresholds:
    @pytest.mark.parametrize(
        "load_score,expected",
        [
            (0.0, "well-balanced"),
            (0.29, "well-balanced"),
            (0.3, "under-stress"),
            (0.59, "under-stress"),
            (0.6, "overloaded"),
            (1.0, "overloaded"),
        ],
    )
    def test_threshold(self, load_score: float, expected: str) -> None:
        calc = SpanLoadCalculator(_Stub([]))
        assert calc._load_quality(load_score) == expected
