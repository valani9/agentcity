"""vstack.sdt_reward -- Deci & Ryan's Self-Determination Theory
applied to AI agent reward shaping.

Anchored in:
  - Deci & Ryan (1985, 2017) Self-Determination Theory.
  - Ryan & Deci (2000) SDT and intrinsic motivation.
  - Deci (1971) overjustification effect.
  - Pink (2009) *Drive* (autonomy/mastery/purpose synthesis).
  - Gagne & Deci (2005) SDT and work motivation.
  - Casper et al. (2023) Open Problems in RLHF.
  - Bai et al. (2022) Constitutional AI.

Three basic psychological needs: AUTONOMY, COMPETENCE, RELATEDNESS.

Three pipeline modes (quick / standard / forensic) with full v0.2.0
production infrastructure.

Backward-compatible: ``SDTRewardDetector`` remains exported as alias
of ``SDTRewardAnalyzer``.

Quick start
-----------

    from vstack.sdt_reward import (
        SDTRewardAnalyzer,
        AgentSDTTrace,
    )
    from vstack.aar import AnthropicClient

    trace = AgentSDTTrace(
        agent_id="research-agent",
        task="Explore design space for new feature.",
        task_class="research_exploration",
        system_prompt="You MUST follow rules. You will be RATED on accuracy.",
        extrinsic_signals=["low ratings flagged", "cost cap < 5 calls"],
        observed_behaviors=[
            "Agent restated established patterns.",
            "Agent refused to deviate.",
        ],
        outcome="Output is rigid; no novel directions surfaced.",
        success=False,
    )
    detection = SDTRewardAnalyzer(
        AnthropicClient(), mode="forensic"
    ).run(trace)
    print(detection.to_markdown())

CLI
---

    vstack-sdt analyze --trace trace.json --mode forensic
    vstack-sdt playbooks
    vstack-sdt compose
    vstack-sdt schema --target trace
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    SDT_COMPOSITION,
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
    SDTRewardAnalyzer,
    SDTRewardAnalyzerAsync,
    SDTRewardDetector,  # legacy alias
)
from .prompts import (
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_OVERJUSTIFICATION_PROMPT,
    FORENSIC_REWARD_SHAPING_PROMPT,
    INTERVENTIONS_PROMPT,  # legacy
    NEEDS_PROMPT,  # legacy
    QUICK_DIAGNOSTIC_PROMPT,
    SDT_SYSTEM_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_NEEDS_PROMPT,
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    REWARD_SHAPING_CATEGORIES,
    SDT_MODES,
    SDT_NEEDS,
    SDT_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    TASK_CLASSES,
    AgentSDTTrace,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    EffortEstimate,
    InterventionType,
    NeedScore,
    OverjustificationAudit,
    RewardShapingCategory,
    RewardShapingItem,
    SDTDetection,
    SDTIntervention,
    SDTMode,
    SDTNeed,
    SDTNeedOrNone,
    SDTProfilePattern,
    Severity,
    TaskClass,
    severity_from_undermining,
)

__all__ = [
    # Analyzer entry points
    "SDTRewardAnalyzer",
    "SDTRewardAnalyzerAsync",
    "SDTRewardDetector",  # legacy alias
    "LLMClient",
    "AsyncLLMClient",
    # Schema -- input
    "AgentSDTTrace",
    # Schema -- output
    "NeedScore",
    "RewardShapingItem",
    "OverjustificationAudit",
    "SDTIntervention",
    "SDTDetection",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Literal enums + constants
    "SDTNeed",
    "SDTNeedOrNone",
    "SDTMode",
    "SDTProfilePattern",
    "TaskClass",
    "Severity",
    "InterventionType",
    "RewardShapingCategory",
    "EffortEstimate",
    "SDT_NEEDS",
    "SDT_MODES",
    "SDT_PROFILE_PATTERNS",
    "TASK_CLASSES",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "REWARD_SHAPING_CATEGORIES",
    "severity_from_undermining",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "SDT_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # Prompts
    "SDT_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_NEEDS_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_REWARD_SHAPING_PROMPT",
    "FORENSIC_OVERJUSTIFICATION_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "NEEDS_PROMPT",  # legacy
    "INTERVENTIONS_PROMPT",  # legacy
    "assemble_prompt",
]

__version__ = "0.2.0"
