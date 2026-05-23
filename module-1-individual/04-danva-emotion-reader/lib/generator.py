"""EmotionRecognitionAnalyzer: DANVA-style emotion-recognition accuracy
diagnostic for AI agents.

Three pipeline modes:

  - ``quick`` -- one LLM call (top-1 intervention). ~2s, ~$0.005.
  - ``standard`` -- one LLM call (2-4 ranked interventions; v0.0.x behavior).
    Skipped on high-accuracy. ~5s, ~$0.015.
  - ``forensic`` -- three+ LLM calls: dimensional overlay + cascade
    reconcile + ranked interventions with composition targets. ~15s, ~$0.05.

Full v0.1.0 production wiring: structured logging with run-id, token /
cost telemetry, input sanitization + fencing, async mirror.

Deterministic synthesis: per-emotion metrics, confusion matrix,
intensity curves, profile-pattern classifier, baseline drift,
composition handoff, playbook attachment.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Coroutine, Iterable, Iterator
from pathlib import Path
from statistics import correlation, mean, variance
from typing import Any, Literal, Protocol, cast

from agentcity.aar import (
    LLMUsage,
    detect_injection,
    extract_json_array,
    get_logger,
    new_run_id,
    record_llm_call,
    run_context,
    time_call,
    with_retry,
)

from ._calibration import compare_to_baseline, load_baseline
from ._composition import recommended_downstream, recommended_upstream
from ._playbooks import find_playbook_for_intervention
from .prompts import (
    DANVA_SYSTEM_PROMPT,
    FORENSIC_CASCADE_RECONCILE_PROMPT,
    FORENSIC_DIMENSIONAL_OVERLAY_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    assemble_prompt,
)
from .schema import (
    EMOTION_CATEGORIES,
    AgentEmotionTrace,
    AttachedPlaybook,
    CascadeAnalysis,
    CircumplexProjection,
    ComposedPatternHandoff,
    DANVAMode,
    DANVAProfilePattern,
    EmotionConfusionMatrix,
    EmotionIntervention,
    EmotionItem,
    EmotionMetric,
    EmotionRecognitionAnalysis,
    IntensityCurve,
    severity_from_accuracy,
)

log = get_logger("agentcity.danva_emotion.generator")


_DEFAULT_COST_PER_1K = {
    "input": 0.003,
    "output": 0.015,
}


class LLMClient(Protocol):
    """Single-method synchronous LLM client contract."""

    def complete(self, prompt: str, system: str | None = None) -> str: ...


class AsyncLLMClient(Protocol):
    """Single-method asynchronous LLM client contract."""

    async def complete(self, prompt: str, system: str | None = None) -> str: ...


# Emotion → (valence, arousal) on Russell's circumplex, normalized to [-1, 1].
_EMOTION_VAD: dict[str, tuple[float, float]] = {
    "happy": (0.85, 0.55),
    "sad": (-0.75, -0.40),
    "angry": (-0.65, 0.80),
    "fearful": (-0.60, 0.70),
    "disgust": (-0.65, 0.30),
    "surprise": (0.10, 0.85),
    "neutral": (0.0, 0.0),
    "uncertain": (0.0, 0.0),
}


def _quadrant(valence: float, arousal: float) -> str:
    if valence >= 0 and arousal >= 0:
        return "high-pos"
    if valence < 0 and arousal >= 0:
        return "high-neg"
    if valence >= 0 and arousal < 0:
        return "low-pos"
    return "low-neg"


class EmotionRecognitionAnalyzer:
    """Run the DANVA-style emotion-recognition diagnostic.

    Mode-aware. Construction-default mode can be overridden per-call.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: DANVAMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: DANVAMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def run(
        self,
        trace: AgentEmotionTrace,
        *,
        mode: DANVAMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> EmotionRecognitionAnalysis:
        active_mode: DANVAMode = mode or self.mode
        run_id = new_run_id()
        with run_context(run_id, pattern="danva_emotion"):
            return self._run_pipeline(trace, active_mode, run_id, baseline_path)

    def run_batch(
        self,
        traces: Iterable[AgentEmotionTrace],
        *,
        mode: DANVAMode | None = None,
    ) -> Iterator[EmotionRecognitionAnalysis]:
        active_mode: DANVAMode = mode or self.mode
        for trace in traces:
            run_id = new_run_id()
            with run_context(run_id, pattern="danva_emotion"):
                yield self._run_pipeline(trace, active_mode, run_id, None)

    # ------------------------------------------------------------------
    # Pipeline dispatch
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        trace: AgentEmotionTrace,
        mode: DANVAMode,
        run_id: str,
        baseline_path: str | Path | None,
    ) -> EmotionRecognitionAnalysis:
        self._validate_trace(trace)
        injection_detected = self._scan_injection(trace)

        started = time.monotonic()
        log.info(
            "Running DANVA analysis (mode=%s) for agent %s items=%d",
            mode,
            trace.agent_id or "<unknown>",
            len(trace.items),
        )

        acc = _PipelineAcc()

        # Deterministic synthesis (no LLM).
        metrics = self._compute_metrics(trace.items)
        overall_acc, overall_mae = self._compute_overall(trace.items)
        weakest = self._coerce_weakest(metrics)
        quality = self._accuracy_quality(overall_acc)
        confusion_matrix = self._build_confusion_matrix(trace.items)
        intensity_curves = self._build_intensity_curves(trace.items)
        circumplex = self._project_circumplex(trace.items)
        profile_pattern = self._classify_profile_pattern(metrics, trace.items, circumplex)

        # LLM passes per mode.
        cascade: CascadeAnalysis | None = None
        if mode == "quick":
            interventions = self._pass_quick(
                trace, metrics, overall_acc, overall_mae, weakest, quality, acc
            )
        elif mode == "standard":
            interventions = self._pass_standard(
                trace,
                metrics,
                overall_acc,
                overall_mae,
                weakest,
                quality,
                profile_pattern,
                acc,
            )
        elif mode == "forensic":
            # Forensic adds dimensional + cascade passes.
            forensic_circumplex = self._pass_dimensional_overlay(trace, acc)
            if forensic_circumplex is not None:
                circumplex = forensic_circumplex
            cascade = self._pass_cascade_reconcile(metrics, confusion_matrix, circumplex, acc)
            interventions = self._pass_forensic_interventions(
                trace,
                metrics,
                weakest,
                profile_pattern,
                cascade,
                acc,
            )
        else:  # pragma: no cover
            raise ValueError(f"unknown DANVAMode: {mode!r}")

        composition = (
            self._build_composition_handoff(trace, profile_pattern, weakest, interventions)
            if self.composition_enabled
            else None
        )
        playbooks = self._attach_playbooks(interventions) if self.playbooks_enabled else []

        baseline = None
        baseline_source = baseline_path or trace.baseline_path
        if baseline_source:
            try:
                bl = load_baseline(baseline_source)
                provisional = EmotionRecognitionAnalysis(
                    metrics=metrics,
                    overall_accuracy=overall_acc,
                    overall_intensity_mae=overall_mae,
                    weakest_emotion=weakest,
                    accuracy_quality=quality,
                    interventions=interventions,
                    n_items=len(trace.items),
                    mode=mode,
                    profile_pattern=profile_pattern,
                )
                baseline = compare_to_baseline(provisional, bl)
            except Exception as exc:  # pragma: no cover
                log.warning("Baseline comparison failed: %s", type(exc).__name__)

        severity = severity_from_accuracy(overall_acc)
        elapsed_ms = (time.monotonic() - started) * 1000.0

        analysis = EmotionRecognitionAnalysis(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            metrics=metrics,
            overall_accuracy=overall_acc,
            overall_intensity_mae=overall_mae,
            weakest_emotion=weakest,
            accuracy_quality=quality,
            interventions=interventions,
            generator_model=self.model,
            n_items=len(trace.items),
            mode=mode,
            severity=severity,
            profile_pattern=profile_pattern,
            confusion_matrix=confusion_matrix,
            intensity_curves=intensity_curves,
            circumplex_projection=circumplex,
            cascade_analysis=cascade,
            baseline=baseline,
            composition_handoff=composition,
            attached_playbooks=playbooks,
            run_id=run_id,
            cost_usd=acc.cost_usd,
            tokens_total=acc.tokens_total,
            tokens_input=acc.tokens_input,
            tokens_output=acc.tokens_output,
            llm_calls=acc.llm_calls,
            elapsed_ms=elapsed_ms,
            injection_detected=injection_detected,
        )

        log.info(
            "DANVA analysis done mode=%s accuracy=%.2f weakest=%s profile=%s elapsed=%.0fms",
            mode,
            overall_acc,
            weakest,
            profile_pattern,
            elapsed_ms,
        )
        return analysis

    # ------------------------------------------------------------------
    # Validation + scan
    # ------------------------------------------------------------------

    def _validate_trace(self, trace: AgentEmotionTrace) -> None:
        if not trace.items:
            raise ValueError("AgentEmotionTrace.items cannot be empty.")

    def _scan_injection(self, trace: AgentEmotionTrace) -> bool:
        hit_count = 0
        for i, item in enumerate(trace.items):
            hits = detect_injection(item.user_input)
            if hits:
                hit_count += 1
                log.warning(
                    "prompt-injection pattern detected in item",
                    extra={"item_id": item.item_id, "field": "user_input"},
                )
        if hit_count:
            log.warning("injection scan: %d item(s) flagged", hit_count)
        return hit_count > 0

    # ------------------------------------------------------------------
    # Deterministic metrics
    # ------------------------------------------------------------------

    def _compute_metrics(self, items: list[EmotionItem]) -> list[EmotionMetric]:
        by_truth: dict[str, list[EmotionItem]] = defaultdict(list)
        for it in items:
            by_truth[it.ground_truth_emotion].append(it)

        metrics: list[EmotionMetric] = []
        for emotion in EMOTION_CATEGORIES:
            bucket = by_truth.get(emotion, [])
            n = len(bucket)
            if n == 0:
                metrics.append(
                    EmotionMetric(
                        emotion=emotion,  # type: ignore[arg-type]
                        n_items=0,
                        accuracy=0.0,
                        intensity_mae=0.0,
                        confusion_with={},
                        severity="none",
                        intensity_bias=0.0,
                        intensity_correlation=0.0,
                    )
                )
                continue
            correct = sum(1 for it in bucket if it.agent_inferred_emotion == emotion)
            accuracy = correct / n
            mae = (
                sum(abs(it.agent_inferred_intensity - it.ground_truth_intensity) for it in bucket)
                / n
            )
            confusion: Counter[str] = Counter()
            for it in bucket:
                if it.agent_inferred_emotion != emotion:
                    confusion[it.agent_inferred_emotion] += 1
            # Intensity bias = mean(inferred) - mean(truth).
            bias = mean(it.agent_inferred_intensity for it in bucket) - mean(
                it.ground_truth_intensity for it in bucket
            )
            # Intensity correlation (Pearson) when n >= 2 and variance > 0.
            corr = 0.0
            if n >= 2:
                try:
                    corr = correlation(
                        [it.ground_truth_intensity for it in bucket],
                        [it.agent_inferred_intensity for it in bucket],
                    )
                except Exception:
                    corr = 0.0
            metrics.append(
                EmotionMetric(
                    emotion=emotion,  # type: ignore[arg-type]
                    n_items=n,
                    accuracy=round(accuracy, 4),
                    intensity_mae=round(mae, 4),
                    confusion_with=dict(confusion),
                    severity=severity_from_accuracy(accuracy),
                    intensity_bias=round(bias, 4),
                    intensity_correlation=round(corr, 4),
                )
            )
        return metrics

    def _compute_overall(self, items: list[EmotionItem]) -> tuple[float, float]:
        if not items:
            return 0.0, 0.0
        correct = sum(1 for it in items if it.agent_inferred_emotion == it.ground_truth_emotion)
        mae = sum(
            abs(it.agent_inferred_intensity - it.ground_truth_intensity) for it in items
        ) / len(items)
        return round(correct / len(items), 4), round(mae, 4)

    def _coerce_weakest(
        self, metrics: list[EmotionMetric]
    ) -> Literal["happy", "sad", "angry", "fearful", "disgust", "surprise", "neutral", "none"]:
        candidates = [m for m in metrics if m.n_items >= 2]
        if not candidates:
            return "none"
        bottom = min(candidates, key=lambda m: m.accuracy)
        if bottom.accuracy >= 0.8:
            return "none"
        return bottom.emotion

    def _accuracy_quality(
        self, overall_accuracy: float
    ) -> Literal["high-accuracy", "developing", "low-accuracy"]:
        if overall_accuracy >= 0.8:
            return "high-accuracy"
        if overall_accuracy >= 0.5:
            return "developing"
        return "low-accuracy"

    def _build_confusion_matrix(self, items: list[EmotionItem]) -> EmotionConfusionMatrix:
        matrix: dict[str, dict[str, int]] = {
            gt: {inf: 0 for inf in (*EMOTION_CATEGORIES, "uncertain")} for gt in EMOTION_CATEGORIES
        }
        row_totals: dict[str, int] = {gt: 0 for gt in EMOTION_CATEGORIES}
        column_totals: dict[str, int] = {inf: 0 for inf in (*EMOTION_CATEGORIES, "uncertain")}
        diagonal = 0
        for it in items:
            matrix[it.ground_truth_emotion][it.agent_inferred_emotion] += 1
            row_totals[it.ground_truth_emotion] += 1
            column_totals[it.agent_inferred_emotion] += 1
            if it.ground_truth_emotion == it.agent_inferred_emotion:
                diagonal += 1
        return EmotionConfusionMatrix(
            emotions_ground_truth=EMOTION_CATEGORIES,
            emotions_inferred=(*EMOTION_CATEGORIES, "uncertain"),
            matrix=matrix,
            row_totals=row_totals,
            column_totals=column_totals,
            diagonal_total=diagonal,
        )

    def _build_intensity_curves(self, items: list[EmotionItem]) -> list[IntensityCurve]:
        curves: list[IntensityCurve] = []
        for emotion in EMOTION_CATEGORIES:
            bucket = [it for it in items if it.ground_truth_emotion == emotion]
            n = len(bucket)
            if n == 0:
                curves.append(
                    IntensityCurve(
                        emotion=emotion,  # type: ignore[arg-type]
                        n_items=0,
                    )
                )
                continue
            truth_vals = [it.ground_truth_intensity for it in bucket]
            infer_vals = [it.agent_inferred_intensity for it in bucket]
            bias = mean(infer_vals) - mean(truth_vals) if n >= 1 else 0.0
            corr = 0.0
            collapse = 1.0
            if n >= 2:
                try:
                    corr = correlation(truth_vals, infer_vals)
                except Exception:
                    corr = 0.0
                tvar = variance(truth_vals)
                ivar = variance(infer_vals)
                collapse = (ivar / tvar) if tvar > 1e-9 else 1.0
            curves.append(
                IntensityCurve(
                    emotion=emotion,  # type: ignore[arg-type]
                    n_items=n,
                    truth_bins=[0.0, 0.25, 0.5, 0.75, 1.0],
                    mean_inferred_by_bin=[],
                    intensity_bias=round(bias, 4),
                    intensity_correlation=round(corr, 4),
                    intensity_collapse_score=round(collapse, 4),
                )
            )
        return curves

    def _project_circumplex(self, items: list[EmotionItem]) -> CircumplexProjection | None:
        if not items:
            return None
        truth_v = mean(
            _EMOTION_VAD[it.ground_truth_emotion][0] * it.ground_truth_intensity for it in items
        )
        truth_a = mean(
            _EMOTION_VAD[it.ground_truth_emotion][1] * it.ground_truth_intensity for it in items
        )
        infer_v = mean(
            _EMOTION_VAD[it.agent_inferred_emotion][0] * it.agent_inferred_intensity for it in items
        )
        infer_a = mean(
            _EMOTION_VAD[it.agent_inferred_emotion][1] * it.agent_inferred_intensity for it in items
        )
        dist = ((truth_v - infer_v) ** 2 + (truth_a - infer_a) ** 2) ** 0.5
        q_truth = _quadrant(truth_v, truth_a)
        q_inf = _quadrant(infer_v, infer_a)
        return CircumplexProjection(
            valence_truth=round(truth_v, 4),
            arousal_truth=round(truth_a, 4),
            valence_inferred=round(infer_v, 4),
            arousal_inferred=round(infer_a, 4),
            euclidean_distance=round(dist, 4),
            quadrant_truth=q_truth,  # type: ignore[arg-type]
            quadrant_inferred=q_inf,  # type: ignore[arg-type]
            quadrant_match=(q_truth == q_inf),
        )

    def _classify_profile_pattern(
        self,
        metrics: list[EmotionMetric],
        items: list[EmotionItem],
        circumplex: CircumplexProjection | None,
    ) -> DANVAProfilePattern:
        accs = {m.emotion: m.accuracy for m in metrics if m.n_items >= 1}
        n_items_total = len(items)
        if not accs:
            return "indeterminate"

        # Uncertain dump.
        n_uncertain = sum(1 for it in items if it.agent_inferred_emotion == "uncertain")
        if n_items_total > 0 and n_uncertain / n_items_total > 0.25:
            return "uncertain_dump"

        # Sarcasm-blind: false positives on sarcastic items.
        sarcastic = [it for it in items if it.cue_explicitness == "sarcastic"]
        if sarcastic:
            false_pos = sum(1 for it in sarcastic if it.agent_inferred_emotion == "happy")
            if false_pos / len(sarcastic) > 0.5:
                return "sarcasm_blind"

        # Anger blind (check before neutral_collapse -- more specific).
        angry_metric = next((m for m in metrics if m.emotion == "angry"), None)
        if angry_metric and angry_metric.n_items >= 2:
            if angry_metric.accuracy < 0.5:
                to_neutral_angry = angry_metric.confusion_with.get("neutral", 0)
                if to_neutral_angry / max(angry_metric.n_items, 1) > 0.5:
                    return "anger_blind"

        # Neutral collapse: many emotion items read as neutral.
        non_neutral = [it for it in items if it.ground_truth_emotion != "neutral"]
        if non_neutral:
            to_neutral = sum(1 for it in non_neutral if it.agent_inferred_emotion == "neutral")
            if to_neutral / len(non_neutral) > 0.4:
                return "neutral_collapse"

        # Sadness collapse.
        sad_metric = next((m for m in metrics if m.emotion == "sad"), None)
        if sad_metric and sad_metric.n_items >= 2:
            if sad_metric.accuracy >= 0.7 and sad_metric.intensity_bias <= -0.30:
                return "sadness_collapse"

        # Positive bias: neutral/sad misclassified as happy.
        neut_sad = [it for it in items if it.ground_truth_emotion in {"neutral", "sad"}]
        if neut_sad:
            as_happy = sum(1 for it in neut_sad if it.agent_inferred_emotion == "happy")
            if as_happy / len(neut_sad) > 0.3:
                return "positive_bias"

        # Fear-sadness confusion.
        fear_metric = next((m for m in metrics if m.emotion == "fearful"), None)
        if fear_metric and fear_metric.n_items >= 2:
            to_sad = fear_metric.confusion_with.get("sad", 0)
            if to_sad / max(fear_metric.n_items, 1) > 0.5:
                return "fear_sadness_confusion"

        # Valence-only signal: quadrant matches but category accuracy < 0.5.
        if circumplex and circumplex.quadrant_match:
            overall = sum(m.accuracy * m.n_items for m in metrics) / max(
                sum(m.n_items for m in metrics), 1
            )
            if overall < 0.5:
                return "valence_only_signal"

        # Categorical-only: category match high but intensity bias large.
        category_match = sum(
            1 for it in items if it.agent_inferred_emotion == it.ground_truth_emotion
        ) / max(n_items_total, 1)
        if category_match >= 0.7:
            overall_mae = sum(
                abs(it.agent_inferred_intensity - it.ground_truth_intensity) for it in items
            ) / max(n_items_total, 1)
            if overall_mae >= 0.25:
                return "categorical_signal_only"

        # Balanced patterns.
        if all(m.accuracy >= 0.8 for m in metrics if m.n_items >= 1):
            return "balanced_high"
        if all(m.accuracy < 0.4 for m in metrics if m.n_items >= 1):
            return "balanced_low"
        if all(0.4 <= m.accuracy < 0.8 for m in metrics if m.n_items >= 1):
            return "balanced_developing"

        return "indeterminate"

    # ------------------------------------------------------------------
    # LLM call helper
    # ------------------------------------------------------------------

    def _call(
        self,
        prompt: str,
        *,
        pass_name: str,
        mode: DANVAMode,
        acc: "_PipelineAcc",
    ) -> str:
        with time_call() as t:
            raw = self._complete(prompt, system=DANVA_SYSTEM_PROMPT)
        usage = cast(LLMUsage | None, getattr(self.llm, "last_usage", None))
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
        total_tokens = (
            int(getattr(usage, "total_tokens", 0) or 0) if usage else input_tokens + output_tokens
        )
        cost = (input_tokens / 1000.0) * self.cost_per_1k_input + (
            output_tokens / 1000.0
        ) * self.cost_per_1k_output
        record_llm_call(
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            elapsed_ms=t["elapsed_ms"],
            extra={"pass": pass_name, "mode": mode, "pattern": "danva_emotion"},
        )
        acc.add(input_tokens, output_tokens, cost, t["elapsed_ms"])
        return raw.strip()

    # ------------------------------------------------------------------
    # LLM passes (mode-specific)
    # ------------------------------------------------------------------

    def _format_metrics_table(self, metrics: list[EmotionMetric]) -> str:
        lines = []
        for m in metrics:
            if m.n_items == 0:
                continue
            lines.append(
                f"- {m.emotion} (n={m.n_items}): accuracy={m.accuracy:.2%}, "
                f"intensity_mae={m.intensity_mae:.2f}, bias={m.intensity_bias:+.2f}"
            )
        return "\n".join(lines) or "(no items)"

    def _format_confusion_table(self, metrics: list[EmotionMetric]) -> str:
        lines = []
        for m in metrics:
            if m.confusion_with:
                lines.append(
                    f"- {m.emotion}: "
                    + ", ".join(
                        f"{k} ({v}x)"
                        for k, v in sorted(m.confusion_with.items(), key=lambda x: -x[1])
                    )
                )
        return "\n".join(lines) or "(none)"

    def _sample_errors(self, items: list[EmotionItem]) -> str:
        errors = [it for it in items if it.agent_inferred_emotion != it.ground_truth_emotion][:5]
        if not errors:
            return "(none)"
        return "\n".join(
            f"- input: {it.user_input[:120]!r} | truth: {it.ground_truth_emotion} | "
            f"inferred: {it.agent_inferred_emotion}"
            for it in errors
        )

    def _pass_quick(
        self,
        trace: AgentEmotionTrace,
        metrics: list[EmotionMetric],
        overall_acc: float,
        overall_mae: float,
        weakest: str,
        quality: str,
        acc: "_PipelineAcc",
    ) -> list[EmotionIntervention]:
        # Quick mode: only LLM-call if quality != high-accuracy.
        if quality == "high-accuracy":
            return []
        prompt = assemble_prompt(
            QUICK_DIAGNOSTIC_PROMPT,
            n_items=len(trace.items),
            overall_accuracy=f"{overall_acc:.2%}",
            overall_intensity_mae=f"{overall_mae:.2f}",
            weakest_emotion=weakest,
            accuracy_quality=quality,
            metrics_table=self._format_metrics_table(metrics),
            confusion_table=self._format_confusion_table(metrics),
            sample_errors=self._sample_errors(trace.items),
        )
        raw = self._call(prompt, pass_name="quick", mode="quick", acc=acc)
        return self._parse_interventions(raw)

    def _pass_standard(
        self,
        trace: AgentEmotionTrace,
        metrics: list[EmotionMetric],
        overall_acc: float,
        overall_mae: float,
        weakest: str,
        quality: str,
        profile_pattern: str,
        acc: "_PipelineAcc",
    ) -> list[EmotionIntervention]:
        if quality == "high-accuracy":
            return []
        prompt = assemble_prompt(
            STANDARD_INTERVENTIONS_PROMPT,
            n_items=len(trace.items),
            overall_accuracy=f"{overall_acc:.2%}",
            overall_intensity_mae=f"{overall_mae:.2f}",
            weakest_emotion=weakest,
            accuracy_quality=quality,
            profile_pattern=profile_pattern,
            metrics_table=self._format_metrics_table(metrics),
            confusion_table=self._format_confusion_table(metrics),
            sample_errors=self._sample_errors(trace.items),
        )
        raw = self._call(prompt, pass_name="standard", mode="standard", acc=acc)
        return self._parse_interventions(raw)

    def _pass_dimensional_overlay(
        self,
        trace: AgentEmotionTrace,
        acc: "_PipelineAcc",
    ) -> CircumplexProjection | None:
        sample = [it.model_dump() for it in trace.items[:10]]
        prompt = assemble_prompt(
            FORENSIC_DIMENSIONAL_OVERLAY_PROMPT,
            items=sample,
        )
        raw = self._call(prompt, pass_name="forensic_dimensional", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return CircumplexProjection(**obj)
        except Exception as exc:
            log.warning("Failed to parse circumplex: %s", type(exc).__name__)
            return None

    def _pass_cascade_reconcile(
        self,
        metrics: list[EmotionMetric],
        confusion_matrix: EmotionConfusionMatrix,
        circumplex: CircumplexProjection | None,
        acc: "_PipelineAcc",
    ) -> CascadeAnalysis | None:
        prompt = assemble_prompt(
            FORENSIC_CASCADE_RECONCILE_PROMPT,
            metrics_table=self._format_metrics_table(metrics),
            confusion_table=self._format_confusion_table(metrics),
            circumplex=circumplex.model_dump() if circumplex else None,
        )
        raw = self._call(prompt, pass_name="forensic_cascade", mode="forensic", acc=acc)
        obj = _try_json_object(raw)
        if not obj:
            return None
        try:
            return CascadeAnalysis(**obj)
        except Exception as exc:
            log.warning("Failed to parse cascade: %s", type(exc).__name__)
            return None

    def _pass_forensic_interventions(
        self,
        trace: AgentEmotionTrace,
        metrics: list[EmotionMetric],
        weakest: str,
        profile_pattern: str,
        cascade: CascadeAnalysis | None,
        acc: "_PipelineAcc",
    ) -> list[EmotionIntervention]:
        overall = sum(m.accuracy * m.n_items for m in metrics) / max(
            sum(m.n_items for m in metrics), 1
        )
        if overall >= 0.8:
            return []
        prompt = assemble_prompt(
            FORENSIC_INTERVENTIONS_PROMPT,
            profile_pattern=profile_pattern,
            cascade_break_point=cascade.cascade_break_point if cascade else "intact",
            weakest_emotion=weakest,
            metrics_table=self._format_metrics_table(metrics),
            sample_errors=self._sample_errors(trace.items),
        )
        raw = self._call(prompt, pass_name="forensic_interventions", mode="forensic", acc=acc)
        return self._parse_interventions(raw)

    def _parse_interventions(self, raw: str) -> list[EmotionIntervention]:
        data = extract_json_array(raw)
        interventions: list[EmotionIntervention] = []
        for entry in data:
            try:
                interventions.append(EmotionIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed EmotionIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # ------------------------------------------------------------------
    # Composition + playbooks
    # ------------------------------------------------------------------

    def _build_composition_handoff(
        self,
        trace: AgentEmotionTrace,
        profile_pattern: str,
        weakest: str,
        interventions: list[EmotionIntervention],
    ) -> ComposedPatternHandoff:
        provisional = EmotionRecognitionAnalysis(
            metrics=[],
            overall_accuracy=0.5,
            overall_intensity_mae=0.2,
            weakest_emotion=weakest,  # type: ignore[arg-type]
            accuracy_quality="developing",
            interventions=interventions,
            n_items=len(trace.items),
            profile_pattern=profile_pattern,  # type: ignore[arg-type]
        )
        downstream, rationale = recommended_downstream(provisional, trace)
        upstream = recommended_upstream()
        payload: dict[str, Any] = {
            "weakest_emotion": weakest,
            "profile_pattern": profile_pattern,
            "framework": trace.framework,
            "intervention_types": [iv.intervention_type for iv in interventions],
        }
        return ComposedPatternHandoff(
            upstream_patterns=upstream,
            downstream_patterns=downstream,
            handoff_payload=payload,
            rationale=rationale,
        )

    def _attach_playbooks(self, interventions: list[EmotionIntervention]) -> list[AttachedPlaybook]:
        attached: dict[tuple[str, str], AttachedPlaybook] = {}
        for iv in interventions:
            pb = find_playbook_for_intervention(iv.target_emotion, iv.intervention_type)
            if pb is not None and (pb.emotion, pb.failure_mode) not in attached:
                attached[(pb.emotion, pb.failure_mode)] = pb
        return list(attached.values())


# ---------------------------------------------------------------------------
# Async mirror
# ---------------------------------------------------------------------------


class EmotionRecognitionAnalyzerAsync:
    """Async mirror of :class:`EmotionRecognitionAnalyzer`."""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        mode: DANVAMode = "standard",
        max_retries: int = 3,
        cost_per_1k_input: float = _DEFAULT_COST_PER_1K["input"],
        cost_per_1k_output: float = _DEFAULT_COST_PER_1K["output"],
        composition_enabled: bool = True,
        playbooks_enabled: bool = True,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.mode: DANVAMode = mode
        self.max_retries = max_retries
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.composition_enabled = composition_enabled
        self.playbooks_enabled = playbooks_enabled

    async def arun(
        self,
        trace: AgentEmotionTrace,
        *,
        mode: DANVAMode | None = None,
        baseline_path: str | Path | None = None,
    ) -> EmotionRecognitionAnalysis:
        active_mode: DANVAMode = mode or self.mode
        client = self.llm

        async def _async_complete(prompt: str, system: str | None = None) -> str:
            return await client.complete(prompt, system=system)

        sync_shim = _SyncAdapterFromAsync(_async_complete, getattr(self.llm, "last_usage", None))
        sync_analyzer = EmotionRecognitionAnalyzer(
            llm_client=sync_shim,
            model=self.model,
            mode=active_mode,
            max_retries=self.max_retries,
            cost_per_1k_input=self.cost_per_1k_input,
            cost_per_1k_output=self.cost_per_1k_output,
            composition_enabled=self.composition_enabled,
            playbooks_enabled=self.playbooks_enabled,
        )
        return await asyncio.to_thread(
            sync_analyzer.run, trace, mode=active_mode, baseline_path=baseline_path
        )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


class _PipelineAcc:
    """Per-run accumulator for token + cost + elapsed telemetry."""

    __slots__ = (
        "tokens_input",
        "tokens_output",
        "tokens_total",
        "cost_usd",
        "llm_calls",
        "elapsed_ms",
    )

    def __init__(self) -> None:
        self.tokens_input = 0
        self.tokens_output = 0
        self.tokens_total = 0
        self.cost_usd = 0.0
        self.llm_calls = 0
        self.elapsed_ms = 0.0

    def add(self, input_tokens: int, output_tokens: int, cost: float, elapsed_ms: float) -> None:
        self.tokens_input += input_tokens
        self.tokens_output += output_tokens
        self.tokens_total += input_tokens + output_tokens
        self.cost_usd += cost
        self.elapsed_ms += elapsed_ms
        self.llm_calls += 1


class _SyncAdapterFromAsync:
    """Wrap an async ``complete`` callable as a synchronous client."""

    def __init__(
        self,
        async_complete: Callable[[str, str | None], Coroutine[Any, Any, str]],
        last_usage: LLMUsage | None,
    ) -> None:
        self._async_complete = async_complete
        self.last_usage = last_usage

    def complete(self, prompt: str, system: str | None = None) -> str:
        return asyncio.run(self._async_complete(prompt, system))


def _try_json_object(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        v = json.loads(text)
        if isinstance(v, dict):
            return v
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if 0 <= start < end:
        try:
            v = json.loads(text[start : end + 1])
            if isinstance(v, dict):
                return v
        except json.JSONDecodeError:
            pass
    return None


_legacy_log = logging.getLogger("agentcity.danva_emotion.generator")
_legacy_log.addHandler(logging.NullHandler())
