"""
agentcity.grpi — Beckhard's GRPI model (Goals / Roles / Processes /
Interactions) applied to multi-agent setup.

Unlike most AgentCity patterns, this one is GENERATIVE: it produces a
Working Agreement contract from a team setup request, instead of
diagnosing a completed trace.

Quick start:

    from agentcity.grpi import (
        GRPIWorkingAgreementGenerator,
        TeamSetupRequest,
        AgentRole,
    )
    from agentcity.aar.clients import AnthropicClient

    request = TeamSetupRequest(
        task="Design and launch a Q3 marketing campaign within 14 days.",
        agents=[
            AgentRole(name="researcher", description="Market research."),
            AgentRole(name="strategist", description="Channel selection."),
            AgentRole(name="critic", description="Devil's-advocate review."),
        ],
        constraints=["Budget $20K", "1 mandatory dissent round per decision"],
    )
    agreement = GRPIWorkingAgreementGenerator(AnthropicClient()).generate(request)
    print(agreement.to_markdown())
    print(agreement.to_orchestrator_preamble())

See README.md for the full pattern explanation.
"""

from .generator import GRPIWorkingAgreementGenerator, LLMClient
from .schema import (
    DIMENSIONS,
    AgentRole,
    GoalsSection,
    InteractionsSection,
    ProcessesSection,
    RoleAssignment,
    RolesSection,
    TeamSetupRequest,
    WorkingAgreement,
)

__all__ = [
    "GRPIWorkingAgreementGenerator",
    "LLMClient",
    "AgentRole",
    "TeamSetupRequest",
    "WorkingAgreement",
    "GoalsSection",
    "RoleAssignment",
    "RolesSection",
    "ProcessesSection",
    "InteractionsSection",
    "DIMENSIONS",
]

__version__ = "0.1.0"
