"""Schema for the AAR (After-Action Review) Generator.

Wharton 4-step AAR structure (anchored in US Army TC 25-20):
  1. Goal       - What did we want to accomplish?
  2. Results    - What did we actually do?
  3. Lessons    - Why was there a difference?
  4. Next Steps - What will we do differently?

v0.2.0 adds three pipeline modes, a 7-point severity scale, eight
profile patterns, forensic-mode audits (Trace Quality, Lesson
Groundedness), calibration baselines, composition handoff, attached
playbooks. The existing AAR schema fields are preserved and v0.2.0
fields are added with defaults so all downstream patterns continue to
import + construct AAR objects unchanged.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- v0.2.0 mode + severity --------------------------------------------

AARMode = Literal["quick", "standard", "forensic"]
AAR_MODES: tuple[str, ...] = ("quick", "standard", "forensic")

Severity = Literal["none", "trace", "low", "moderate", "medium", "high", "critical"]
SEVERITY_ORDER: tuple[str, ...] = (
    "none",
    "trace",
    "low",
    "moderate",
    "medium",
    "high",
    "critical",
)


def severity_from_gap(gap_score: float) -> Severity:
    """Map goal-results gap (0=full alignment, 1=total miss) to severity."""
    s = max(0.0, min(1.0, float(gap_score)))
    if s < 0.10:
        return "none"
    if s < 0.25:
        return "trace"
    if s < 0.40:
        return "low"
    if s < 0.55:
        return "moderate"
    if s < 0.70:
        return "medium"
    if s < 0.85:
        return "high"
    return "critical"


AARProfilePattern = Literal[
    "success_aligned",
    "partial_success",
    "total_failure",
    "scope_mismatch",
    "retry_thrashing",
    "cost_overrun",
    "deadline_missed",
    "indeterminate",
]
AAR_PROFILE_PATTERNS: tuple[str, ...] = (
    "success_aligned",
    "partial_success",
    "total_failure",
    "scope_mismatch",
    "retry_thrashing",
    "cost_overrun",
    "deadline_missed",
    "indeterminate",
)


EffortEstimate = Literal["1h", "1d", "1w", "1m", "ongoing"]


# --- Input: a structured agent run trace -----------------------------------


class TraceStep(BaseModel):
    timestamp: datetime
    type: Literal["tool_call", "message", "decision", "observation", "thought"]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_step_id: str | None = None
    step_id: str | None = None


class AgentTrace(BaseModel):
    agent_id: str | None = None
    agent_framework: str | None = None
    goal: str
    steps: list[TraceStep]
    outcome: str
    success: bool
    cost_usd: float | None = None
    latency_seconds: float | None = None
    retry_count: int | None = None
    baseline_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: the Wharton 4-step AAR ---------------------------------------


class Lesson(BaseModel):
    pattern: str
    description: str
    root_cause: str
    framework_anchor: str
    cross_pattern_links: list[str] = Field(default_factory=list)


class NextStep(BaseModel):
    intervention_type: Literal[
        "prompt_patch",
        "tool_addition",
        "tool_removal",
        "scaffold_change",
        "new_eval",
        "human_review",
        "memory_injection",
        "compose_pattern",
    ]
    description: str
    suggested_implementation: str
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class TraceQualityAudit(BaseModel):
    """Forensic-mode: how rich was the input trace?"""

    step_count: int = Field(default=0, ge=0)
    tool_call_count: int = Field(default=0, ge=0)
    decision_count: int = Field(default=0, ge=0)
    observation_count: int = Field(default=0, ge=0)
    has_cost: bool = False
    has_latency: bool = False
    has_retry_count: bool = False
    completeness_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class LessonGroundednessAudit(BaseModel):
    """Forensic-mode: are lessons grounded in the trace?"""

    grounded_lesson_count: int = Field(default=0, ge=0)
    ungrounded_lesson_count: int = Field(default=0, ge=0)
    lessons_with_framework_anchor: int = Field(default=0, ge=0)
    lessons_with_cross_pattern_links: int = Field(default=0, ge=0)
    groundedness_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


class AttachedPlaybook(BaseModel):
    profile: str
    failure_mode: str
    title: str
    steps: list[str]
    expected_effort: EffortEstimate
    anchor_citation: str = ""


class BaselineComparison(BaseModel):
    historical_baseline_id: str | None = None
    historical_generated_at: datetime | None = None
    baseline_profile_pattern: str | None = None
    score_deltas: dict[str, float] = Field(default_factory=dict)
    drift_severity: Literal["none", "minor", "moderate", "severe"] = "none"
    notes: str = ""


class ComposedPatternHandoff(BaseModel):
    upstream_patterns: list[str] = Field(default_factory=list)
    downstream_patterns: list[str] = Field(default_factory=list)
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class AAR(BaseModel):
    """The full Wharton 4-step After-Action Review."""

    goal: str
    results: str
    lessons: list[Lesson]
    next_steps: list[NextStep]

    source_trace_id: str | None = None
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    suggested_prompt_patch: str | None = None
    suggested_eval_test: str | None = None
    lesson_record_for_memory: dict[str, Any] | None = None

    # v0.2.0 fields (all optional with defaults for backward compatibility).
    mode: AARMode = "standard"
    severity: Severity = "moderate"
    profile_pattern: AARProfilePattern = "indeterminate"
    gap_score: float = Field(default=0.5, ge=0.0, le=1.0)
    trace_quality_audit: TraceQualityAudit | None = None
    lesson_groundedness_audit: LessonGroundednessAudit | None = None
    baseline: BaselineComparison | None = None
    composition_handoff: ComposedPatternHandoff | None = None
    attached_playbooks: list[AttachedPlaybook] = Field(default_factory=list)
    run_id: str | None = None
    cost_usd: float = Field(default=0.0, ge=0.0)
    tokens_total: int = Field(default=0, ge=0)
    tokens_input: int = Field(default=0, ge=0)
    tokens_output: int = Field(default=0, ge=0)
    llm_calls: int = Field(default=0, ge=0)
    elapsed_ms: float = Field(default=0.0, ge=0.0)
    injection_detected: bool = False

    def to_markdown(self) -> str:
        """Render the AAR as a markdown document."""
        out: list[str] = []
        out.append("# After-Action Review\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.run_id:
            out.append(f"_Run id: `{self.run_id}`_\n")
        if self.generator_model:
            out.append(f"_Model: {self.generator_model}_\n")
        out.append(f"_Mode: **{self.mode}**_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
        out.append(f"_Gap score: {self.gap_score:.2f} (severity: {self.severity})_\n")
        out.append(f"_Profile pattern: **{self.profile_pattern}**_\n")
        if self.llm_calls or self.cost_usd:
            out.append(
                f"_Resources: {self.llm_calls} LLM call(s), {self.tokens_total} tokens, "
                f"${self.cost_usd:.4f}, {self.elapsed_ms:.0f}ms_\n"
            )

        out.append("\n## 1. Goal — What did we want to accomplish?\n")
        out.append(self.goal + "\n")
        out.append("\n## 2. Results — What did we actually do?\n")
        out.append(self.results + "\n")
        out.append("\n## 3. Lessons — Why was there a difference?\n")
        for i, lesson in enumerate(self.lessons, 1):
            out.append(f"\n### Lesson {i}: {lesson.pattern}\n")
            out.append(f"- **What:** {lesson.description}\n")
            out.append(f"- **Root cause:** {lesson.root_cause}\n")
            out.append(f"- **Framework anchor:** {lesson.framework_anchor}\n")
            if lesson.cross_pattern_links:
                out.append(f"- **Cross-pattern links:** {', '.join(lesson.cross_pattern_links)}\n")
        out.append("\n## 4. Next Steps — What will we do differently?\n")
        for i, step in enumerate(self.next_steps, 1):
            out.append(f"\n### Step {i}: {step.intervention_type}\n")
            out.append(f"- **What:** {step.description}\n")
            out.append(f"- **Implementation:** {step.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {step.estimated_impact}\n")
            if step.rationale:
                out.append(f"- **Rationale:** {step.rationale}\n")

        if self.trace_quality_audit:
            tq = self.trace_quality_audit
            out.append("\n## Trace Quality Audit (Forensic)\n")
            out.append(
                f"- step_count: {tq.step_count}\n"
                f"- tool_call_count: {tq.tool_call_count}\n"
                f"- decision_count: {tq.decision_count}\n"
                f"- observation_count: {tq.observation_count}\n"
                f"- has_cost: {tq.has_cost}\n"
                f"- has_latency: {tq.has_latency}\n"
                f"- has_retry_count: {tq.has_retry_count}\n"
                f"- completeness_estimate: {tq.completeness_estimate:.2f}\n"
            )
            if tq.explanation:
                out.append(f"- {tq.explanation}\n")

        if self.lesson_groundedness_audit:
            lg = self.lesson_groundedness_audit
            out.append("\n## Lesson Groundedness Audit (Forensic)\n")
            out.append(
                f"- grounded_lesson_count: {lg.grounded_lesson_count}\n"
                f"- ungrounded_lesson_count: {lg.ungrounded_lesson_count}\n"
                f"- lessons_with_framework_anchor: {lg.lessons_with_framework_anchor}\n"
                f"- lessons_with_cross_pattern_links: {lg.lessons_with_cross_pattern_links}\n"
                f"- groundedness_estimate: {lg.groundedness_estimate:.2f}\n"
            )
            if lg.explanation:
                out.append(f"- {lg.explanation}\n")

        if self.suggested_prompt_patch:
            out.append("\n---\n## Suggested Prompt Patch\n```\n")
            out.append(self.suggested_prompt_patch)
            out.append("\n```\n")
        if self.suggested_eval_test:
            out.append("\n## Suggested Eval Test\n```python\n")
            out.append(self.suggested_eval_test)
            out.append("\n```\n")

        if self.attached_playbooks:
            out.append("\n## Attached Playbooks\n")
            for pb in self.attached_playbooks:
                out.append(
                    f"\n### {pb.title} _(profile={pb.profile}, failure_mode={pb.failure_mode})_\n"
                )
                for j, pb_step in enumerate(pb.steps, 1):
                    out.append(f"{j}. {pb_step}\n")

        if self.composition_handoff and (
            self.composition_handoff.downstream_patterns
            or self.composition_handoff.upstream_patterns
        ):
            out.append("\n## Composition Handoff\n")
            ch = self.composition_handoff
            if ch.upstream_patterns:
                out.append(f"- **Upstream:** {', '.join(f'`{p}`' for p in ch.upstream_patterns)}\n")
            if ch.downstream_patterns:
                out.append(
                    f"- **Recommended downstream:** "
                    f"{', '.join(f'`{p}`' for p in ch.downstream_patterns)}\n"
                )

        return "".join(out)
