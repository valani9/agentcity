"""
Schema for the AAR (After-Action Review) Generator.

The Wharton 4-step AAR structure:
  1. Goal       - What did we want to accomplish?
  2. Results    - What did we actually do?
  3. Lessons    - Why were there differences between #1 and #2?
  4. Next Steps - What will we do differently / repeat?

Inputs and outputs are defined as Pydantic models so they serialize cleanly
to JSON for storage in observability tools, agent memory systems, or
downstream eval pipelines.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Timezone-aware UTC now; replaces the deprecated `datetime.utcnow`."""
    return datetime.now(timezone.utc)


# --- Input: a structured agent run trace -----------------------------------


class TraceStep(BaseModel):
    """One step in an agent's execution trace.

    Mirrors the OpenTelemetry agent-trace span schema closely so that traces
    captured by LangSmith, Braintrust, Phoenix, Langfuse, or the Claude Agent
    SDK can be ingested with minimal transformation.
    """

    timestamp: datetime
    type: Literal["tool_call", "message", "decision", "observation", "thought"]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_step_id: str | None = None
    step_id: str | None = None


class AgentTrace(BaseModel):
    """A full agent run, ready to be reviewed by the AAR Generator.

    The minimum useful trace has a stated goal, a sequence of steps, and a
    binary success signal. Richer traces (cost, latency, retry counts,
    tool-error details) produce richer AARs.
    """

    agent_id: str | None = None
    agent_framework: str | None = None  # e.g. "claude-agent-sdk", "langgraph"
    goal: str
    steps: list[TraceStep]
    outcome: str
    success: bool
    cost_usd: float | None = None
    latency_seconds: float | None = None
    retry_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Output: the Wharton 4-step AAR ---------------------------------------


class Lesson(BaseModel):
    """One named lesson derived from the gap between Goal and Results.

    Each lesson cross-links to the OB framework that explains the failure
    (e.g. "Lencioni: lack of commitment" or "Kahneman: anchoring bias"),
    making the AAR connect to the broader AgentCity pattern library.
    """

    pattern: str  # short name of the failure pattern, e.g. "anchored-on-first-hypothesis"
    description: str  # what happened, plainly
    root_cause: str  # the underlying mechanism
    framework_anchor: str  # which OB framework explains this; e.g. "Kahneman 1974 - anchoring bias"
    cross_pattern_links: list[str] = Field(
        default_factory=list,
        description="Other AgentCity patterns this lesson connects to (e.g. '#17 lencioni-diagnostic')",
    )


class NextStep(BaseModel):
    """A concrete intervention to apply before the next run."""

    intervention_type: Literal[
        "prompt_patch",
        "tool_addition",
        "tool_removal",
        "scaffold_change",
        "new_eval",
        "human_review",
        "memory_injection",
    ]
    description: str
    suggested_implementation: str  # concrete code / prompt-edit / spec
    estimated_impact: Literal["high", "medium", "low"] = "medium"
    rationale: str = ""


class AAR(BaseModel):
    """The full Wharton 4-step After-Action Review."""

    # Wharton's 4 steps
    goal: str  # 1. What did we want to accomplish?
    results: str  # 2. What did we do?
    lessons: list[Lesson]  # 3. Why the difference?
    next_steps: list[NextStep]  # 4. What for better outcome?

    # Metadata
    source_trace_id: str | None = None
    generated_at: datetime = Field(default_factory=_utcnow)
    generator_model: str | None = None
    success: bool

    # Convenience fields derived during generation
    suggested_prompt_patch: str | None = None
    suggested_eval_test: str | None = None
    lesson_record_for_memory: dict[str, Any] | None = None

    def to_markdown(self) -> str:
        """Render the AAR as a markdown document following Wharton's canonical
        4-step format. This is the artifact a human reviewer or downstream
        documentation tool can consume directly.
        """
        out: list[str] = []
        out.append(f"# After-Action Review\n")
        out.append(f"_Generated {self.generated_at.isoformat()}_\n")
        if self.generator_model:
            out.append(f"_Model: {self.generator_model}_\n")
        out.append(f"_Outcome: {'success' if self.success else 'failure'}_\n")
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
                out.append(
                    f"- **Cross-pattern links:** {', '.join(lesson.cross_pattern_links)}\n"
                )
        out.append("\n## 4. Next Steps — What will we do differently?\n")
        for i, step in enumerate(self.next_steps, 1):
            out.append(f"\n### Step {i}: {step.intervention_type}\n")
            out.append(f"- **What:** {step.description}\n")
            out.append(f"- **Implementation:** {step.suggested_implementation}\n")
            out.append(f"- **Expected impact:** {step.estimated_impact}\n")
            if step.rationale:
                out.append(f"- **Rationale:** {step.rationale}\n")
        if self.suggested_prompt_patch:
            out.append("\n---\n## Suggested Prompt Patch\n```\n")
            out.append(self.suggested_prompt_patch)
            out.append("\n```\n")
        if self.suggested_eval_test:
            out.append("\n## Suggested Eval Test\n```python\n")
            out.append(self.suggested_eval_test)
            out.append("\n```\n")
        return "".join(out)
