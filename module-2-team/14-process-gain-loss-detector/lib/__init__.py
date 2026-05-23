"""agentcity.process_gain_loss — Steiner / Robbins-&-Judge process-gain
and process-loss diagnostic for multi-agent systems.

When you assemble N agents to do a task, does the team output beat what
the best single agent could have produced? Often not. The detector
quantifies the gap and identifies which of the six canonical factors
(coordination cost, social loafing, groupthink, handoff loss, context
dilution, consensus dilution) is doing the most damage.

Quick start:

    from agentcity.process_gain_loss import (
        ProcessGainLossDetector,
        ProcessTrace,
        IndividualBaseline,
        TeamResult,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = ProcessTrace(
        task="Write a one-page research summary on prompt-injection defenses.",
        individual_baselines=[
            IndividualBaseline(agent_name="solo-claude", output_summary="...", quality_score=0.85),
            IndividualBaseline(agent_name="solo-gpt", output_summary="...", quality_score=0.78),
        ],
        team_result=TeamResult(
            agents=["lead", "researcher", "writer", "reviewer", "fact-checker"],
            output_summary="...",
            quality_score=0.62,
        ),
        interaction_log="...",
        outcome="Team underperformed both single-agent baselines.",
        success=True,
    )
    detection = ProcessGainLossDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
"""

from .generator import LLMClient, ProcessGainLossDetector
from .schema import (
    PROCESS_FACTORS,
    IndividualBaseline,
    ProcessFactorEvidence,
    ProcessGainLossDetection,
    ProcessIntervention,
    ProcessTrace,
    TeamResult,
)

__all__ = [
    "ProcessGainLossDetector",
    "LLMClient",
    "ProcessTrace",
    "IndividualBaseline",
    "TeamResult",
    "ProcessFactorEvidence",
    "ProcessIntervention",
    "ProcessGainLossDetection",
    "PROCESS_FACTORS",
]

__version__ = "0.1.0"
