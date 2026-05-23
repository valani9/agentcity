"""agentcity.yerkes_dodson — Yerkes & Dodson's inverted-U performance
curve applied to AI agent workload-pressure design.

Performance vs pressure has a U-shape:
  - Under no pressure        → wandering / drifting
  - Under moderate pressure  → focused (optimal)
  - Under high pressure      → corner-cutting / freezing / hallucinating

The detector reads an agent's pressure inputs (deadline, budget, retry
cap, error visibility, task complexity) + observed behaviors, and
identifies whether the agent is on the curve's optimum or has fallen
off either side.

Quick start:

    from agentcity.yerkes_dodson import (
        WorkloadDetector,
        AgentPerformanceTrace,
        PressureInputs,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentPerformanceTrace(
        agent_id="research-agent-001",
        task="Compile a 1-page summary on prompt injection defenses.",
        pressure=PressureInputs(
            deadline_pressure="absurd",
            budget_pressure="absurd",
            task_complexity="complex",
        ),
        observed_behaviors=[
            "Agent cited 3 papers without verifying they exist.",
            "Agent shipped without running its own check.",
        ],
        outcome="Summary contains 2 fabricated citations.",
        success=False,
    )
    detection = WorkloadDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
    # observed_zone: over_pressure
    # failure_mode: hallucinating
    # intervention #1: loosen_deadline / loosen_budget
"""

from .generator import LLMClient, WorkloadDetector
from .schema import (
    AgentPerformanceTrace,
    PressureInputs,
    WorkloadDetection,
    WorkloadIntervention,
    WorkloadZoneEvidence,
)

__all__ = [
    "WorkloadDetector",
    "LLMClient",
    "AgentPerformanceTrace",
    "PressureInputs",
    "WorkloadZoneEvidence",
    "WorkloadIntervention",
    "WorkloadDetection",
]

__version__ = "0.1.0"
