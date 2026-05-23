"""agentcity.vroom_expectancy — Victor Vroom's E × I × V motivation
calculus applied to AI agents.

Motivation = Expectancy × Instrumentality × Valence. The product is
MULTIPLICATIVE — if any term approaches zero, motivation collapses
regardless of the others. The diagnostic identifies the bottleneck
term and proposes interventions to lift it.

For AI agents:
  - EXPECTANCY: scaffolding adequacy, task scope sanity
  - INSTRUMENTALITY: "will my output matter" signal in the context
  - VALENCE: agent's valuation of the outcome (purpose, user benefit,
              avoidance of low-value boilerplate)

Quick start:

    from agentcity.vroom_expectancy import (
        VroomExpectancyCalculator,
        AgentExpectancyTrace,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentExpectancyTrace(
        agent_id="research-agent",
        task="Debug the entire codebase.",
        task_class="code_generation",
        system_prompt="Find all bugs across all files. No one will review your output carefully.",
        observed_behaviors=[
            "Agent produced superficial output for 5 files, then quit.",
        ],
        effort_signals=["Quit after 5 files of 200."],
        outcome="Bugs unfound.",
        success=False,
    )
    detection = VroomExpectancyCalculator(AnthropicClient()).run(trace)
    print(detection.to_markdown())
    # bottleneck_term: expectancy (sprawling unscaffolded task);
    # intervention: scaffold_subtasks
"""

from .generator import LLMClient, VroomExpectancyCalculator
from .schema import (
    VROOM_TERMS,
    AgentExpectancyTrace,
    VroomDetection,
    VroomIntervention,
    VroomTermScore,
)

__all__ = [
    "VroomExpectancyCalculator",
    "LLMClient",
    "AgentExpectancyTrace",
    "VroomTermScore",
    "VroomIntervention",
    "VroomDetection",
    "VROOM_TERMS",
]

__version__ = "0.0.14"
