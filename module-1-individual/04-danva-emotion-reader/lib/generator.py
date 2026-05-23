"""EmotionRecognitionAnalyzer: DANVA-style emotion-recognition accuracy
diagnostic for an AI agent.

Pipeline:
  1. Validate the trace (non-empty items list)
  2. Compute per-emotion metrics DETERMINISTICALLY in Python:
     accuracy, intensity MAE, confusion patterns
  3. Bucket overall accuracy quality
  4. ONE LLM pass: propose interventions (skipped on high-accuracy)
"""

from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from typing import Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import DANVA_SYSTEM_PROMPT, INTERVENTIONS_PROMPT
from .schema import (
    EMOTION_CATEGORIES,
    AgentEmotionTrace,
    EmotionIntervention,
    EmotionItem,
    EmotionMetric,
    EmotionRecognitionAnalysis,
)

log = logging.getLogger("agentcity.danva_emotion.generator")


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class EmotionRecognitionAnalyzer:
    """Run the DANVA-style emotion-recognition diagnostic."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        max_retries: int = 3,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.max_retries = max_retries
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(self, trace: AgentEmotionTrace) -> EmotionRecognitionAnalysis:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running DANVA-style emotion-recognition diagnostic for agent %s (%d items)",
            trace.agent_id or "<unknown>",
            len(trace.items),
        )

        # All metrics computed DETERMINISTICALLY — no LLM in the math
        metrics = self._compute_metrics(trace.items)
        overall_acc, overall_mae = self._compute_overall(trace.items)
        weakest = self._coerce_weakest(metrics)
        quality = self._accuracy_quality(overall_acc)

        interventions = (
            []
            if quality == "high-accuracy"
            else self._pass_interventions(
                trace.items, metrics, overall_acc, overall_mae, weakest, quality
            )
        )

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
        )

        elapsed = time.monotonic() - started
        log.info(
            "DANVA diagnostic for agent %s done in %.2fs (accuracy=%.2f, weakest=%s, quality=%s)",
            trace.agent_id or "<unknown>",
            elapsed,
            overall_acc,
            weakest,
            quality,
        )
        return analysis

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentEmotionTrace) -> None:
        if not trace.items:
            raise ValueError("AgentEmotionTrace.items cannot be empty.")

    # --- Deterministic metric computation -----------------------------

    def _compute_metrics(self, items: list[EmotionItem]) -> list[EmotionMetric]:
        # Group items by ground-truth emotion
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
            metrics.append(
                EmotionMetric(
                    emotion=emotion,  # type: ignore[arg-type]
                    n_items=n,
                    accuracy=round(accuracy, 4),
                    intensity_mae=round(mae, 4),
                    confusion_with=dict(confusion),
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
        # Consider only emotions with at least 2 items in the batch
        # (otherwise accuracy on n=1 is noise)
        candidates = [m for m in metrics if m.n_items >= 2]
        if not candidates:
            return "none"
        # Pick the lowest-accuracy emotion. If all accuracies are >= 0.8, "none".
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

    # --- LLM pass (interventions only — math is locked) ---------------

    def _pass_interventions(
        self,
        items: list[EmotionItem],
        metrics: list[EmotionMetric],
        overall_acc: float,
        overall_mae: float,
        weakest: str,
        quality: str,
    ) -> list[EmotionIntervention]:
        metrics_lines = []
        confusion_lines = []
        for m in metrics:
            if m.n_items == 0:
                continue
            metrics_lines.append(
                f"- {m.emotion} (n={m.n_items}): accuracy={m.accuracy:.2%}, "
                f"intensity_mae={m.intensity_mae:.2f}"
            )
            if m.confusion_with:
                confusion_lines.append(
                    f"- {m.emotion}: "
                    + ", ".join(
                        f"{k} ({v}x)"
                        for k, v in sorted(m.confusion_with.items(), key=lambda x: -x[1])
                    )
                )

        # Sample up to 5 misclassified items for context
        errors = [it for it in items if it.agent_inferred_emotion != it.ground_truth_emotion][:5]
        sample_errors = (
            "\n".join(
                f"- input: {it.user_input[:120]!r} | truth: {it.ground_truth_emotion} | "
                f"inferred: {it.agent_inferred_emotion}"
                for it in errors
            )
            or "(none)"
        )

        prompt = INTERVENTIONS_PROMPT.format(
            overall_accuracy=f"{overall_acc:.2%}",
            overall_intensity_mae=f"{overall_mae:.2f}",
            weakest_emotion=weakest,
            accuracy_quality=quality,
            metrics_table="\n".join(metrics_lines) or "(no items)",
            confusion_table="\n".join(confusion_lines) or "(none)",
            sample_errors=sample_errors,
        )
        raw = self._complete(prompt, system=DANVA_SYSTEM_PROMPT).strip()
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
