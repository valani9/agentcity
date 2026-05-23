"""Comprehensive v0.2.0 tests for the upgraded McGregor diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from agentcity.aar import InMemoryTelemetrySink, set_default_sink
from agentcity.mcgregor import (
    MCGREGOR_COMPOSITION,
    MCGREGOR_MODES,
    MCGREGOR_PROFILE_PATTERNS,
    MODES,
    PLAYBOOKS,
    SEVERITY_ORDER,
    BaselineComparison,
    McGregorOrchestratorAnalyzer,
    McGregorOrchestratorAnalyzerAsync,
    ModeIndicators,
    OrchestratorIntervention,
    OrchestratorModeDetection,
    OrchestratorModeDetector,
    OrchestratorStep,
    OrchestratorTrace,
    TaskProperties,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_mismatch,
)


def _step(
    content: str = "x", step_type: str = "delegate", actor: str = "orchestrator"
) -> OrchestratorStep:
    return OrchestratorStep(step_type=step_type, actor=actor, content=content)  # type: ignore[arg-type]


def _trace(
    *,
    task: str = "Run the test suite on every PR.",
    risk_level: str = "low",
    complexity: str = "routine",
    reversibility: str = "reversible",
    regulatory_exposure: bool = False,
    agent_capability: str = "proven",
    success: bool = True,
    framework: str | None = None,
) -> OrchestratorTrace:
    return OrchestratorTrace(
        trace_id="t",
        task=task,
        sub_agents=["runner-1"],
        task_properties=TaskProperties(
            risk_level=risk_level,  # type: ignore[arg-type]
            complexity=complexity,  # type: ignore[arg-type]
            reversibility=reversibility,  # type: ignore[arg-type]
            regulatory_exposure=regulatory_exposure,
            agent_capability=agent_capability,  # type: ignore[arg-type]
        ),
        steps=[_step()],
        outcome="Each test run required pre-approval; 5x slower than needed.",
        success=success,
        framework=framework,
    )


def _stub(canned: list[str]) -> object:
    from agentcity.aar import StubClient

    return StubClient(canned)


def _indicators_dict(
    check_in: float = 0.9, autonomy: float = 0.1, approvals: float = 0.9, intervention: float = 0.5
) -> dict[str, object]:
    return {
        "check_in_frequency": check_in,
        "autonomy_granted": autonomy,
        "pre_approval_required": approvals,
        "intervention_rate": intervention,
        "explanation": "x",
        "evidence_quotes": [],
        "confidence": 0.7,
    }


def _standard_payload(
    observed: str = "theory_x",
    optimal: str = "theory_y",
    mismatch: float = 0.7,
    quality: str = "severe-mismatch",
) -> str:
    return json.dumps(
        {
            "observed_mode": observed,
            "optimal_mode": optimal,
            "mode_mismatch": mismatch,
            "indicators": _indicators_dict(),
            "mode_quality": quality,
            "rationale": "Theory X on low-risk proven-agent waste.",
        }
    )


def _interventions_payload() -> str:
    return json.dumps(
        [
            {
                "target_mode": "theory_y",
                "intervention_type": "loosen_oversight",
                "description": "Remove approval gates for low-risk.",
                "suggested_implementation": "config change",
                "estimated_impact": "high",
                "rationale": "x",
                "effort_estimate": "1d",
                "risk": "low",
            }
        ]
    )


def _quick_payload() -> str:
    obj = json.loads(_standard_payload())
    obj["top_intervention"] = {
        "target_mode": "theory_y",
        "intervention_type": "loosen_oversight",
        "description": "x",
        "suggested_implementation": "y",
        "estimated_impact": "high",
        "rationale": "z",
    }
    return json.dumps(obj)


def _step_audit_payload() -> str:
    return json.dumps(
        [
            {
                "step_index": 0,
                "step_type": "delegate",
                "mode_signal": "theory_x",
                "was_appropriate": False,
                "suggested_alternative": "delegate without pre-approval",
                "explanation": "low-risk doesn't need this gate",
            }
        ]
    )


def _optimality_payload() -> str:
    return json.dumps(
        {
            "optimal_mode": "theory_y",
            "task_risk": "low-risk -> Theory Y appropriate",
            "task_complexity": "routine",
            "task_reversibility": "reversible",
            "agent_capability": "proven",
            "regulatory": "n/a",
            "final_rationale": "All four indicators point to Theory Y.",
        }
    )


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


class TestSchemaInvariants:
    def test_modes_three(self) -> None:
        assert set(MCGREGOR_MODES) == {"quick", "standard", "forensic"}

    def test_modes_taxonomy(self) -> None:
        assert set(MODES) == {"theory_x", "theory_y", "hybrid"}

    def test_profile_patterns_count(self) -> None:
        assert len(MCGREGOR_PROFILE_PATTERNS) == 12

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_severity_polarity(self) -> None:
        assert severity_from_mismatch(0.0) == "none"
        assert severity_from_mismatch(1.0) == "critical"
        # severe-mismatch floor
        assert severity_from_mismatch(0.1, "severe-mismatch") == "high"

    def test_legacy_alias_works(self) -> None:
        assert OrchestratorModeDetector is McGregorOrchestratorAnalyzer


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


class TestModes:
    def test_standard_two_calls(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = McGregorOrchestratorAnalyzer(stub, mode="standard").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "standard"
        assert det.llm_calls == 2
        assert det.observed_mode == "theory_x"
        assert det.optimal_mode == "theory_y"

    def test_quick_one_call(self) -> None:
        stub = _stub([_quick_payload()])
        det = McGregorOrchestratorAnalyzer(stub, mode="quick").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "quick"
        assert det.llm_calls == 1
        assert len(det.interventions) == 1

    def test_forensic_four_calls(self) -> None:
        stub = _stub(
            [
                _standard_payload(),
                _step_audit_payload(),
                _optimality_payload(),
                _interventions_payload(),
            ]
        )
        det = McGregorOrchestratorAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "forensic"
        assert det.llm_calls == 4
        assert len(det.step_audits) == 1
        assert det.optimality_justification is not None

    def test_well_matched_skips_interventions(self) -> None:
        payload = _standard_payload(
            observed="theory_y",
            optimal="theory_y",
            mismatch=0.0,
            quality="well-matched",
        )
        stub = _stub([payload])
        det = McGregorOrchestratorAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.llm_calls == 1
        assert det.interventions == []


# ---------------------------------------------------------------------------
# Profile classifier
# ---------------------------------------------------------------------------


class TestProfilePattern:
    def test_theory_x_on_low_risk(self) -> None:
        # task is low-risk, proven agent => theory_x_on_proven_agent (more specific)
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = McGregorOrchestratorAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "theory_x_on_proven_agent"

    def test_theory_y_on_high_risk(self) -> None:
        payload = _standard_payload(observed="theory_y", optimal="theory_x", mismatch=0.7)
        stub = _stub([payload, _interventions_payload()])
        det = McGregorOrchestratorAnalyzer(stub).run(  # type: ignore[arg-type]
            _trace(risk_level="high", reversibility="reversible")
        )
        assert det.profile_pattern == "theory_y_on_high_risk"

    def test_irreversible_under_theory_y(self) -> None:
        # Overrides any other classification.
        payload = _standard_payload(observed="theory_y", optimal="theory_x", mismatch=0.8)
        stub = _stub([payload, _interventions_payload()])
        det = McGregorOrchestratorAnalyzer(stub).run(  # type: ignore[arg-type]
            _trace(risk_level="high", reversibility="irreversible")
        )
        assert det.profile_pattern == "irreversible_action_under_supervision"

    def test_regulated_workflow_under_supervision(self) -> None:
        payload = _standard_payload(observed="theory_y", optimal="theory_x")
        stub = _stub([payload, _interventions_payload()])
        det = McGregorOrchestratorAnalyzer(stub).run(  # type: ignore[arg-type]
            _trace(regulatory_exposure=True, risk_level="medium", reversibility="reversible")
        )
        assert det.profile_pattern == "regulated_workflow_under_supervision"

    def test_well_matched_theory_y(self) -> None:
        payload = _standard_payload(
            observed="theory_y",
            optimal="theory_y",
            mismatch=0.0,
            quality="well-matched",
        )
        stub = _stub([payload])
        det = McGregorOrchestratorAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "well_matched_theory_y"


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


class TestTelemetry:
    def teardown_method(self) -> None:
        set_default_sink(None)

    def test_records_per_call(self) -> None:
        sink = InMemoryTelemetrySink()
        set_default_sink(sink)
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = McGregorOrchestratorAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert len(sink.events) == det.llm_calls == 2
        for ev in sink.events:
            assert ev.pattern == "mcgregor"
            assert ev.run_id == det.run_id


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(MCGREGOR_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "theory_x_on_proven_agent" in keys
        assert "irreversible_action_under_supervision" in keys

    def test_theory_x_proven_recommends_sdt(self) -> None:
        det = OrchestratorModeDetection(
            observed_mode="theory_x",
            optimal_mode="theory_y",
            mode_mismatch=0.6,
            indicators=ModeIndicators(
                check_in_frequency=0.9,
                autonomy_granted=0.1,
                pre_approval_required=0.9,
                intervention_rate=0.5,
                explanation="x",
                evidence_quotes=[],
            ),
            mode_quality="severe-mismatch",
            rationale="x",
            interventions=[],
            profile_pattern="theory_x_on_proven_agent",
        )
        recs, _ = recommended_downstream(det)
        assert "agentcity.sdt_reward" in recs

    def test_upstream_includes_lewin(self) -> None:
        up = recommended_upstream()
        assert "agentcity.lewin" in up


# ---------------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------------


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("theory_x", "low_risk_oversupervision") in keys
        assert ("theory_y", "high_risk_undersupervision") in keys
        assert ("theory_y", "irreversible_action_under_supervision") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("theory_x", "loosen_oversight")
        assert pb is not None
        assert pb.failure_mode == "low_risk_oversupervision"


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


class TestCalibration:
    def _det(self) -> OrchestratorModeDetection:
        return OrchestratorModeDetection(
            observed_mode="theory_x",
            optimal_mode="theory_y",
            mode_mismatch=0.6,
            indicators=ModeIndicators(
                check_in_frequency=0.9,
                autonomy_granted=0.1,
                pre_approval_required=0.9,
                intervention_rate=0.5,
                explanation="x",
                evidence_quotes=[],
            ),
            mode_quality="severe-mismatch",
            rationale="x",
            interventions=[],
            run_id="r-1",
        )

    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        det = self._det()
        path = tmp_path / "baseline.json"
        record_baseline(det, path)
        restored = load_baseline(path)
        assert restored.observed_mode == "theory_x"

    def test_drift_returns_comparison(self) -> None:
        det = self._det()
        cmp = compare_to_baseline(det, det)
        assert isinstance(cmp, BaselineComparison)
        assert cmp.drift_severity == "none"


# ---------------------------------------------------------------------------
# Async mirror
# ---------------------------------------------------------------------------


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
        stub = _AsyncStub([_standard_payload(), _interventions_payload()])
        analyzer = McGregorOrchestratorAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> OrchestratorModeDetection:
            return await analyzer.arun(_trace())

        det = asyncio.run(call())
        assert det.mode == "standard"


# ---------------------------------------------------------------------------
# Markdown v2
# ---------------------------------------------------------------------------


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = McGregorOrchestratorAnalyzer(stub).run(_trace(framework="crewai"))  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "McGregor" in md
        assert "Mode:" in md
        assert "Profile pattern:" in md
        assert "Composition Handoff" in md

    def test_forensic_renders_optimality_and_audit(self) -> None:
        stub = _stub(
            [
                _standard_payload(),
                _step_audit_payload(),
                _optimality_payload(),
                _interventions_payload(),
            ]
        )
        det = McGregorOrchestratorAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "Optimality Justification" in md
        assert "Step-by-Step Audit" in md


# Silence ruff
_ = OrchestratorIntervention
