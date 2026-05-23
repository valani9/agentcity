"""agentcity.grpi -- Beckhard's GRPI (Goals/Roles/Processes/Interactions)
applied to multi-agent setup.

Generates a Working Agreement document from a team setup request.

Anchored in:
  - Beckhard (1972) canonical GRPI.
  - Rubin-Plovnick-Fry (1977) task-oriented team development.
  - Hackman (2002) *Leading Teams*.
  - Salas et al. (2018) Science of Team Performance.
  - Lencioni (2002) Five Dysfunctions.
  - Edmondson (1999) psychological safety.
  - Wang et al. (2023) Cooperative LLM Agents.

Three pipeline modes (quick / standard / forensic) with full v0.2.0
production infrastructure.

Backward-compatible: ``GRPIWorkingAgreementGenerator`` remains exported
as alias of ``GRPIWorkingAgreementAnalyzer``.

Quick start
-----------

    from agentcity.grpi import (
        GRPIWorkingAgreementAnalyzer,
        TeamSetupRequest,
        AgentRole,
    )
    from agentcity.aar import AnthropicClient

    request = TeamSetupRequest(
        task="Design and launch a Q3 marketing campaign within 14 days.",
        agents=[
            AgentRole(name="researcher", description="Market research."),
            AgentRole(name="strategist", description="Channel selection."),
            AgentRole(name="critic", description="Devil's-advocate review."),
        ],
        constraints=["Budget $20K", "1 mandatory dissent round per decision"],
    )
    agreement = GRPIWorkingAgreementAnalyzer(
        AnthropicClient(), mode="forensic"
    ).run(request)
    print(agreement.to_markdown())

CLI
---

    agentcity-grpi generate --request request.json --mode forensic
    agentcity-grpi playbooks
    agentcity-grpi compose
    agentcity-grpi schema --target request
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    GRPI_COMPOSITION,
    recommended_downstream,
    recommended_upstream,
)
from ._playbooks import (
    PLAYBOOKS,
    all_playbook_keys,
    find_playbook,
    find_playbook_for_intervention,
)
from .generator import (
    AsyncLLMClient,
    GRPIWorkingAgreementAnalyzer,
    GRPIWorkingAgreementAnalyzerAsync,
    GRPIWorkingAgreementGenerator,  # legacy alias
    LLMClient,
)
from .prompts import (
    FORENSIC_DYSFUNCTION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_ROLE_FIT_PROMPT,
    GENERATION_PROMPT,  # legacy
    GRPI_GENERATION_PROMPT,  # legacy
    GRPI_SYSTEM_PROMPT,
    QUICK_GENERATION_PROMPT,
    STANDARD_GENERATION_PROMPT,
    STANDARD_REFINEMENT_PROMPT,
    assemble_prompt,
)
from .schema import (
    DIMENSIONS,
    GRPI_MODES,
    GRPI_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    AgentRole,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    DysfunctionPreventionAudit,
    EffortEstimate,
    GoalsSection,
    GRPIDimension,
    GRPIIntervention,
    GRPIMode,
    GRPIProfilePattern,
    InteractionsSection,
    ProcessesSection,
    RoleAssignment,
    RoleFitAudit,
    RolesSection,
    Severity,
    TeamSetupRequest,
    WorkingAgreement,
    severity_from_completeness,
)

__all__ = [
    # Analyzer entry points
    "GRPIWorkingAgreementAnalyzer",
    "GRPIWorkingAgreementAnalyzerAsync",
    "GRPIWorkingAgreementGenerator",  # legacy alias
    "LLMClient",
    "AsyncLLMClient",
    # Schema -- input
    "TeamSetupRequest",
    "AgentRole",
    # Schema -- output
    "WorkingAgreement",
    "GoalsSection",
    "RolesSection",
    "RoleAssignment",
    "ProcessesSection",
    "InteractionsSection",
    "RoleFitAudit",
    "DysfunctionPreventionAudit",
    "GRPIIntervention",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Literal enums + constants
    "GRPIMode",
    "GRPIProfilePattern",
    "GRPIDimension",
    "Severity",
    "EffortEstimate",
    "DIMENSIONS",
    "GRPI_MODES",
    "GRPI_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "severity_from_completeness",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "GRPI_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # Prompts
    "GRPI_SYSTEM_PROMPT",
    "QUICK_GENERATION_PROMPT",
    "STANDARD_GENERATION_PROMPT",
    "STANDARD_REFINEMENT_PROMPT",
    "FORENSIC_ROLE_FIT_PROMPT",
    "FORENSIC_DYSFUNCTION_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "GRPI_GENERATION_PROMPT",  # legacy
    "GENERATION_PROMPT",  # legacy
    "assemble_prompt",
]

__version__ = "0.2.0"
