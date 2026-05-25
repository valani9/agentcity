"""vstack.vroom_expectancy -- Victor Vroom's E*I*V motivation
calculus applied to AI agents.

Anchored in:
  - Vroom (1964) *Work and Motivation*.
  - Porter & Lawler (1968) *Managerial Attitudes and Performance*.
  - Bandura (1977) Self-Efficacy.
  - Eccles & Wigfield (2002) Motivational Beliefs.
  - Locke & Latham (1990) *A Theory of Goal Setting*.
  - Kanfer, Frese & Johnson (2017) Motivation Related to Work.
  - Casper et al. (2023) Open Problems in RLHF.

Three pipeline modes (quick / standard / forensic) with full v0.2.0
production infrastructure (run-id correlation, token/cost telemetry,
input guards, async mirror).

Backward-compatible: ``VroomExpectancyCalculator`` remains exported as
an alias for ``VroomExpectancyAnalyzer``.

Quick start
-----------

    from vstack.vroom_expectancy import (
        VroomExpectancyAnalyzer,
        AgentExpectancyTrace,
    )
    from vstack.aar import AnthropicClient

    trace = AgentExpectancyTrace(
        agent_id="research-agent",
        task="Debug the entire codebase.",
        task_class="code_generation",
        system_prompt="Find all bugs across all files. No one will review carefully.",
        observed_behaviors=["Agent produced superficial output for 5 files, then quit."],
        effort_signals=["Quit after 5 files of 200."],
        outcome="Bugs unfound.",
        success=False,
    )
    detection = VroomExpectancyAnalyzer(
        AnthropicClient(), mode="forensic"
    ).run(trace)
    print(detection.to_markdown())

CLI
---

    vstack-vroom analyze --trace trace.json --mode forensic
    vstack-vroom playbooks
    vstack-vroom compose
    vstack-vroom schema --target trace
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    VROOM_COMPOSITION,
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
    LLMClient,
    VroomExpectancyAnalyzer,
    VroomExpectancyAnalyzerAsync,
    VroomExpectancyCalculator,  # legacy alias
)
from .prompts import (
    FORENSIC_EIV_INTERACTION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_PROMPT_SIGNAL_PROMPT,
    INTERVENTIONS_PROMPT,  # legacy
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_TERMS_PROMPT,
    TERMS_PROMPT,  # legacy
    VROOM_SYSTEM_PROMPT,
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    SEVERITY_ORDER,
    SIGNAL_CATEGORIES,
    TASK_CLASSES,
    VROOM_MODES,
    VROOM_PROFILE_PATTERNS,
    VROOM_TERMS,
    AgentExpectancyTrace,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    EffortEstimate,
    EIVInteractionAudit,
    InterventionType,
    PromptSignalItem,
    Severity,
    SignalCategory,
    TaskClass,
    VroomDetection,
    VroomIntervention,
    VroomMode,
    VroomProfilePattern,
    VroomTerm,
    VroomTermOrNone,
    VroomTermScore,
    severity_from_motivation,
)

__all__ = [
    # Analyzer entry points
    "VroomExpectancyAnalyzer",
    "VroomExpectancyAnalyzerAsync",
    "VroomExpectancyCalculator",  # legacy alias
    "LLMClient",
    "AsyncLLMClient",
    # Schema -- input
    "AgentExpectancyTrace",
    # Schema -- output
    "VroomTermScore",
    "PromptSignalItem",
    "EIVInteractionAudit",
    "VroomIntervention",
    "VroomDetection",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Literal enums + constants
    "VroomTerm",
    "VroomTermOrNone",
    "VroomMode",
    "VroomProfilePattern",
    "TaskClass",
    "SignalCategory",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "VROOM_TERMS",
    "VROOM_MODES",
    "VROOM_PROFILE_PATTERNS",
    "TASK_CLASSES",
    "SIGNAL_CATEGORIES",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_motivation",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "VROOM_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # Prompts
    "VROOM_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_TERMS_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_PROMPT_SIGNAL_PROMPT",
    "FORENSIC_EIV_INTERACTION_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "TERMS_PROMPT",  # legacy
    "INTERVENTIONS_PROMPT",  # legacy
    "assemble_prompt",
]

__version__ = "0.2.0"
