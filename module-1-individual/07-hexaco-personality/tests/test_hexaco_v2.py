"""Comprehensive v0.2.0 tests for the upgraded HEXACO diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from vstack.aar import InMemoryTelemetrySink, set_default_sink
from vstack.hexaco import (
    HEXACO_COMPOSITION,
    HEXACO_FACTORS,
    HEXACO_MODES,
    HEXACO_PROFILE_PATTERNS,
    PLAYBOOKS,
    SEVERITY_ORDER,
    AgentPersonalityTrace,
    BaselineComparison,
    HEXACODetection,
    HEXACOPersonalityAnalyzer,
    HEXACOPersonalityAnalyzerAsync,
    HEXACOPersonalityDetector,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_fit,
)


def _trace(
    *,
    task: str = "Compile a 1-page summary on prompt injection defenses.",
    task_class: str = "high_stakes_advisor",
    outcome: str = "Summary contains 2 fabricated citations.",
    success: bool = False,
    observed_behaviors: list[str] | None = None,
    safety_relevant_events: list[str] | None = None,
    framework: str | None = None,
    deployment_authority_scope: str = "user_data_write",
) -> AgentPersonalityTrace:
    return AgentPersonalityTrace(
        agent_id="t",
        model_name="m",
        task=task,
        task_class=task_class,  # type: ignore[arg-type]
        system_prompt="You are a helpful research assistant.",
        observed_behaviors=observed_behaviors
        or ["Agent cited 3 unverified papers.", "Agent skipped fact-check."],
        safety_relevant_events=safety_relevant_events or ["Agent bypassed verification step."],
        outcome=outcome,
        success=success,
        framework=framework,
        deployment_authority_scope=deployment_authority_scope,  # type: ignore[arg-type]
    )


def _stub(canned: list[str]) -> object:
    from vstack.aar import StubClient

    return StubClient(canned)


def _f(
    name: str,
    score: float = 0.5,
    target: float = 0.5,
    fit: float = 1.0,
) -> dict[str, object]:
    return {
        "factor": name,
        "score": score,
        "target_score": target,
        "fit_score": fit,
        "explanation": f"{name} explanation",
        "evidence_quotes": [],
        "confidence": 0.7,
    }


def _profile_payload(
    h: float = 0.3,
    e: float = 0.5,
    x: float = 0.5,
    a: float = 0.7,
    c: float = 0.3,
    o: float = 0.5,
    h_target: float = 0.85,
    c_target: float = 0.85,
    h_risk: str = "high",
    weakest: str = "honesty_humility",
    fit_quality: str = "developing",
    overall_fit: float = 0.55,
) -> str:
    return json.dumps(
        {
            "factors": [
                _f("honesty_humility", h, h_target, fit=1.0 - abs(h - h_target)),
                _f("emotionality", e, 0.5, fit=1.0 - abs(e - 0.5)),
                _f("extraversion", x, 0.5, fit=1.0 - abs(x - 0.5)),
                _f("agreeableness", a, 0.5, fit=1.0 - abs(a - 0.5)),
                _f("conscientiousness", c, c_target, fit=1.0 - abs(c - c_target)),
                _f("openness", o, 0.5, fit=1.0 - abs(o - 0.5)),
            ],
            "overall_fit": overall_fit,
            "h_factor_risk": h_risk,
            "fit_quality": fit_quality,
            "weakest_factor": weakest,
        }
    )


def _interventions_payload() -> str:
    return json.dumps(
        [
            {
                "target_factor": "honesty_humility",
                "direction": "increase",
                "intervention_type": "add_h_factor_guardrail",
                "description": "Add anti-deception rule.",
                "suggested_implementation": "Edit system prompt.",
                "estimated_impact": "high",
                "rationale": "low-H signal",
                "effort_estimate": "1d",
                "risk": "low",
            }
        ]
    )


def _quick_payload() -> str:
    obj = json.loads(_profile_payload())
    obj["top_intervention"] = {
        "target_factor": "honesty_humility",
        "direction": "increase",
        "intervention_type": "add_h_factor_guardrail",
        "description": "Add anti-deception rule.",
        "suggested_implementation": "Edit system prompt.",
        "estimated_impact": "high",
        "rationale": "low-H signal",
    }
    return json.dumps(obj)


def _facets_payload() -> str:
    facets = []
    parents = {
        "honesty_humility": ("sincerity", "fairness", "greed_avoidance", "modesty"),
        "emotionality": ("fearfulness", "anxiety", "dependence", "sentimentality"),
        "extraversion": (
            "social_self_esteem",
            "social_boldness",
            "sociability",
            "liveliness",
        ),
        "agreeableness": ("forgiveness", "gentleness", "flexibility", "patience"),
        "conscientiousness": (
            "organization",
            "diligence",
            "perfectionism",
            "prudence",
        ),
        "openness": (
            "aesthetic_appreciation",
            "inquisitiveness",
            "creativity",
            "unconventionality",
        ),
    }
    for parent, fs in parents.items():
        for f in fs:
            facets.append(
                {
                    "facet": f,
                    "parent_factor": parent,
                    "score": 0.5,
                    "target_score": 0.5,
                    "fit_score": 1.0,
                    "explanation": "x",
                }
            )
    return json.dumps(facets)


def _safety_audit_payload() -> str:
    return json.dumps(
        [
            {
                "event": "Agent bypassed verification step.",
                "facet_attribution": ["sincerity", "fairness"],
                "direction": "low_h_signal",
                "severity": "high",
                "notes": "x",
            }
        ]
    )


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


class TestSchemaInvariants:
    def test_modes_three(self) -> None:
        assert set(HEXACO_MODES) == {"quick", "standard", "forensic"}

    def test_profile_patterns_count(self) -> None:
        assert len(HEXACO_PROFILE_PATTERNS) == 13

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_six_factors(self) -> None:
        assert len(HEXACO_FACTORS) == 6

    def test_severity_polarity(self) -> None:
        assert severity_from_fit(1.0) == "none"
        assert severity_from_fit(0.0) == "critical"
        # H-risk floor
        assert severity_from_fit(0.95, "high") == "high"

    def test_legacy_alias_works(self) -> None:
        assert HEXACOPersonalityDetector is HEXACOPersonalityAnalyzer


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


class TestModes:
    def test_standard_two_calls(self) -> None:
        stub = _stub([_profile_payload(), _interventions_payload()])
        det = HEXACOPersonalityAnalyzer(stub, mode="standard").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "standard"
        assert det.llm_calls == 2
        assert det.h_factor_risk == "high"

    def test_quick_one_call(self) -> None:
        stub = _stub([_quick_payload()])
        det = HEXACOPersonalityAnalyzer(stub, mode="quick").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "quick"
        assert det.llm_calls == 1
        assert len(det.interventions) == 1

    def test_forensic_four_calls(self) -> None:
        stub = _stub(
            [
                _profile_payload(),
                _facets_payload(),
                _safety_audit_payload(),
                _interventions_payload(),
            ]
        )
        det = HEXACOPersonalityAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "forensic"
        assert det.llm_calls == 4
        assert len(det.facet_scores) == 24
        assert len(det.safety_event_audit) == 1

    def test_well_fit_skips_interventions(self) -> None:
        payload = _profile_payload(
            h=0.85,
            c=0.85,
            h_risk="low",
            fit_quality="well-fit",
            overall_fit=0.9,
            weakest="none",
        )
        stub = _stub([payload])
        det = HEXACOPersonalityAnalyzer(stub).run(_trace(success=True))  # type: ignore[arg-type]
        assert det.llm_calls == 1
        assert det.interventions == []


# ---------------------------------------------------------------------------
# Profile classifier
# ---------------------------------------------------------------------------


class TestProfilePattern:
    def test_h_factor_dominant_risk(self) -> None:
        stub = _stub([_profile_payload(h=0.2, c=0.5, a=0.5), _interventions_payload()])
        det = HEXACOPersonalityAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        # Should hit either dark_triad or h_factor_dominant. Either is acceptable
        # depending on c value; with c=0.5 we should NOT trigger dark_triad.
        assert det.profile_pattern in ("h_factor_dominant_risk", "h_factor_with_high_a")

    def test_helpful_but_unsafe(self) -> None:
        # Low H + high A => h_factor_with_high_a
        stub = _stub([_profile_payload(h=0.3, a=0.8, c=0.7), _interventions_payload()])
        det = HEXACOPersonalityAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "h_factor_with_high_a"

    def test_dark_triad(self) -> None:
        # Low H + low C + low A
        stub = _stub([_profile_payload(h=0.2, c=0.3, a=0.3), _interventions_payload()])
        det = HEXACOPersonalityAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "low_h_low_c_low_a_dark_triad"

    def test_code_review_misfit(self) -> None:
        stub = _stub(
            [
                _profile_payload(h=0.7, c=0.4, a=0.5, h_risk="low"),
                _interventions_payload(),
            ]
        )
        det = HEXACOPersonalityAnalyzer(stub).run(_trace(task_class="code_review"))  # type: ignore[arg-type]
        assert det.profile_pattern == "low_c_code_review_misfit"

    def test_well_fit_balanced(self) -> None:
        payload = _profile_payload(
            h=0.85,
            c=0.85,
            h_risk="low",
            fit_quality="well-fit",
            overall_fit=0.9,
            weakest="none",
        )
        stub = _stub([payload])
        det = HEXACOPersonalityAnalyzer(stub).run(_trace(success=True))  # type: ignore[arg-type]
        assert det.profile_pattern == "well_fit_balanced"


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


class TestTelemetry:
    def teardown_method(self) -> None:
        set_default_sink(None)

    def test_records_per_call(self) -> None:
        sink = InMemoryTelemetrySink()
        set_default_sink(sink)
        stub = _stub([_profile_payload(), _interventions_payload()])
        det = HEXACOPersonalityAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert len(sink.events) == det.llm_calls == 2
        for ev in sink.events:
            assert ev.pattern == "hexaco"
            assert ev.run_id == det.run_id


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(HEXACO_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "h_factor_with_high_a" in keys
        assert "low_h_low_c_low_a_dark_triad" in keys

    def test_h_risk_recommends_devils_advocate(self) -> None:
        det = HEXACODetection(
            task_class="high_stakes_advisor",
            factors=[],
            overall_fit=0.5,
            h_factor_risk="high",
            fit_quality="developing",
            weakest_factor="honesty_humility",
            interventions=[],
            profile_pattern="h_factor_dominant_risk",
        )
        recs, _ = recommended_downstream(det)
        assert "vstack.devils_advocate" in recs

    def test_upstream_includes_lewin(self) -> None:
        up = recommended_upstream()
        assert "vstack.lewin" in up


# ---------------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------------


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("honesty_humility", "manipulation_signal") in keys
        assert ("conscientiousness", "code_review_misses") in keys
        assert ("honesty_humility", "dark_triad_pattern") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("honesty_humility", "add_h_factor_guardrail")
        assert pb is not None
        assert pb.failure_mode == "manipulation_signal"


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


class TestCalibration:
    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        det = HEXACODetection(
            task_class="high_stakes_advisor",
            factors=[],
            overall_fit=0.7,
            h_factor_risk="elevated",
            fit_quality="developing",
            weakest_factor="honesty_humility",
            interventions=[],
            run_id="r-1",
        )
        path = tmp_path / "baseline.json"
        record_baseline(det, path)
        restored = load_baseline(path)
        assert restored.h_factor_risk == "elevated"

    def test_drift_returns_comparison(self) -> None:
        det = HEXACODetection(
            task_class="high_stakes_advisor",
            factors=[],
            overall_fit=0.7,
            h_factor_risk="elevated",
            fit_quality="developing",
            weakest_factor="honesty_humility",
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
        stub = _AsyncStub([_profile_payload(), _interventions_payload()])
        analyzer = HEXACOPersonalityAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> HEXACODetection:
            return await analyzer.arun(_trace())

        det = asyncio.run(call())
        assert det.mode == "standard"


# ---------------------------------------------------------------------------
# Markdown v2
# ---------------------------------------------------------------------------


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        stub = _stub([_profile_payload(), _interventions_payload()])
        det = HEXACOPersonalityAnalyzer(stub).run(_trace(framework="crewai"))  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "HEXACO" in md
        assert "Mode:" in md
        assert "Profile pattern:" in md
        assert "Composition Handoff" in md

    def test_forensic_renders_facets(self) -> None:
        stub = _stub(
            [
                _profile_payload(),
                _facets_payload(),
                _safety_audit_payload(),
                _interventions_payload(),
            ]
        )
        det = HEXACOPersonalityAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "Facet Decomposition" in md
        assert "Safety Event Audit" in md
