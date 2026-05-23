"""agentcity.mcgregor — Douglas McGregor's Theory X / Theory Y framework
applied to orchestrator-agent oversight design.

Theory X = tight oversight (every step approved). Theory Y = loose
oversight (broad goals + autonomy). Hybrid = per-step risk-based choice.
The right mode depends on TASK PROPERTIES, not on universal preference.

The detector reads an orchestrator-agent interaction trace + the task
properties (risk, complexity, reversibility, regulatory exposure, agent
capability) and reports the observed mode, the optimal mode, and how
mismatched they are.

Quick start:

    from agentcity.mcgregor import (
        OrchestratorModeDetector,
        OrchestratorTrace,
        OrchestratorStep,
        TaskProperties,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = OrchestratorTrace(
        trace_id="ci-runner-001",
        task="Run the test suite on every PR and report results.",
        sub_agents=["runner-1"],
        task_properties=TaskProperties(
            risk_level="low",
            complexity="routine",
            reversibility="reversible",
            agent_capability="proven",
        ),
        steps=[...],
        outcome="Each test run required orchestrator pre-approval; 5x slower than needed.",
        success=True,
    )
    detection = OrchestratorModeDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
"""

from .generator import LLMClient, OrchestratorModeDetector
from .schema import (
    MODES,
    ModeIndicators,
    OrchestratorIntervention,
    OrchestratorModeDetection,
    OrchestratorStep,
    OrchestratorTrace,
    TaskProperties,
)

__all__ = [
    "OrchestratorModeDetector",
    "LLMClient",
    "OrchestratorTrace",
    "OrchestratorStep",
    "TaskProperties",
    "ModeIndicators",
    "OrchestratorIntervention",
    "OrchestratorModeDetection",
    "MODES",
]

__version__ = "0.1.0"
