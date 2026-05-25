"""v0.2.0 tests for the Heffernan Superflocks diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from vstack.aar import InMemoryTelemetrySink, set_default_sink
from vstack.superflocks import (
    PLAYBOOKS,
    SEVERITY_ORDER,
    SUPERFLOCKS_COMPOSITION,
    SUPERFLOCKS_MODES,
    SUPERFLOCKS_PROFILE_PATTERNS,
    AgentCapability,
    BaselineComparison,
    RoutingDecision,
    RoutingTrace,
    SuperflocksAnalyzer,
    SuperflocksAnalyzerAsync,
    SuperflocksDetection,
    SuperflocksDetector,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_fragility,
)


def _trace(top_share: float = 0.9, framework: str | None = None) -> RoutingTrace:
    # Build N decisions where most go to "alpha".
    n_total = 10
    n_top = int(top_share * n_total)
    decisions: list[RoutingDecision] = []
    for i in range(n_top):
        decisions.append(
            RoutingDecision(
                task_id=f"t{i}", task_class="general", routed_to="alpha", outcome="success"
            )
        )
    for i in range(n_total - n_top):
        decisions.append(
            RoutingDecision(
                task_id=f"t{n_top + i}", task_class="general", routed_to="beta", outcome="success"
            )
        )
    return RoutingTrace(
        trace_id="x",
        window_description="last 10 tasks",
        agents=["alpha", "beta"],
        capabilities=[
            AgentCapability(agent_name="alpha", capability_scores={"general": 0.9}),
            AgentCapability(agent_name="beta", capability_scores={"general": 0.8}),
        ],
        routing_decisions=decisions,
        outcome="completed window",
        success=True,
        framework=framework,
    )


def _stub(canned: list[str]) -> object:
    from vstack.aar import StubClient

    return StubClient(canned)


def _metrics_payload() -> str:
    return json.dumps(
        {
            "metrics": [
                {"name": "top_agent_share", "value": 0.9, "explanation": "x", "severity": "high"},
                {"name": "routing_gini", "value": 0.7, "explanation": "x", "severity": "high"},
                {
                    "name": "complementarity_utilization",
                    "value": 0.2,
                    "explanation": "x",
                    "severity": "high",
                },
                {"name": "fallback_coverage", "value": 0.1, "explanation": "x", "severity": "high"},
                {
                    "name": "failure_clustering",
                    "value": 0.5,
                    "explanation": "x",
                    "severity": "medium",
                },
            ]
        }
    )


def _interventions_payload() -> str:
    return json.dumps(
        [
            {
                "intervention_type": "introduce_routing_jitter",
                "description": "x",
                "suggested_implementation": "y",
                "estimated_impact": "high",
                "rationale": "z",
                "effort_estimate": "1d",
                "risk": "low",
            }
        ]
    )


def _quick_payload() -> str:
    obj = json.loads(_metrics_payload())
    obj["top_intervention"] = {
        "intervention_type": "introduce_routing_jitter",
        "description": "x",
        "suggested_implementation": "y",
        "estimated_impact": "high",
        "rationale": "z",
    }
    return json.dumps(obj)


def _capability_audit_payload() -> str:
    return json.dumps(
        {
            "wasted_capability_count": 2,
            "most_underutilized_agent": "beta",
            "capability_dimensions_underused": ["general"],
            "notes": "x",
        }
    )


def _failure_audit_payload() -> str:
    return json.dumps(
        {
            "top_agent_failure_share": 0.6,
            "fallback_used_on_failure": False,
            "cascade_risk": "high",
            "notes": "x",
        }
    )


class TestSchemaInvariants:
    def test_modes_three(self) -> None:
        assert set(SUPERFLOCKS_MODES) == {"quick", "standard", "forensic"}

    def test_profile_patterns_count(self) -> None:
        assert len(SUPERFLOCKS_PROFILE_PATTERNS) == 8

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_severity_polarity(self) -> None:
        assert severity_from_fragility(0.0) == "none"
        assert severity_from_fragility(1.0) == "critical"

    def test_legacy_alias(self) -> None:
        assert SuperflocksDetector is SuperflocksAnalyzer


class TestModes:
    def test_quick_one_call(self) -> None:
        stub = _stub([_quick_payload()])
        det = SuperflocksAnalyzer(stub, mode="quick").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "quick"
        assert det.llm_calls == 1

    def test_standard_one_call(self) -> None:
        # v0.0.x compat: standard mode is a single combined call.
        combined = json.loads(_metrics_payload())
        combined["interventions"] = json.loads(_interventions_payload())
        combined["fragility_quality"] = "superflocks"
        stub = _stub([json.dumps(combined)])
        det = SuperflocksAnalyzer(stub, mode="standard").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "standard"
        assert det.llm_calls == 1

    def test_forensic_four_calls(self) -> None:
        # forensic = combined + capability + failure + interventions = 4.
        combined = json.loads(_metrics_payload())
        combined["interventions"] = []
        combined["fragility_quality"] = "superflocks"
        stub = _stub(
            [
                json.dumps(combined),
                _capability_audit_payload(),
                _failure_audit_payload(),
                _interventions_payload(),
            ]
        )
        det = SuperflocksAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "forensic"
        assert det.llm_calls == 4
        assert det.capability_audit is not None
        assert det.failure_audit is not None


class TestDeterministicCompute:
    def test_top_agent(self) -> None:
        stub = _stub([_metrics_payload(), _interventions_payload()])
        det = SuperflocksAnalyzer(stub).run(_trace(top_share=0.9))  # type: ignore[arg-type]
        assert det.top_agent == "alpha"
        assert det.top_agent_share == 0.9

    def test_robust_when_balanced(self) -> None:
        stub = _stub([_metrics_payload()])
        det = SuperflocksAnalyzer(stub).run(_trace(top_share=0.5))  # type: ignore[arg-type]
        assert det.fragility_quality == "robust"
        assert det.interventions == []


class TestProfilePattern:
    def test_top_agent_monopoly(self) -> None:
        stub = _stub([_metrics_payload(), _interventions_payload()])
        det = SuperflocksAnalyzer(stub).run(_trace(top_share=0.9))  # type: ignore[arg-type]
        assert det.profile_pattern == "top_agent_monopoly"


class TestTelemetry:
    def teardown_method(self) -> None:
        set_default_sink(None)

    def test_records_per_call(self) -> None:
        sink = InMemoryTelemetrySink()
        set_default_sink(sink)
        combined = json.loads(_metrics_payload())
        combined["interventions"] = json.loads(_interventions_payload())
        combined["fragility_quality"] = "superflocks"
        stub = _stub([json.dumps(combined)])
        det = SuperflocksAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert len(sink.events) == det.llm_calls == 1
        for ev in sink.events:
            assert ev.pattern == "superflocks"
            assert ev.run_id == det.run_id


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(SUPERFLOCKS_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "robust_diversified" in keys
        assert "top_agent_monopoly" in keys

    def test_monopoly_recommends_bias_stack(self) -> None:
        det = SuperflocksDetection(
            top_agent="alpha",
            top_agent_share=0.9,
            routing_gini=0.8,
            fragility_score=0.85,
            fragility_quality="superflocks",
            metrics=[],
            interventions=[],
            profile_pattern="top_agent_monopoly",
        )
        recs, _ = recommended_downstream(det)
        assert "vstack.bias_stack" in recs

    def test_upstream_includes_grpi(self) -> None:
        up = recommended_upstream()
        assert "vstack.grpi" in up


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("superflocks", "top_agent_monopoly") in keys
        assert ("superflocks", "no_fallback") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("superflocks", "introduce_routing_jitter")
        assert pb is not None
        assert pb.failure_mode == "top_agent_monopoly"


class TestCalibration:
    def _det(self) -> SuperflocksDetection:
        return SuperflocksDetection(
            top_agent="alpha",
            top_agent_share=0.9,
            routing_gini=0.8,
            fragility_score=0.85,
            fragility_quality="superflocks",
            metrics=[],
            interventions=[],
            run_id="r-1",
        )

    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        det = self._det()
        path = tmp_path / "baseline.json"
        record_baseline(det, path)
        restored = load_baseline(path)
        assert restored.top_agent == "alpha"

    def test_drift_returns_comparison(self) -> None:
        det = self._det()
        cmp = compare_to_baseline(det, det)
        assert isinstance(cmp, BaselineComparison)
        assert cmp.drift_severity == "none"


class _AsyncStub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.last_usage = None

    async def complete(self, prompt: str, system: str | None = None) -> str:
        if not self._responses:
            raise RuntimeError("exhausted")
        return self._responses.pop(0)


class TestAsync:
    def test_arun_returns_detection(self) -> None:
        stub = _AsyncStub([_metrics_payload(), _interventions_payload()])
        analyzer = SuperflocksAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> SuperflocksDetection:
            return await analyzer.arun(_trace())

        det = asyncio.run(call())
        assert det.mode == "standard"


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        stub = _stub([_metrics_payload(), _interventions_payload()])
        det = SuperflocksAnalyzer(stub).run(_trace(framework="crewai"))  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "Superflocks" in md
        assert "Mode:" in md
        assert "Profile pattern:" in md
        assert "Composition Handoff" in md
