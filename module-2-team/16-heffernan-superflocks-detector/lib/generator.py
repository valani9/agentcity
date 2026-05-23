"""SuperflocksDetector: diagnose Heffernan's superflocks fragility pattern
in a multi-agent orchestrator's routing behavior.

Pipeline:
  1. Validate the trace (non-empty agents, >=2 routing decisions)
  2. Compute five quantitative metrics locally (deterministic Python):
     - top_agent_share
     - routing_gini
     - complementarity_utilization
     - fallback_coverage
     - failure_clustering
  3. Single LLM pass: produce qualitative per-metric explanations +
     severity assessments + interventions
  4. Compute the fragility-quality bucket from the metrics
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import Counter
from typing import Any, Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array  # noqa: F401  (kept for parity)
from agentcity.aar._retry import with_retry

from .prompts import METRICS_PROMPT, SUPERFLOCKS_SYSTEM_PROMPT
from .schema import (
    AgentCapability,
    FragilityIntervention,
    RoutingTrace,
    SuperflocksDetection,
    SuperflocksMetric,
)

log = logging.getLogger("agentcity.superflocks.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)

_METRIC_ORDER: tuple[str, ...] = (
    "top_agent_share",
    "routing_gini",
    "complementarity_utilization",
    "fallback_coverage",
    "failure_clustering",
)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class SuperflocksDetector:
    """Run the Heffernan superflocks diagnostic on a RoutingTrace."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "claude-sonnet-4-6",
        *,
        max_retries: int = 3,
        max_trace_chars: int = 200_000,
    ) -> None:
        self.llm = llm_client
        self.model = model
        self.max_retries = max_retries
        self.max_trace_chars = max_trace_chars
        self._complete = with_retry(self.llm.complete, max_attempts=max_retries)

    def run(self, trace: RoutingTrace) -> SuperflocksDetection:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Superflocks detection for trace %s (agents=%d, decisions=%d)",
            trace.trace_id or "<unknown>",
            len(trace.agents),
            len(trace.routing_decisions),
        )

        numerical = self._compute_metrics(trace)
        top_agent, top_share = self._top_agent_and_share(trace)
        gini = numerical["routing_gini"]

        data = self._pass_1_qualitative(trace, numerical)
        metrics = self._parse_metrics(data.get("metrics", []), numerical)
        interventions = self._parse_interventions(data.get("interventions", []))
        fragility_score = self._fragility_score(numerical)
        fragility_quality = self._fragility_quality(
            fragility_score, str(data.get("fragility_quality", "")).strip().lower()
        )

        detection = SuperflocksDetection(
            trace_id=trace.trace_id,
            top_agent=top_agent,
            top_agent_share=top_share,
            routing_gini=gini,
            fragility_score=fragility_score,
            fragility_quality=fragility_quality,
            metrics=metrics,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Superflocks detection for trace %s done in %.2fs "
            "(top=%s @ %.2f, fragility=%s, score=%.2f)",
            trace.trace_id or "<unknown>",
            elapsed,
            top_agent,
            top_share,
            fragility_quality,
            fragility_score,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: RoutingTrace) -> None:
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("RoutingTrace.outcome cannot be empty.")
        if not trace.agents:
            raise ValueError("RoutingTrace.agents cannot be empty.")
        if len(trace.routing_decisions) < 2:
            raise ValueError("RoutingTrace.routing_decisions must contain at least 2 decisions.")

    # --- Local metric computation ---------------------------------------

    def _compute_metrics(self, trace: RoutingTrace) -> dict[str, float]:
        decisions = trace.routing_decisions
        n = len(decisions)
        counts = Counter(d.routed_to for d in decisions)
        top_count = max(counts.values()) if counts else 0
        top_share = top_count / n if n else 0.0

        # Gini over per-agent share (counts for all agents including 0-share)
        per_agent_counts = [counts.get(a, 0) for a in trace.agents]
        gini = self._gini(per_agent_counts)

        # Complementarity utilization: fraction of decisions where the chosen
        # agent was NOT the top agent. Higher = more diverse routing.
        top_agents_set = {a for a, c in counts.items() if c == top_count} if counts else set()
        non_top = sum(1 for d in decisions if d.routed_to not in top_agents_set)
        complementarity = non_top / n if n else 0.0

        # Fallback coverage: for each observed task_class, fraction where >=2
        # agents have capability >=0.5. If no capability data, 1.0 (assume coverage).
        fallback = self._fallback_coverage(trace)

        # Failure clustering: among failed decisions, fraction routed to top agent.
        failed = [d for d in decisions if d.outcome == "failure"]
        if failed and top_agents_set:
            failed_on_top = sum(1 for d in failed if d.routed_to in top_agents_set)
            clustering = failed_on_top / len(failed)
        else:
            clustering = 0.0

        return {
            "top_agent_share": round(top_share, 2),
            "routing_gini": round(gini, 2),
            "complementarity_utilization": round(complementarity, 2),
            "fallback_coverage": round(fallback, 2),
            "failure_clustering": round(clustering, 2),
        }

    def _gini(self, counts: list[int]) -> float:
        if not counts:
            return 0.0
        sorted_counts = sorted(counts)
        n = len(sorted_counts)
        total = sum(sorted_counts)
        if total <= 0:
            return 0.0
        weighted = sum((2 * i - n - 1) * x for i, x in enumerate(sorted_counts, start=1))
        return max(0.0, min(1.0, weighted / (n * total)))

    def _fallback_coverage(self, trace: RoutingTrace) -> float:
        if not trace.capabilities:
            return 1.0
        # Collect task classes observed in routing
        classes = {d.task_class for d in trace.routing_decisions if d.task_class}
        if not classes:
            return 1.0
        cap_map: dict[str, dict[str, float]] = {
            c.agent_name: c.capability_scores for c in trace.capabilities
        }
        covered = 0
        for task_class in classes:
            qualified = sum(1 for scores in cap_map.values() if scores.get(task_class, 0.0) >= 0.5)
            if qualified >= 2:
                covered += 1
        return covered / len(classes)

    def _top_agent_and_share(self, trace: RoutingTrace) -> tuple[str | None, float]:
        counts = Counter(d.routed_to for d in trace.routing_decisions)
        if not counts:
            return None, 0.0
        agent, count = counts.most_common(1)[0]
        return agent, round(count / len(trace.routing_decisions), 2)

    def _fragility_score(self, numerical: dict[str, float]) -> float:
        """Weighted blend of the five metrics where higher = more fragile.

        For complementarity_utilization and fallback_coverage, higher values
        are GOOD, so we invert before weighting.
        """
        share = numerical["top_agent_share"]
        gini = numerical["routing_gini"]
        complementarity_loss = 1.0 - numerical["complementarity_utilization"]
        fallback_loss = 1.0 - numerical["fallback_coverage"]
        clustering = numerical["failure_clustering"]
        # Weights chosen by intuition: top_agent_share + gini dominate; clustering
        # is the empirical confirmation; complementarity/fallback are structural.
        score = (
            0.30 * share
            + 0.25 * gini
            + 0.20 * complementarity_loss
            + 0.15 * fallback_loss
            + 0.10 * clustering
        )
        return round(max(0.0, min(1.0, score)), 2)

    def _fragility_quality(
        self, score: float, raw: str
    ) -> Literal["robust", "concentrated", "superflocks"]:
        if raw in ("robust", "concentrated", "superflocks"):
            return raw  # type: ignore[return-value]
        if score >= 0.65:
            return "superflocks"
        if score >= 0.35:
            return "concentrated"
        return "robust"

    # --- LLM pass ------------------------------------------------------

    def _pass_1_qualitative(
        self, trace: RoutingTrace, numerical: dict[str, float]
    ) -> dict[str, Any]:
        prompt = METRICS_PROMPT.format(
            trace_id=trace.trace_id or "<unknown>",
            window_description=trace.window_description,
            outcome=trace.outcome,
            success=trace.success,
            agents=", ".join(trace.agents),
            capabilities=self._format_capabilities(trace.capabilities),
            decisions=self._format_decisions(trace),
            metrics_numerical=json.dumps(numerical, indent=2),
        )
        raw = self._complete(prompt, system=SUPERFLOCKS_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _parse_metrics(
        self, raw: list[Any], numerical: dict[str, float]
    ) -> list[SuperflocksMetric]:
        metrics: list[SuperflocksMetric] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            # Override the LLM-reported value with our deterministic local value
            name = entry.get("name")
            if isinstance(name, str) and name in numerical:
                entry["value"] = numerical[name]
            try:
                metrics.append(SuperflocksMetric(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed SuperflocksMetric (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {m.name for m in metrics}
        for name in _METRIC_ORDER:
            if name not in seen:
                metrics.append(
                    SuperflocksMetric(
                        name=name,  # type: ignore[arg-type]
                        value=numerical.get(name, 0.0),
                        explanation="No qualitative explanation provided by the model.",
                        severity="none",
                    )
                )
        order = {n: i for i, n in enumerate(_METRIC_ORDER)}
        metrics.sort(key=lambda m: order.get(m.name, len(_METRIC_ORDER)))
        return metrics

    def _parse_interventions(self, raw: list[Any]) -> list[FragilityIntervention]:
        interventions: list[FragilityIntervention] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                interventions.append(FragilityIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed FragilityIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Formatting helpers --------------------------------------------

    def _format_capabilities(self, caps: list[AgentCapability]) -> str:
        if not caps:
            return "(none provided)"
        lines = []
        for c in caps:
            scores_text = ", ".join(f"{k}={v:.2f}" for k, v in c.capability_scores.items())
            lines.append(f"- {c.agent_name}: {scores_text or '(no scores)'}")
        return "\n".join(lines)

    def _format_decisions(self, trace: RoutingTrace) -> str:
        lines = [
            f"- task={d.task_id} class={d.task_class} -> {d.routed_to} "
            f"(reason: {d.reason or 'n/a'}, outcome: {d.outcome})"
            for d in trace.routing_decisions
        ]
        full = "\n".join(lines)
        if len(full) <= self.max_trace_chars:
            return full
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... DECISIONS TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )

    # --- JSON object extraction -----------------------------------------

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        candidates: list[str] = []
        stripped = text.strip()
        if stripped:
            candidates.append(stripped)
        for match in _FENCE_RE.finditer(text):
            body = match.group(1).strip()
            if body:
                candidates.append(body)
        start = text.find("{")
        end = text.rfind("}")
        if 0 <= start < end:
            candidates.append(text[start : end + 1])
        for candidate in candidates:
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        return {}
