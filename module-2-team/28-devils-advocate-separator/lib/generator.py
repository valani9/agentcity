"""RoleSeparationDetector: diagnose Devil's-Advocate role separation
(plan / execute / self-evaluate / external-critique) in a single-agent
trace.

Pipeline:
  1. Validate the trace (non-empty task, outcome, at least one step)
  2. Pass 1: LLM scores all four phases against the trace
  3. Compute role_separation_score from phase presence + actor diversity
  4. Compute locus_of_judgment from who performed self_evaluate vs
     external_critique
  5. Compute self_approval_rate from the agent's self-evaluation steps
  6. Determine role_separation_quality bucket
  7. Pass 2: propose interventions targeting the weakest phase
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal, Protocol

from agentcity.aar._json_parsing import extract_json_array
from agentcity.aar._retry import with_retry

from .prompts import (
    INTERVENTIONS_PROMPT,
    PHASE_EVIDENCE_PROMPT,
    ROLE_SEPARATION_SYSTEM_PROMPT,
)
from .schema import (
    PHASES,
    PhaseEvidence,
    RoleSeparationDetection,
    RoleSeparationIntervention,
    SingleAgentTrace,
)

log = logging.getLogger("agentcity.devils_advocate.generator")


class LLMClient(Protocol):
    def complete(self, prompt: str, system: str | None = None) -> str: ...


class RoleSeparationDetector:
    """Run the Role-Separation diagnostic on a SingleAgentTrace."""

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

    def run(self, trace: SingleAgentTrace) -> RoleSeparationDetection:
        self._validate_trace(trace)
        trace_text = self._serialize_trace(trace)

        started = time.monotonic()
        log.info(
            "Running Role-Separation detection for agent %s (steps=%d, success=%s)",
            trace.agent_id or "<unknown>",
            len(trace.steps),
            trace.success,
        )

        evidence = self._pass_1_phases(trace, trace_text)
        sep_score = self._role_separation_score(evidence)
        locus = self._locus_of_judgment(evidence)
        approval = self._self_approval_rate(trace)
        quality = self._role_separation_quality(sep_score, evidence)
        interventions = self._pass_2_interventions(trace, trace_text, evidence, quality, locus)

        detection = RoleSeparationDetection(
            agent_id=trace.agent_id,
            model_name=trace.model_name,
            role_separation_quality=quality,
            role_separation_score=sep_score,
            locus_of_judgment=locus,
            phase_evidence=evidence,
            self_approval_rate=approval,
            interventions=interventions,
            generator_model=self.model,
            success=trace.success,
        )

        elapsed = time.monotonic() - started
        log.info(
            "Role-Separation detection for agent %s done in %.2fs "
            "(quality=%s, locus=%s, interventions=%d)",
            trace.agent_id or "<unknown>",
            elapsed,
            quality,
            locus,
            len(interventions),
        )
        return detection

    # --- Input validation ----------------------------------------------

    def _validate_trace(self, trace: SingleAgentTrace) -> None:
        if not trace.task or not trace.task.strip():
            raise ValueError("SingleAgentTrace.task cannot be empty.")
        if not trace.outcome or not trace.outcome.strip():
            raise ValueError("SingleAgentTrace.outcome cannot be empty.")
        if not trace.steps:
            raise ValueError("SingleAgentTrace.steps cannot be empty.")

    # --- LLM passes ----------------------------------------------------

    def _pass_1_phases(self, trace: SingleAgentTrace, trace_text: str) -> list[PhaseEvidence]:
        prompt = PHASE_EVIDENCE_PROMPT.format(
            task=trace.task,
            model_name=trace.model_name or "unspecified",
            outcome=trace.outcome,
            success=trace.success,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=ROLE_SEPARATION_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        evidence: list[PhaseEvidence] = []
        for entry in data:
            try:
                evidence.append(PhaseEvidence(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed PhaseEvidence (%s): %r",
                    type(exc).__name__,
                    entry,
                )

        seen = {ev.phase for ev in evidence}
        for phase in PHASES:
            if phase not in seen:
                evidence.append(
                    PhaseEvidence(
                        phase=phase,  # type: ignore[arg-type]
                        present=False,
                        actor="primary",
                        substantive_score=0.0,
                        explanation="No evidence of this phase observed.",
                        evidence_quotes=[],
                    )
                )

        order = {phase: i for i, phase in enumerate(PHASES)}
        evidence.sort(key=lambda e: order.get(e.phase, len(PHASES)))
        return evidence

    def _pass_2_interventions(
        self,
        trace: SingleAgentTrace,
        trace_text: str,
        evidence: list[PhaseEvidence],
        quality: str,
        locus: str,
    ) -> list[RoleSeparationIntervention]:
        if quality == "well-separated":
            return []
        evidence_text = json.dumps([e.model_dump() for e in evidence], indent=2, default=str)
        prompt = INTERVENTIONS_PROMPT.format(
            quality=quality,
            locus=locus,
            evidence=evidence_text,
            trace=trace_text,
        )
        raw = self._complete(prompt, system=ROLE_SEPARATION_SYSTEM_PROMPT).strip()
        data = extract_json_array(raw)

        interventions: list[RoleSeparationIntervention] = []
        for entry in data:
            try:
                interventions.append(RoleSeparationIntervention(**entry))
            except Exception as exc:
                log.warning(
                    "Dropping malformed RoleSeparationIntervention (%s): %r",
                    type(exc).__name__,
                    entry,
                )
        return interventions

    # --- Synthesis -----------------------------------------------------

    def _role_separation_score(self, evidence: list[PhaseEvidence]) -> float:
        """Score 0.0 (fully conflated) to 1.0 (fully separated).

        Rewards: external_critique present, performed by a distinct actor,
                 and substantive.
        Penalizes: self_evaluate by primary agent acting as a stand-in for
                   external critique.
        """
        by_phase = {ev.phase: ev for ev in evidence}
        critique = by_phase.get("external_critique")
        self_eval = by_phase.get("self_evaluate")
        plan = by_phase.get("plan")

        score = 0.0
        if critique and critique.present and critique.actor != "primary":
            score += 0.6 * critique.substantive_score
        if self_eval and self_eval.present:
            score += 0.2 * self_eval.substantive_score
            if plan and self_eval.actor == plan.actor:
                score -= 0.1
        if critique and critique.present and critique.actor != "primary":
            score += 0.3
        return max(0.0, min(1.0, score))

    def _locus_of_judgment(
        self, evidence: list[PhaseEvidence]
    ) -> Literal["self-reviewed", "externally-reviewed", "mixed", "unreviewed"]:
        by_phase = {ev.phase: ev for ev in evidence}
        self_eval = by_phase.get("self_evaluate")
        ext_critique = by_phase.get("external_critique")
        self_present = bool(self_eval and self_eval.present)
        ext_present = bool(
            ext_critique and ext_critique.present and ext_critique.actor != "primary"
        )
        if ext_present and self_present:
            return "mixed"
        if ext_present:
            return "externally-reviewed"
        if self_present:
            return "self-reviewed"
        return "unreviewed"

    def _self_approval_rate(self, trace: SingleAgentTrace) -> float:
        """Estimate what fraction of self-evaluate steps approved (vs revised).

        Heuristic: any self_evaluate step whose content contains a clear
        revision/retry marker counts as revision; otherwise approval.
        """
        self_evals = [s for s in trace.steps if s.type == "self_evaluate"]
        if not self_evals:
            return 0.0
        revision_markers = (
            "revise",
            "retry",
            "actually wrong",
            "let me reconsider",
            "i was incorrect",
            "this isn't right",
            "back to the drawing board",
        )
        approvals = sum(
            1 for s in self_evals if not any(m in s.content.lower() for m in revision_markers)
        )
        return round(approvals / len(self_evals), 2)

    def _role_separation_quality(
        self, sep_score: float, evidence: list[PhaseEvidence]
    ) -> Literal["well-separated", "partially-conflated", "fully-conflated"]:
        ext = next(
            (ev for ev in evidence if ev.phase == "external_critique"),
            None,
        )
        ext_present_distinct = bool(
            ext and ext.present and ext.actor != "primary" and ext.substantive_score >= 0.4
        )
        if sep_score >= 0.6 and ext_present_distinct:
            return "well-separated"
        if sep_score >= 0.3:
            return "partially-conflated"
        return "fully-conflated"

    # --- Trace serialization -------------------------------------------

    def _serialize_trace(self, trace: SingleAgentTrace) -> str:
        header = [
            f"Task: {trace.task}",
            f"Subject model: {trace.model_name or 'unspecified'}",
            f"Outcome: {trace.outcome}",
            f"Success: {trace.success}",
            "",
        ]
        step_lines: list[str] = []
        for i, step in enumerate(trace.steps):
            ts = (
                f"[{step.timestamp.isoformat()}] "
                if step.timestamp is not None
                else f"[step {i + 1}] "
            )
            conf = f" (confidence={step.confidence:.2f})" if step.confidence is not None else ""
            step_lines.append(f"{ts}({step.type}, actor={step.actor}){conf} {step.content}")
        full = "\n".join(header + step_lines)
        if len(full) <= self.max_trace_chars:
            return full
        log.warning(
            "Single-agent trace exceeds max_trace_chars (%d > %d); truncating",
            len(full),
            self.max_trace_chars,
        )
        keep = self.max_trace_chars // 2 - 200
        return (
            full[:keep]
            + f"\n\n[... TRACE TRUNCATED ({len(full) - self.max_trace_chars} chars omitted) ...]\n\n"
            + full[-keep:]
        )
