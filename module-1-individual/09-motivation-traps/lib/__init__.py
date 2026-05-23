"""agentcity.motivation_traps — Saxberg's 4 Motivation Traps applied
to AI agents.

The four traps: VALUES (task seen as not worth doing), SELF_EFFICACY
(belief in inability to succeed), EMOTIONS (anxiety/frustration blocking
engagement), ATTRIBUTION (blaming wrong cause for failure). Each trap
requires a different intervention; generic "try harder" prompts are
ineffective.

Quick start:

    from agentcity.motivation_traps import (
        MotivationTrapsDetector,
        AgentMotivationTrace,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentMotivationTrace(
        agent_id="research-agent",
        task="Investigate latency spike.",
        task_class="research",
        observed_behaviors=[
            "Agent quit after one failed query.",
            "Repeated the same query format on retry.",
        ],
        self_reports=["I'm not sure I can find this answer.", "Maybe the data is wrong."],
        abandonment_signal="refused after one attempt",
        outcome="Agent gave up; root cause unfound.",
        success=False,
    )
    detection = MotivationTrapsDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
    # dominant_trap: self_efficacy; intervention: scaffold_subtasks
"""

from .generator import LLMClient, MotivationTrapsDetector
from .schema import (
    MOTIVATION_TRAPS,
    AgentMotivationTrace,
    MotivationDetection,
    MotivationIntervention,
    TrapEvidence,
)

__all__ = [
    "MotivationTrapsDetector",
    "LLMClient",
    "AgentMotivationTrace",
    "MotivationDetection",
    "MotivationIntervention",
    "TrapEvidence",
    "MOTIVATION_TRAPS",
]

__version__ = "0.0.12"
