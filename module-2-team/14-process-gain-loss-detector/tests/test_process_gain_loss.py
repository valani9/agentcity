"""Tests for the Process Gain/Loss Detector."""

from __future__ import annotations

import json

import pytest

from agentcity.process_gain_loss import (
    PROCESS_FACTORS,
    IndividualBaseline,
    ProcessFactorEvidence,
    ProcessGainLossDetection,
    ProcessGainLossDetector,
    ProcessIntervention,
    ProcessTrace,
    TeamResult,
)


def _baseline(name: str, quality: float = 0.7, cost: float | None = 1.0) -> IndividualBaseline:
    return IndividualBaseline(
        agent_name=name,
        output_summary="x",
        quality_score=quality,
        cost_units=cost,
    )


def _team(agents: list[str], quality: float = 0.5, cost: float | None = 3.0) -> TeamResult:
    return TeamResult(agents=agents, output_summary="x", quality_score=quality, cost_units=cost)


def _trace(**overrides: object) -> ProcessTrace:
    base: dict[str, object] = dict(
        trace_id="test",
        task="default task",
        individual_baselines=[_baseline("solo-a", 0.8), _baseline("solo-b", 0.7)],
        team_result=_team(["a", "b", "c"], quality=0.5, cost=3.0),
        interaction_log="some log",
        outcome="default outcome",
        success=True,
    )
    base.update(overrides)
    return ProcessTrace(**base)  # type: ignore[arg-type]


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self._responses.pop(0) if self._responses else ""


def _factor(name: str, score: float = 0.5, sev: str = "medium") -> dict[str, object]:
    return {
        "factor": name,
        "score": score,
        "severity": sev,
        "explanation": "test",
        "evidence_quotes": [],
    }


class TestSchemaRoundtrip:
    def test_trace_roundtrip(self) -> None:
        trace = _trace()
        restored = ProcessTrace.model_validate_json(trace.model_dump_json())
        assert restored.task == trace.task

    def test_detection_markdown_all_sections(self) -> None:
        detection = ProcessGainLossDetection(
            trace_id="t",
            process_quality="process-loss",
            gain_loss_score=-0.23,
            individual_best_quality=0.85,
            individual_best_agent="solo-claude",
            individual_mean_quality=0.81,
            team_quality=0.62,
            contributing_factors=[
                ProcessFactorEvidence(
                    factor="social_loafing",
                    score=0.7,
                    severity="high",
                    explanation="rubber-stamps from reviewer",
                    evidence_quotes=["reviewer: 'LGTM'"],
                )
            ],
            interventions=[
                ProcessIntervention(
                    target_factor="team_design",
                    intervention_type="use_single_best_agent",
                    description="use solo-claude",
                    suggested_implementation="route to solo",
                    estimated_impact="high",
                    rationale="cleaner result",
                )
            ],
            cost_overhead_ratio=5.2,
            generator_model="test-model",
            success=True,
        )
        md = detection.to_markdown()
        assert "Process Gain/Loss Detection" in md
        assert "PROCESS-LOSS" in md
        assert "-0.23" in md
        assert "Cost overhead vs best single: 5.20x" in md
        assert "Contributing Factors" in md
        assert "Recommended Interventions" in md


class TestValidation:
    def test_empty_task_rejected(self) -> None:
        det = ProcessGainLossDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="task"):
            det.run(_trace(task=""))

    def test_empty_outcome_rejected(self) -> None:
        det = ProcessGainLossDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="outcome"):
            det.run(_trace(outcome=""))

    def test_single_baseline_rejected(self) -> None:
        det = ProcessGainLossDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="at least 2 baselines"):
            det.run(_trace(individual_baselines=[_baseline("solo-a", 0.8)]))

    def test_empty_team_agents_rejected(self) -> None:
        det = ProcessGainLossDetector(_Stub(["[]", "[]"]))
        with pytest.raises(ValueError, match="team_result.agents"):
            det.run(_trace(team_result=_team([])))


class TestDetectionPipeline:
    def test_process_loss(self) -> None:
        factors = json.dumps(
            [_factor("social_loafing", 0.8, "high"), _factor("groupthink", 0.5, "medium")]
        )
        interventions = json.dumps(
            [
                {
                    "target_factor": "social_loafing",
                    "intervention_type": "explicit_critic",
                    "description": "add a real critic",
                    "suggested_implementation": "patch",
                    "estimated_impact": "high",
                    "rationale": "counters loafing",
                }
            ]
        )
        stub = _Stub([factors, interventions])
        det = ProcessGainLossDetector(stub, model="test-model")
        detection = det.run(_trace())

        # Loss case calls LLM twice
        assert len(stub.calls) == 2
        assert detection.process_quality == "process-loss"
        assert detection.gain_loss_score == pytest.approx(-0.30)
        assert detection.individual_best_agent == "solo-a"
        assert detection.individual_best_quality == 0.8
        assert len(detection.contributing_factors) == 6  # filled
        assert len(detection.interventions) == 1
        # Cost overhead: 3.0 / 1.0 = 3.0
        assert detection.cost_overhead_ratio == 3.0

    def test_process_gain_skips_llm(self) -> None:
        # Team quality (0.9) beats best baseline (0.8) by +0.10
        stub = _Stub([])  # no LLM responses needed
        det = ProcessGainLossDetector(stub, model="test-model")
        trace = _trace(team_result=_team(["a", "b"], quality=0.9, cost=2.0))
        detection = det.run(trace)

        # Process gain => zero LLM calls
        assert len(stub.calls) == 0
        assert detection.process_quality == "process-gain"
        assert detection.gain_loss_score == pytest.approx(0.10)
        assert detection.contributing_factors == []
        assert detection.interventions == []

    def test_neutral_within_threshold(self) -> None:
        # team 0.78 vs best 0.80 = -0.02, within +/-0.05 threshold
        factors = json.dumps([_factor("coordination_cost", 0.3, "low")])
        stub = _Stub([factors, "[]"])
        det = ProcessGainLossDetector(stub, model="test-model")
        trace = _trace(team_result=_team(["a", "b"], quality=0.78, cost=2.0))
        detection = det.run(trace)

        assert detection.process_quality == "neutral"
        assert -0.05 <= detection.gain_loss_score <= 0.05

    def test_missing_factors_filled(self) -> None:
        # Only return one factor; the rest should be filled with zero scores
        factors = json.dumps([_factor("groupthink", 0.6, "high")])
        det = ProcessGainLossDetector(_Stub([factors, "[]"]))
        detection = det.run(_trace())
        present = {f.factor for f in detection.contributing_factors}
        assert present == set(PROCESS_FACTORS)


class TestCostOverhead:
    def test_with_costs(self) -> None:
        det = ProcessGainLossDetector(_Stub(["[]", "[]"]))
        detection = det.run(_trace())
        assert detection.cost_overhead_ratio == 3.0

    def test_no_costs(self) -> None:
        det = ProcessGainLossDetector(_Stub(["[]", "[]"]))
        trace = _trace(
            individual_baselines=[
                _baseline("solo-a", 0.8, cost=None),
                _baseline("solo-b", 0.7, cost=None),
            ],
            team_result=_team(["a", "b"], quality=0.5, cost=None),
        )
        detection = det.run(trace)
        assert detection.cost_overhead_ratio is None


class TestQualityThresholds:
    @pytest.mark.parametrize(
        "gain_loss,expected",
        [
            (0.10, "process-gain"),
            (0.06, "process-gain"),
            (0.05, "neutral"),
            (0.0, "neutral"),
            (-0.05, "neutral"),
            (-0.06, "process-loss"),
            (-0.30, "process-loss"),
        ],
    )
    def test_threshold(self, gain_loss: float, expected: str) -> None:
        det = ProcessGainLossDetector(_Stub([]))
        assert det._process_quality(gain_loss) == expected
