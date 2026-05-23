"""agentcity.devils_advocate — Critical-Evaluator / Devil's Advocate
role-separation diagnostic for single-agent traces.

When the same agent both plans and judges its own output, self-confirmation
is almost guaranteed. This detector measures the four phases
(plan / execute / self-evaluate / external-critique) and recommends
concrete role-separation interventions.

Grounded in Janis on groupthink (1972) and the broader literature on
structured dissent.

Quick start:

    from agentcity.devils_advocate import (
        RoleSeparationDetector,
        SingleAgentTrace,
        RoleStep,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = SingleAgentTrace(
        agent_id="planner-001",
        task="Decide which database to use.",
        steps=[...],
        outcome="Agent approved its own plan without external review.",
        success=False,
    )
    detection = RoleSeparationDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
"""

from .generator import LLMClient, RoleSeparationDetector
from .schema import (
    PHASES,
    PhaseEvidence,
    RoleSeparationDetection,
    RoleSeparationIntervention,
    RoleStep,
    SingleAgentTrace,
)

__all__ = [
    "RoleSeparationDetector",
    "LLMClient",
    "SingleAgentTrace",
    "RoleStep",
    "PhaseEvidence",
    "RoleSeparationIntervention",
    "RoleSeparationDetection",
    "PHASES",
]

__version__ = "0.1.0"
