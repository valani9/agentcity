"""Comprehensive v0.2.0 tests for the upgraded SDT Intrinsic Reward diagnostic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from agentcity.aar import InMemoryTelemetrySink, set_default_sink
from agentcity.sdt_reward import (
    PLAYBOOKS,
    SDT_COMPOSITION,
    SDT_MODES,
    SDT_NEEDS,
    SDT_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    AgentSDTTrace,
    BaselineComparison,
    SDTDetection,
    SDTRewardAnalyzer,
    SDTRewardAnalyzerAsync,
    SDTRewardDetector,
    all_playbook_keys,
    compare_to_baseline,
    find_playbook_for_intervention,
    load_baseline,
    record_baseline,
    recommended_downstream,
    recommended_upstream,
    severity_from_undermining,
)


def _trace(
    *,
    task: str = "Explore design space for new feature.",
    task_class: str = "research_exploration",
    outcome: str = "Output is rigid; no novel directions surfaced.",
    success: bool = False,
    system_prompt: str = "You MUST follow rules. You will be RATED on accuracy.",
    extrinsic_signals: list[str] | None = None,
    framework: str | None = None,
) -> AgentSDTTrace:
    return AgentSDTTrace(
        agent_id="t",
        model_name="m",
        task=task,
        task_class=task_class,  # type: ignore[arg-type]
        system_prompt=system_prompt,
        extrinsic_signals=extrinsic_signals or ["low ratings flagged", "cost cap < 5 calls"],
        observed_behaviors=[
            "Agent restated established patterns.",
            "Agent refused to deviate.",
        ],
        outcome=outcome,
        success=success,
        framework=framework,
    )


def _stub(canned: list[str]) -> object:
    from agentcity.aar import StubClient

    return StubClient(canned)


def _need(name: str, score: float = 0.3) -> dict[str, object]:
    return {
        "need": name,
        "score": score,
        "explanation": f"{name} ev",
        "evidence_quotes": [],
        "confidence": 0.7,
    }


def _standard_payload(
    autonomy: float = 0.2,
    competence: float = 0.6,
    relatedness: float = 0.5,
    intrinsic_score: float = 0.43,
    quality: str = "controlled",
    undermined: str = "autonomy",
) -> str:
    return json.dumps(
        {
            "need_evidence": [
                _need("autonomy", autonomy),
                _need("competence", competence),
                _need("relatedness", relatedness),
            ],
            "intrinsic_motivation_score": intrinsic_score,
            "motivation_quality": quality,
            "most_undermined_need": undermined,
        }
    )


def _interventions_payload() -> str:
    return json.dumps(
        [
            {
                "target_need": "autonomy",
                "intervention_type": "remove_external_reward_threat",
                "description": "Remove rating threats from prompt.",
                "suggested_implementation": "Edit system prompt.",
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
        "target_need": "autonomy",
        "intervention_type": "remove_external_reward_threat",
        "description": "x",
        "suggested_implementation": "y",
        "estimated_impact": "high",
        "rationale": "z",
    }
    return json.dumps(obj)


def _reward_shaping_payload() -> str:
    return json.dumps(
        [
            {
                "category": "rating_threat",
                "polarity": "extrinsic_controlling",
                "source_quote": "You will be RATED on accuracy",
                "affected_need": "autonomy",
                "explanation": "x",
            },
            {
                "category": "rule_imposition",
                "polarity": "extrinsic_controlling",
                "source_quote": "You MUST follow rules",
                "affected_need": "autonomy",
                "explanation": "x",
            },
            {
                "category": "cost_cap",
                "polarity": "extrinsic_controlling",
                "source_quote": "cost cap < 5 calls",
                "affected_need": "autonomy",
                "explanation": "x",
            },
        ]
    )


def _overjustification_payload() -> str:
    return json.dumps(
        {
            "is_active": True,
            "intrinsic_signal_count": 0,
            "extrinsic_signal_count": 3,
            "ratio": 1.0,
            "notes": "All signals extrinsic-controlling.",
        }
    )


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


class TestSchemaInvariants:
    def test_modes_three(self) -> None:
        assert set(SDT_MODES) == {"quick", "standard", "forensic"}

    def test_profile_patterns_count(self) -> None:
        assert len(SDT_PROFILE_PATTERNS) == 12

    def test_severity_seven(self) -> None:
        assert len(SEVERITY_ORDER) == 7

    def test_three_needs(self) -> None:
        assert len(SDT_NEEDS) == 3

    def test_severity_polarity(self) -> None:
        # Inverse polarity: high intrinsic = low severity.
        assert severity_from_undermining(1.0) == "none"
        assert severity_from_undermining(0.0) == "critical"
        # Quality floor
        assert severity_from_undermining(0.9, "controlled") == "medium"

    def test_legacy_alias_works(self) -> None:
        assert SDTRewardDetector is SDTRewardAnalyzer


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


class TestModes:
    def test_standard_two_calls(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = SDTRewardAnalyzer(stub, mode="standard").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "standard"
        assert det.llm_calls == 2
        assert det.most_undermined_need == "autonomy"

    def test_quick_one_call(self) -> None:
        stub = _stub([_quick_payload()])
        det = SDTRewardAnalyzer(stub, mode="quick").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "quick"
        assert det.llm_calls == 1
        assert len(det.interventions) == 1

    def test_forensic_four_calls(self) -> None:
        stub = _stub(
            [
                _standard_payload(),
                _reward_shaping_payload(),
                _overjustification_payload(),
                _interventions_payload(),
            ]
        )
        det = SDTRewardAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        assert det.mode == "forensic"
        assert det.llm_calls == 4
        assert len(det.reward_shaping_items) == 3
        assert det.overjustification_audit is not None
        assert det.overjustification_audit.is_active

    def test_intrinsic_skips_interventions(self) -> None:
        payload = _standard_payload(
            autonomy=0.85,
            competence=0.85,
            relatedness=0.85,
            intrinsic_score=0.85,
            quality="intrinsic",
            undermined="none",
        )
        stub = _stub([payload])
        det = SDTRewardAnalyzer(stub).run(_trace(success=True))  # type: ignore[arg-type]
        assert det.llm_calls == 1
        assert det.interventions == []


# ---------------------------------------------------------------------------
# Profile classifier
# ---------------------------------------------------------------------------


class TestProfilePattern:
    def test_autonomy_undermined(self) -> None:
        # Single need undermined + standard mode (no overjustification).
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = SDTRewardAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "autonomy_undermined_dominant"

    def test_overjustification_active(self) -> None:
        # Forensic mode -- overjustification overrides.
        stub = _stub(
            [
                _standard_payload(),
                _reward_shaping_payload(),
                _overjustification_payload(),
                _interventions_payload(),
            ]
        )
        det = SDTRewardAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "overjustification_active"

    def test_creative_task_low_autonomy(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = SDTRewardAnalyzer(stub).run(_trace(task_class="creative_generation"))  # type: ignore[arg-type]
        assert det.profile_pattern == "creative_task_low_autonomy_misfit"

    def test_multi_need_undermined(self) -> None:
        payload = _standard_payload(
            autonomy=0.2,
            competence=0.2,
            relatedness=0.3,
            intrinsic_score=0.23,
            quality="controlled",
            undermined="autonomy",
        )
        stub = _stub([payload, _interventions_payload()])
        det = SDTRewardAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert det.profile_pattern == "controlled_motivation_dominant"

    def test_intrinsic_balanced(self) -> None:
        payload = _standard_payload(
            autonomy=0.85,
            competence=0.85,
            relatedness=0.85,
            intrinsic_score=0.85,
            quality="intrinsic",
            undermined="none",
        )
        stub = _stub([payload])
        det = SDTRewardAnalyzer(stub).run(_trace(success=True))  # type: ignore[arg-type]
        assert det.profile_pattern == "intrinsic_balanced"


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
        det = SDTRewardAnalyzer(stub).run(_trace())  # type: ignore[arg-type]
        assert len(sink.events) == det.llm_calls == 2
        for ev in sink.events:
            assert ev.pattern == "sdt_reward"
            assert ev.run_id == det.run_id


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


class TestComposition:
    def test_manifest_has_keys(self) -> None:
        keys = set(SDT_COMPOSITION["downstream_by_profile_pattern"].keys())  # type: ignore[union-attr,index]
        assert "autonomy_undermined_dominant" in keys
        assert "overjustification_active" in keys

    def test_autonomy_recommends_schein_culture(self) -> None:
        det = SDTDetection(
            task_class="research_exploration",
            need_evidence=[],
            intrinsic_motivation_score=0.4,
            motivation_quality="controlled",
            most_undermined_need="autonomy",
            interventions=[],
            profile_pattern="autonomy_undermined_dominant",
        )
        recs, _ = recommended_downstream(det)
        assert "agentcity.schein_culture" in recs

    def test_upstream_includes_motivation_traps(self) -> None:
        up = recommended_upstream()
        assert "agentcity.motivation_traps" in up


# ---------------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------------


class TestPlaybooks:
    def test_playbook_count(self) -> None:
        assert len(PLAYBOOKS) >= 12

    def test_keys_present(self) -> None:
        keys = set(all_playbook_keys())
        assert ("autonomy", "rule_imposition") in keys
        assert ("competence", "scaffold_missing") in keys
        assert ("relatedness", "no_user_connection") in keys

    def test_find_playbook_for_intervention(self) -> None:
        pb = find_playbook_for_intervention("autonomy", "remove_external_reward_threat")
        assert pb is not None
        assert pb.failure_mode == "rating_threat"


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


class TestCalibration:
    def test_baseline_roundtrip(self, tmp_path: Path) -> None:
        det = SDTDetection(
            task_class="research_exploration",
            need_evidence=[],
            intrinsic_motivation_score=0.4,
            motivation_quality="controlled",
            most_undermined_need="autonomy",
            interventions=[],
            run_id="r-1",
        )
        path = tmp_path / "baseline.json"
        record_baseline(det, path)
        restored = load_baseline(path)
        assert restored.most_undermined_need == "autonomy"

    def test_drift_returns_comparison(self) -> None:
        det = SDTDetection(
            task_class="research_exploration",
            need_evidence=[],
            intrinsic_motivation_score=0.4,
            motivation_quality="controlled",
            most_undermined_need="autonomy",
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
        analyzer = SDTRewardAnalyzerAsync(stub, mode="standard")  # type: ignore[arg-type]

        async def call() -> SDTDetection:
            return await analyzer.arun(_trace())

        det = asyncio.run(call())
        assert det.mode == "standard"


# ---------------------------------------------------------------------------
# Markdown v2
# ---------------------------------------------------------------------------


class TestMarkdownV2:
    def test_renders_new_sections(self) -> None:
        stub = _stub([_standard_payload(), _interventions_payload()])
        det = SDTRewardAnalyzer(stub).run(_trace(framework="crewai"))  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "SDT" in md
        assert "Mode:" in md
        assert "Profile pattern:" in md
        assert "Composition Handoff" in md

    def test_forensic_renders_reward_and_overjustification(self) -> None:
        stub = _stub(
            [
                _standard_payload(),
                _reward_shaping_payload(),
                _overjustification_payload(),
                _interventions_payload(),
            ]
        )
        det = SDTRewardAnalyzer(stub, mode="forensic").run(_trace())  # type: ignore[arg-type]
        md = det.to_markdown()
        assert "Reward-Shaping Decomposition" in md
        assert "Overjustification Audit" in md
