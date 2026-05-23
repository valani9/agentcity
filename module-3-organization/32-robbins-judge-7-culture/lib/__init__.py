"""agentcity.robbins_culture -- Robbins & Judge 7-Characteristics culture
profile applied to AI agents. Module 3 (organizational) pattern.

The seven dimensions: innovation, attention_to_detail, outcome, people,
team, aggressiveness, stability. Each task class implies a different
target profile; the diagnostic identifies where the agent's observed
profile fails to match.

Where Schein's Iceberg (#31) measures *coherence across layers*, this
pattern measures *fit to task class*.

v0.2.0 features:
  - Three pipeline modes (quick/standard/forensic)
  - Eight ScheinProfilePattern variants + 7-point Severity scale
  - Forensic Target-Profile Provenance + Per-Dimension Risk audits
  - Calibration baseline roundtrip + drift comparison
  - Cross-pattern composition manifest
  - 13 (characteristic, failure_mode) playbooks anchored to
    Robbins & Judge 2017
  - Production infra via agentcity.aar shared module

Quick start:

    from agentcity.robbins_culture import (
        CultureProfileAnalyzer,
        AgentCultureTrace,
    )
    from agentcity.aar import AnthropicClient

    trace = AgentCultureTrace(
        agent_id="research-agent-001",
        task="Explore design space for a new feature.",
        task_class="research_exploration",
        system_prompt="Be thorough; double-check every claim with citations.",
        observed_behaviors=["Agent over-cites; never proposes novel directions."],
        outcome="Output is comprehensive but stale.",
        success=False,
    )
    detection = CultureProfileAnalyzer(AnthropicClient()).run(trace)
    print(detection.to_markdown())
    # biggest_gap: innovation; profile_pattern: innovation_starved
"""

from ._calibration import (
    compare_to_baseline,
    load_baseline,
    record_baseline,
)
from ._composition import (
    ROBBINS_COMPOSITION,
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
    CultureProfileAnalyzer,
    CultureProfileAnalyzerAsync,
    CultureProfileDetector,
    LLMClient,
)
from .schema import (
    CULTURE_CHARACTERISTICS,
    ROBBINS_MODES,
    ROBBINS_PROFILE_PATTERNS,
    SEVERITY_ORDER,
    AgentCultureTrace,
    AttachedPlaybook,
    BaselineComparison,
    CharacteristicScore,
    ComposedPatternHandoff,
    CultureIntervention,
    CultureProfileDetection,
    EffortEstimate,
    InterventionType,
    PerDimensionRisk,
    RobbinsMode,
    RobbinsProfilePattern,
    Severity,
    TargetProfileProvenance,
    TaskClass,
    severity_from_misfit,
)

__all__ = [
    "AgentCultureTrace",
    "AsyncLLMClient",
    "AttachedPlaybook",
    "BaselineComparison",
    "CULTURE_CHARACTERISTICS",
    "CharacteristicScore",
    "ComposedPatternHandoff",
    "CultureIntervention",
    "CultureProfileAnalyzer",
    "CultureProfileAnalyzerAsync",
    "CultureProfileDetection",
    "CultureProfileDetector",
    "EffortEstimate",
    "InterventionType",
    "LLMClient",
    "PLAYBOOKS",
    "PerDimensionRisk",
    "ROBBINS_COMPOSITION",
    "ROBBINS_MODES",
    "ROBBINS_PROFILE_PATTERNS",
    "RobbinsMode",
    "RobbinsProfilePattern",
    "SEVERITY_ORDER",
    "Severity",
    "TargetProfileProvenance",
    "TaskClass",
    "all_playbook_keys",
    "compare_to_baseline",
    "find_playbook",
    "find_playbook_for_intervention",
    "load_baseline",
    "record_baseline",
    "recommended_downstream",
    "recommended_upstream",
    "severity_from_misfit",
]

__version__ = "0.2.0"
