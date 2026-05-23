"""CultureAuditDetector: diagnose Schein's three culture layers (artifacts,
espoused values, underlying assumptions) for an AI agent — and identify
when the layers drift apart.

Pipeline:
  1. Validate the trace (non-empty task + outcome + system_prompt or observed_behaviors)
  2. Pass 1: LLM scores all three layers + alignment + dominant drift
  3. Determine culture-quality bucket
  4. Pass 2: propose interventions for the dominant drift (skipped on aligned)
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import INTERVENTIONS_PROMPT, LAYERS_PROMPT, SCHEIN_SYSTEM_PROMPT
from .schema import (
    CULTURE_LAYERS,
    AgentCultureTrace,
    CultureAuditDetection,
    CultureIntervention,
    LayerEvidence,
)

log = logging.getLogger("agentcity.schein_culture.generator")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class CultureAuditDetector:
    """Run the Schein Iceberg culture audit on an AgentCultureTrace."""

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

    def run(self, trace: AgentCultureTrace) -> CultureAuditDetection:
        self._validate_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Schein Culture audit for agent %s",
            trace.agent_id or "<unknown>",
        )

        data = self._pass_1_layers(trace)
        layers = self._parse_layers(data.get("layers", []))
        alignment = self._coerce_fraction(data.get("alignment_score"))
        dominant_drift = self._coerce_drift(data.get("dominant_drift"))
        culture_quality = self._culture_quality(
            alignment, dominant_drift, str(data.get("culture_quality", "")).strip().lower()
        )

        interventions = (
            []
            if culture_quality == "aligned"
            else self._pass_2_interventions(layers, dominant_drift, culture_quality)
        )

        detection = CultureAuditDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            layers=layers,
            alignment_score=alignment,
            dominant_drift=dominant_drift,
            culture_quality=culture_quality,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Schein Culture audit for agent %s done in %.2fs "
            "(alignment=%.2f, drift=%s, quality=%s)",
            trace.agent_id or "<unknown>",
            elapsed,
            alignment,
            dominant_drift,
            culture_quality,
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: AgentCultureTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("AgentCultureTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("AgentCultureTrace.outcome cannot be empty.")
        if not trace.system_prompt and not trace.observed_behaviors:
            raise ValueError(
                "AgentCultureTrace must include at least one of system_prompt or "
                "observed_behaviors (otherwise there is nothing to audit)."
            )

    # --- LLM passes ----------------------------------------------------

    def _pass_1_layers(self, trace: AgentCultureTrace) -> dict[str, Any]:
        prompt = LAYERS_PROMPT.format(
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            system_prompt=self._truncate(trace.system_prompt) or "(none)",
            observed_behaviors="\n".join(f"- {b}" for b in trace.observed_behaviors) or "(none)",
            inferred_assumptions="\n".join(f"- {a}" for a in trace.inferred_assumptions)
            or "(none)",
        )
        raw = self._complete(prompt, system=SCHEIN_SYSTEM_PROMPT).strip()
        return self._extract_json_object(raw)

    def _pass_2_interventions(
        self,
        layers: list[LayerEvidence],
        dominant_drift: str,
        culture_quality: str,
    ) -> list[CultureIntervention]:
        evidence_text = json.dumps(
            [layer_ev.model_dump() for layer_ev in layers], indent=2, default=str
        )
        prompt = INTERVENTIONS_PROMPT.format(
            dominant_drift=dominant_drift,
            culture_quality=culture_quality,
            evidence=evidence_text,
        )
        raw = self._complete(prompt, system=SCHEIN_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[CultureIntervention] = []
        for entry in data:
            try:
                interventions.append(CultureIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed CultureIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Parsers --------------------------------------------------------

    def _parse_layers(self, raw: list[Any]) -> list[LayerEvidence]:
        layers: list[LayerEvidence] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                layers.append(LayerEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed LayerEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {layer_ev.layer for layer_ev in layers}
        for layer in CULTURE_LAYERS:
            if layer not in seen:
                layers.append(
                    LayerEvidence(
                        layer=layer,  # type: ignore[arg-type]
                        summary="No data observed for this layer.",
                        coherence_score=0.0,
                        observations=[],
                    )
                )
        order = {layer: i for i, layer in enumerate(CULTURE_LAYERS)}
        layers.sort(key=lambda layer_ev: order.get(layer_ev.layer, len(CULTURE_LAYERS)))
        return layers

    def _coerce_fraction(self, raw: Any) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, value))

    def _coerce_drift(
        self, raw: Any
    ) -> Literal[
        "artifacts_vs_espoused",
        "artifacts_vs_assumptions",
        "espoused_vs_assumptions",
        "none-observed",
    ]:
        valid = {
            "artifacts_vs_espoused",
            "artifacts_vs_assumptions",
            "espoused_vs_assumptions",
            "none-observed",
        }
        if isinstance(raw, str) and raw.strip() in valid:
            return raw.strip()  # type: ignore[return-value]
        return "none-observed"

    def _culture_quality(
        self, alignment: float, drift: str, raw_quality: str
    ) -> Literal["aligned", "drifting", "incoherent"]:
        if raw_quality in ("aligned", "drifting", "incoherent"):
            return raw_quality  # type: ignore[return-value]
        # Alignment is the primary signal. A "none-observed" drift only
        # means the detector couldn't pick one of the three drift types,
        # not that the agent is aligned — that's what the alignment score
        # is for.
        if alignment >= 0.75:
            return "aligned"
        if alignment >= 0.4:
            return "drifting"
        return "incoherent"

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_trace_chars:
            return text
        keep = self.max_trace_chars // 2 - 200
        return (
            text[:keep]
            + f"\n\n[... TRUNCATED ({len(text) - self.max_trace_chars} chars omitted) ...]\n\n"
            + text[-keep:]
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
