"""Comprehensive v0.2.0 tests for the upgraded Grant Strengths diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from vstack.aar import InMemoryTelemetrySink, set_default_sink
from vstack.grant_strengths import (
    GRANT_COMPOSITION,
    GRANT_MODES,
    GRANT_PROFILE_PATTERNS,
    PLAYBOOKS,
    SEVERITY_ORDER,
    STRENGTHS,
    AgentBehaviorStep,
    AgentBehaviorTrace,
    BaselineComparison,
    GrantStrengthsAnalyzer,
    GrantStrengthsAnalyzerAsync,
    StrengthOveruseDetection,
    StrengthsOveruseDetector,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_overuse,
)


def _step(content: str = "x", type_: str = "output") -> AgentBehaviorStep:
    return AgentBehaviorStep(type=type_, content=content)  # type: ignore[arg-type]


def _trace(
    *,
    task: str = "default task",
    steps: list[AgentBehaviorStep] | None = None,
    outcome: str = "default outcome",
    success: bool = False,
    harm_visible: bool = False,
    framework: str | None = None,
    task_class: str = "general",
) -> AgentBehaviorTrace:
    return AgentBehaviorTrace(
        agent_id="t",
        model_name="m",
        task=task,
        steps=steps or [_step()],
        outcome=outcome,
        success=success,
        harm_visible=harm_visible,
        framework=framework,
        task_class=task_class,  # type: ignore[arg-type]
    )


def _stub(canned: list[str]) -> object:
    from vstack.aar import StubClient

    return StubClient(canned)


def _s(
    name: str,
    overuse: float = 0.5,
    sev: str = "medium",
    pos: str = "borderline",
) -> dict[str, object]:
    return {
        "strength": name,
        "overuse_score": overuse,
        "severity": sev,
        "explanation": "x",
        "evidence_quotes": [],
        "confidence": 0.7,
        "inverted_u_position": pos,
        "under_use_score": 0.0,
    }


def _standard_payload(
    dominant: str = "helpfulness",
    quality: str = "overused",
    harm: str = "high",
    helpfulness_score: float = 0.95,
) -> str:
    return json.dumps(
        {
            "strengths": [
                _s("helpfulness", helpfulness_score, "high", "overused"),
                _s("agreeableness", 0.3, "low"),
                _s("thoroughness", 0.0, "none", "healthy"),
                _s("caution", 0.0, "none", "healthy"),
                _s("confidence", 0.0, "none", "healthy"),
                _s("brevity", 0.0, "none", "healthy"),
                _s("precision", 0.0, "none", "healthy"),
            ],
            "dominant_overuse": dominant,
            "harm_caused": harm,
            "overuse_quality": quality,
        }
    )


def _interventions_payload() -> str:
    return json.dumps(
        [
            {
                "target_strength": "helpfulness",
                "intervention_type": "add_destructive_action_gate",
                "description": "Gate destructive ops.",
                "suggested_implementation": "Add approval step.",
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
        "target_strength": "helpfulness",
        "intervention_type": "add_destructive_action_gate",
        "description": "x",
        "suggested_implementation": "y",
        "estimated_impact": "high",
        "rationale": "z",
    }
    return json.dumps(obj)


def _paired_audit_payload() -> str:
    return json.dumps(
        [
            {
                "primary_strength": "helpfulness",
                "complement_strength": "caution",
                "primary_position": "overused",
                "complement_position": "under_used",
                "imbalance_score": 0.7,
                "explanation": "x",
            }
        ]
    )


def _harm_causation_payload() -> str:
    return json.dumps(
        [
            {
                "step_index": 0,
                "strength": "helpfulness",
                "action_type": "destructive_action",
                "observed_consequence": "data loss",
                "severity": "critical",
            }
        ]
    )


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


class TestSchemaInvariants:
    def test_modes_three(self) -> None:
        assert set(GRANT_MODES) == {"quick", "standard", "forensic"}

    def test_profile_patterns_count(self) -> None:
        assert len(GRANT_PROFILE_PATTERNS) == 13

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_seven_strengths(self) -> None:
        assert len(STRENGTHS) == 7

    def test_severity_polarity(self) -> None:
        assert severity_from_overuse(0.0) == "none"
        assert severity_from_overuse(1.0) == "critical"
        # Harm floor
        assert severity_from_overuse(0.1, "high") == "high"

    def test_legacy_alias_works(self) -> None:
        assert StrengthsOveruseDetector is GrantStrengthsAnalyzer


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


class TestModes:
    def test_standard_two_calls(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = GrantStrengthsAnalyzer(stub, mode="standard").run(_trace(harm_visible=True))  # type: ignore[arg-type]
        assert det.mode == "standard"
        assert det.llm_calls == 2
        assert det.dominant_overuse == "helpfulness"

    def test_quick_one_call(self) -> None:
        stub = _stub([_quick_payload()])
        det = GrantStrengthsAnalyzer(stub, mode="quick").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "quick"
        assert det.llm_calls == 1
        assert len(det.interventions) == 1

    def test_forensic_four_calls(self) -> None:
        stub = _stub(
            [
                _standard_payload(),
                _paired_audit_payload(),
                _harm_causation_payload(),
                _interventions_payload(),
            ]
        )
        det = GrantStrengthsAnalyzer(stub, mode="forensic").run(_trace(harm_visible=True))  # type: ignore[arg-type]
        assert det.mode == "forensic"
        assert det.llm_calls == 4
        assert len(det.paired_audits) == 1
        assert len(det.harm_causation_chain) == 1

    def test_healthy_skips_interventions(self) -> None:
        payload = _standard_payload(
            dominant="none-observed",
            quality="healthy",
            harm="none",
            helpfulness_score=0.1,
        )
        stub = _stub([payload])
        det = GrantStrengthsAnalyzer(stub).run(_trace(success=True))  # type: ignore[arg-type]
        assert det.llm_calls == 1
        assert det.interventions == []


# ---------------------------------------------------------------------------
# Profile classifier
# ---------------------------------------------------------------------------


class TestProfilePattern:
    def test_helpfulness_destructive(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = GrantStrengthsAnalyzer(stub).run(_trace(harm_visible=True))  # type: ignore[arg-type]
        # With harm=high + dominant, harm_realized fires before per-dominant.
        assert det.profile_pattern == "harm_realized_dominant_overuse"

    def test_dominant_when_no_harm(self) -> None:
        payload = _standard_payload(harm="low", helpfulness_score=0.8)
        stub = _stub([payload, _interventions_payload()])
        det = GrantStrengthsAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "helpfulness_overuse_destructive_action"

    def test_multi_overuse_compounded(self) -> None:
        obj = json.loads(_standard_payload(helpfulness_score=0.8))
        obj["strengths"][1] = _s("agreeableness", 0.75, "high", "overused")
        obj["dominant_overuse"] = "helpfulness"
        obj["harm_caused"] = "low"
        payload = json.dumps(obj)
        stub = _stub([payload, _interventions_payload()])
        det = GrantStrengthsAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "multi_overuse_compounded"

    def test_healthy_balanced(self) -> None:
        payload = _standard_payload(
            dominant="none-observed",
            quality="healthy",
            harm="none",
            helpfulness_score=0.1,
        )
        stub = _stub([payload])
        det = GrantStrengthsAnalyzer(stub).run(_trace(success=True))  # type: ignore[arg-type]
        assert det.profile_pattern == "healthy_balanced"


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
        det = GrantStrengthsAnalyzer(stub).run(_trace(harm_visible=True))  # type: ignore[arg-type]
        assert len(sink.events) == det.llm_calls == 2
        for ev in sink.events:
            assert ev.pattern == "grant_strengths"
            assert ev.run_id == det.run_id


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(GRANT_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "helpfulness_overuse_destructive_action" in keys
        assert "agreeableness_overuse_sycophancy" in keys

    def test_helpfulness_recommends_devils_advocate(self) -> None:
        det = StrengthOveruseDetection(
            dominant_overuse="helpfulness",
            strength_scores={},
            strengths=[],
            harm_caused="high",
            overuse_quality="overused",
            interventions=[],
            profile_pattern="helpfulness_overuse_destructive_action",
        )
        recs, _ = recommended_downstream(det)
        assert "vstack.devils_advocate" in recs

    def test_upstream_includes_hexaco(self) -> None:
        up = recommended_upstream()
        assert "vstack.hexaco" in up
        assert "vstack.lewin" in up


# ---------------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------------


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("helpfulness", "destructive_action") in keys
        assert ("agreeableness", "sycophancy") in keys
        assert ("confidence", "under_hedging") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("helpfulness", "add_destructive_action_gate")
        assert pb is not None
        assert pb.failure_mode == "destructive_action"


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


class TestCalibration:
    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        det = StrengthOveruseDetection(
            dominant_overuse="helpfulness",
            strength_scores={"helpfulness": 0.8},
            strengths=[],
            harm_caused="high",
            overuse_quality="overused",
            interventions=[],
            run_id="r-1",
        )
        path = tmp_path / "baseline.json"
        record_baseline(det, path)
        restored = load_baseline(path)
        assert restored.dominant_overuse == "helpfulness"

    def test_drift_returns_comparison(self) -> None:
        det = StrengthOveruseDetection(
            dominant_overuse="helpfulness",
            strength_scores={"helpfulness": 0.8},
            strengths=[],
            harm_caused="high",
            overuse_quality="overused",
            interventions=[],
        )
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
        analyzer = GrantStrengthsAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> StrengthOveruseDetection:
            return await analyzer.arun(_trace(harm_visible=True))

        det = asyncio.run(call())
        assert det.mode == "standard"


# ---------------------------------------------------------------------------
# Markdown v2
# ---------------------------------------------------------------------------


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = GrantStrengthsAnalyzer(stub).run(  # type: ignore[arg-type]
            _trace(harm_visible=True, framework="crewai")
        )
        md = det.to_markdown()
        assert "Strengths-as-Weaknesses" in md
        assert "Mode:" in md
        assert "Profile pattern:" in md
        assert "Composition Handoff" in md

    def test_forensic_renders_paired_and_harm(self) -> None:
        stub = _stub(
            [
                _standard_payload(),
                _paired_audit_payload(),
                _harm_causation_payload(),
                _interventions_payload(),
            ]
        )
        det = GrantStrengthsAnalyzer(stub, mode="forensic").run(  # type: ignore[arg-type]
            _trace(harm_visible=True)
        )
        md = det.to_markdown()
        assert "Paired-Complement Audits" in md
        assert "Harm Causation Chain" in md
