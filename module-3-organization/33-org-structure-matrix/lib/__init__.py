"""agentcity.org_structure — Org-Structure Matrix Analyzer for AI agent
crews. Third Module 3 (organizational) pattern.

The six structural dimensions: specialization, formalization,
centralization, hierarchy, span_of_control, departmentalization. Each
task class implies a different target structure profile; the diagnostic
identifies where the crew's observed structure fails to match.

Where Schein's Iceberg (#31) measures *coherence* and Robbins/Judge's
7-Characteristics (#32) measures *cultural shape*, this pattern measures
*structural fit*. The three compose into the Module 3 organizational
diagnostic stack.

Quick start:

    from agentcity.org_structure import (
        StructureMatrixAnalyzer,
        CrewStructureTrace,
        AgentRole,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = CrewStructureTrace(
        crew_id="incident-response-crew",
        task="Investigate latency spike across the order pipeline.",
        task_class="incident_response",
        agents=[
            AgentRole(agent_id="a1", role_name="generalist"),
            AgentRole(agent_id="a2", role_name="generalist"),
            AgentRole(agent_id="a3", role_name="generalist"),
        ],
        observed_behaviors=[
            "No agent owns the incident; all three propose ideas in parallel.",
            "Decisions are made by majority vote, not by an incident commander.",
        ],
        outcome="Investigation diverges; MTTR exceeds SLO by 3x.",
        success=False,
    )
    analysis = StructureMatrixAnalyzer(AnthropicClient()).run(trace)
    print(analysis.to_markdown())
    # archetype: flat-peer; gap: centralization; intervention: add_supervisor_layer
"""

from .generator import LLMClient, StructureMatrixAnalyzer
from .schema import (
    STRUCTURE_DIMENSIONS,
    AgentRole,
    CrewStructureTrace,
    StructureAnalysis,
    StructureDimensionScore,
    StructureIntervention,
)

__all__ = [
    "StructureMatrixAnalyzer",
    "LLMClient",
    "AgentRole",
    "CrewStructureTrace",
    "StructureAnalysis",
    "StructureDimensionScore",
    "StructureIntervention",
    "STRUCTURE_DIMENSIONS",
]

__version__ = "0.0.12"
