"""agentcity.smart_goal -- Doran SMART criteria (Specific, Measurable,
Achievable, Relevant, Time-bound) applied to AI agent goal-setting.

Anchored in Doran 1981. Generative pattern: takes a vague goal and
produces a structured SMART spec the agent holds itself accountable to.

Three pipeline modes with v0.2.0 production infrastructure.
Backward-compatible: ``SMARTGoalGenerator`` aliased to
``SMARTGoalAnalyzer``.
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    SMART_GOAL_COMPOSITION,
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
    SMARTGoalAnalyzer,
    SMARTGoalAnalyzerAsync,
    SMARTGoalGenerator,
)
from .prompts import (
    FORENSIC_CRITERIA_COMPLETENESS_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_MEASUREMENT_RIGOR_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    SMART_GENERATION_PROMPT,
    SMART_SYSTEM_PROMPT,
    STANDARD_SMART_GENERATION_PROMPT,
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    SEVERITY_ORDER,
    SMART_CRITERIA,
    SMART_GOAL_MODES,
    SMART_GOAL_PROFILE_PATTERNS,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    CriteriaCompletenessAudit,
    EffortEstimate,
    GoalRequest,
    InterventionType,
    KillCriterion,
    MeasurementRigorAudit,
    Severity,
    SMARTCriterion,
    SMARTGoal,
    SmartGoalIntervention,
    SmartGoalMode,
    SmartGoalProfilePattern,
    SuccessMetric,
    severity_from_smart_score,
)

__all__ = [
    "SMARTGoalAnalyzer",
    "SMARTGoalAnalyzerAsync",
    "SMARTGoalGenerator",
    "LLMClient",
    "AsyncLLMClient",
    "GoalRequest",
    "SMARTCriterion",
    "SuccessMetric",
    "KillCriterion",
    "CriteriaCompletenessAudit",
    "MeasurementRigorAudit",
    "SmartGoalIntervention",
    "AttachedPlaybook",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "SMARTGoal",
    "SmartGoalMode",
    "SmartGoalProfilePattern",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "SMART_CRITERIA",
    "SMART_GOAL_MODES",
    "SMART_GOAL_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_smart_score",
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    "SMART_GOAL_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    "SMART_SYSTEM_PROMPT",
    "SMART_GENERATION_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_SMART_GENERATION_PROMPT",
    "FORENSIC_CRITERIA_COMPLETENESS_PROMPT",
    "FORENSIC_MEASUREMENT_RIGOR_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "assemble_prompt",
]

__version__ = "0.2.0"
