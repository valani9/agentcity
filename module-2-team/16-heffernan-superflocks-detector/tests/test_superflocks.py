"""Tests for the Heffernan Superflocks Detector."""

from __future__ import annotations

import json

import pytest

from vstack.superflocks import (
    AgentCapability,
    FragilityIntervention,
    RoutingDecision,
    RoutingTrace,
    SuperflocksDetection,
    SuperflocksDetector,
    SuperflocksMetric,
)


def _decision(
    task_id: str,
    routed_to: str = "claude",
    task_class: str = "research",
    outcome: str = "success",
) -> RoutingDecision:
    return RoutingDecision(  # type: ignore[arg-type]
        task_id=task_id,
        task_class=task_class,
        routed_to=routed_to,
        outcome=outcome,
    )


def _trace(**overrides: object) -> RoutingTrace:
    base: dict[str, object] = dict(
        trace_id="test",
        window_description="test window",
        agents=["claude", "gpt"],
        capabilities=[],
        routing_decisions=[
            _decision("t01", "claude"),
            _decision("t02", "claude"),
            _decision("t03", "gpt"),
        ],
        outcome="default outcome",
        success=True,
    )
    base.update(overrides)
    return RoutingTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _metric(name: str, value: float = 0.5, severity: str = "medium") -> dict[str, object]:
    return {
        "name": name,
        "value": value,
        "explanation": f"{name} explanation",
        "severity": severity,
    }


def _payload(quality: str = "concentrated") -> str:
    return json.dumps(
        {
            "metrics": [
                _metric("top_agent_share", 0.67, "high"),
                _metric("routing_gini", 0.5, "medium"),
                _metric("complementarity_utilization", 0.33, "medium"),
                _metric("fallback_coverage", 1.0, "low"),
                _metric("failure_clustering", 0.0, "none"),
            ],
            "fragility_quality": quality,
            "interventions": [
                {
                    "intervention_type": "redundant_routing",
                    "description": "route in parallel",
                    "suggested_implementation": "pipeline",
                    "estimated_impact": "high",
                    "rationale": "builds fallback",
                }
            ],
        }
    )


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = RoutingTrace.model_validate_json(trace.model_dump_json())
        assert restored.window_description == trace.window_description

    def test_detection_markdown_all_sections(self) -> None:
        detection = SuperflocksDetection(
            trace_id="t",
            top_agent="claude",
            top_agent_share=0.9,
            routing_gini=0.78,
            fragility_score=0.75,
            fragility_quality="superflocks",
            metrics=[
                SuperflocksMetric(
                    name="top_agent_share",
                    value=0.9,
                    explanation="claude won 90%",
                    severity="high",
                )
            ],
            interventions=[
                FragilityIntervention(
                    intervention_type="redundant_routing",
                    description="route in parallel",
                    suggested_implementation="pipeline",
                    estimated_impact="high",
                    rationale="reduces concentration",
                )
            ],
            generator_model="test-model",
            success=False,
        )
        md = detection.to_markdown()
        assert "Superflocks Detection" in md
        assert "SUPERFLOCKS" in md
        assert "claude" in md
        assert "Per-Metric Detail" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_outcome_rejected(self) -> None:
        det = SuperflocksDetector(_Stub([_payload()]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_empty_agents_rejected(self) -> None:
        det = SuperflocksDetector(_Stub([_payload()]))
        with pytest.raises(ValueError, match="agents"):
            det.run(_trace(agents=[]))

    def test_single_decision_rejected(self) -> None:
        det = SuperflocksDetector(_Stub([_payload()]))
        with pytest.raises(ValueError, match="at least 2 decisions"):
            det.run(_trace(routing_decisions=[_decision("t01")]))


class TestLocalMetrics:
    def test_top_agent_share(self) -> None:
        # 3 of 4 decisions to claude
        trace = _trace(
            routing_decisions=[
                _decision("t01", "claude"),
                _decision("t02", "claude"),
                _decision("t03", "claude"),
                _decision("t04", "gpt"),
            ]
        )
        det = SuperflocksDetector(_Stub([_payload()]))
        metrics = det._compute_metrics(trace)
        assert metrics["top_agent_share"] == 0.75

    def test_routing_gini_inequality(self) -> None:
        # All to claude => max inequality possible for 2 agents
        trace = _trace(
            routing_decisions=[
                _decision("t01", "claude"),
                _decision("t02", "claude"),
                _decision("t03", "claude"),
                _decision("t04", "claude"),
            ]
        )
        det = SuperflocksDetector(_Stub([_payload()]))
        metrics = det._compute_metrics(trace)
        # 2-agent ceiling on gini is 0.5
        assert metrics["routing_gini"] >= 0.4

    def test_complementarity_low_for_dominant(self) -> None:
        trace = _trace(
            routing_decisions=[
                _decision("t01", "claude"),
                _decision("t02", "claude"),
                _decision("t03", "claude"),
                _decision("t04", "gpt"),
            ]
        )
        det = SuperflocksDetector(_Stub([_payload()]))
        metrics = det._compute_metrics(trace)
        # 1 of 4 non-top => 0.25
        assert metrics["complementarity_utilization"] == 0.25

    def test_fallback_coverage_with_capabilities(self) -> None:
        # 2 task classes; class A has 2 qualified agents; class B has 1
        trace = _trace(
            agents=["a", "b", "c"],
            capabilities=[
                AgentCapability(agent_name="a", capability_scores={"x": 0.9, "y": 0.9}),
                AgentCapability(agent_name="b", capability_scores={"x": 0.7, "y": 0.2}),
                AgentCapability(agent_name="c", capability_scores={"x": 0.2, "y": 0.2}),
            ],
            routing_decisions=[
                _decision("t01", "a", task_class="x"),
                _decision("t02", "a", task_class="y"),
            ],
        )
        det = SuperflocksDetector(_Stub([_payload()]))
        metrics = det._compute_metrics(trace)
        # x has 2 agents at >=0.5; y has 1 => 1/2 = 0.5
        assert metrics["fallback_coverage"] == 0.5

    def test_failure_clustering(self) -> None:
        trace = _trace(
            routing_decisions=[
                _decision("t01", "claude", outcome="failure"),
                _decision("t02", "claude", outcome="failure"),
                _decision("t03", "claude", outcome="success"),
                _decision("t04", "gpt", outcome="success"),
            ]
        )
        det = SuperflocksDetector(_Stub([_payload()]))
        metrics = det._compute_metrics(trace)
        # Both failures on claude (top) => 1.0
        assert metrics["failure_clustering"] == 1.0


class TestDetectionPipeline:
    def test_concentrated_end_to_end(self) -> None:
        stub = _Stub([_payload(quality="concentrated")])
        det = SuperflocksDetector(stub, model="test-model")
        detection = det.run(_trace())

        assert len(stub.calls) == 1
        assert detection.fragility_quality in ("concentrated", "robust", "superflocks")
        assert detection.top_agent == "claude"
        assert len(detection.metrics) == 5

    def test_missing_metrics_filled(self) -> None:
        partial = json.dumps(
            {
                "metrics": [_metric("top_agent_share", 0.67, "medium")],
                "fragility_quality": "concentrated",
                "interventions": [],
            }
        )
        det = SuperflocksDetector(_Stub([partial]))
        detection = det.run(_trace())
        assert len(detection.metrics) == 5

    def test_llm_metric_value_overridden_by_local(self) -> None:
        # LLM reports value 0.99 for top_agent_share, but local computes 0.67
        bad_value = json.dumps(
            {
                "metrics": [
                    {
                        "name": "top_agent_share",
                        "value": 0.99,
                        "explanation": "x",
                        "severity": "high",
                    }
                ],
                "fragility_quality": "concentrated",
                "interventions": [],
            }
        )
        det = SuperflocksDetector(_Stub([bad_value]))
        detection = det.run(_trace())
        top_share_metric = next(m for m in detection.metrics if m.name == "top_agent_share")
        # 2 of 3 to claude => 0.67
        assert top_share_metric.value == 0.67


class TestFragilityQualityThresholds:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.0, "robust"),
            (0.2, "robust"),
            (0.35, "concentrated"),
            (0.5, "concentrated"),
            (0.65, "superflocks"),
            (0.9, "superflocks"),
        ],
    )
    def test_threshold(self, score: float, expected: str) -> None:
        det = SuperflocksDetector(_Stub([]))
        assert det._fragility_quality(score, "") == expected
