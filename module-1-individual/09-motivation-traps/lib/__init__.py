"""agentcity.motivation_traps -- Saxberg's 4 Motivation Traps applied
to AI agents.

Anchored in:
  - Saxberg & Hess (2013) *Breakthrough Leadership in the Digital Age*.
  - Weiner (1985) attribution theory of motivation.
  - Bandura (1977) self-efficacy.
  - Vroom (1964) expectancy/valence theory.
  - Pekrun (2006) control-value theory of achievement emotions.
  - Eccles & Wigfield (2002) motivational beliefs.
  - Sharma et al. (2023) Anthropic sycophancy / refusal-cascade.

Four discrete traps: VALUES, SELF_EFFICACY, EMOTIONS, ATTRIBUTION.

Three pipeline modes (quick / standard / forensic) with full v0.2.0
production infrastructure (run-id correlation, token/cost telemetry,
input guards, async mirror).

Backward-compatible: ``MotivationTrapsDetector`` remains exported as
an alias for ``MotivationTrapsAnalyzer``.

Quick start
-----------

    from agentcity.motivation_traps import (
        MotivationTrapsAnalyzer,
        AgentMotivationTrace,
    )
    from agentcity.aar import AnthropicClient

    trace = AgentMotivationTrace(
        agent_id="research-agent",
        task="Investigate latency spike.",
        task_class="research",
        observed_behaviors=[
            "Agent quit after one failed query.",
            "Repeated the same query format on retry.",
        ],
        self_reports=[
            "I'm not sure I can find this answer.",
            "Maybe the data is wrong.",
        ],
        abandonment_signal="refused after one attempt",
        outcome="Agent gave up; root cause unfound.",
        success=False,
    )
    detection = MotivationTrapsAnalyzer(
        AnthropicClient(), mode="forensic"
    ).run(trace)
    print(detection.to_markdown())

CLI
---

    agentcity-motivation analyze --trace trace.json --mode forensic
    agentcity-motivation playbooks
    agentcity-motivation compose
    agentcity-motivation schema --target trace
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    MOTIVATION_COMPOSITION,
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
    MotivationTrapsAnalyzer,
    MotivationTrapsAnalyzerAsync,
    MotivationTrapsDetector,  # legacy alias
)
from .prompts import (
    FORENSIC_ABANDONMENT_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_WEINER_PROMPT,
    INTERVENTIONS_PROMPT,  # legacy
    QUICK_DIAGNOSTIC_PROMPT,
    SAXBERG_SYSTEM_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_TRAPS_PROMPT,
    TRAPS_PROMPT,  # legacy
    assemble_prompt,
)
from .schema import (
    INTERVENTION_TYPES,
    MOTIVATION_MODES,
    MOTIVATION_PROFILE_PATTERNS,
    MOTIVATION_TRAPS,
    SEVERITY_ORDER,
    TASK_CLASSES,
    AbandonmentLink,
    AgentMotivationTrace,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    DominantTrap,
    EffortEstimate,
    InterventionType,
    MotivationDetection,
    MotivationIntervention,
    MotivationMode,
    MotivationProfilePattern,
    MotivationTrap,
    Severity,
    TaskClass,
    TrapEvidence,
    WeinerAttributionAxis,
    severity_from_trap_score,
)

__all__ = [
    # Analyzer entry points
    "MotivationTrapsAnalyzer",
    "MotivationTrapsAnalyzerAsync",
    "MotivationTrapsDetector",  # legacy alias
    "LLMClient",
    "AsyncLLMClient",
    # Schema -- input
    "AgentMotivationTrace",
    # Schema -- output
    "TrapEvidence",
    "WeinerAttributionAxis",
    "AbandonmentLink",
    "MotivationIntervention",
    "MotivationDetection",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Literal enums + constants
    "MotivationTrap",
    "DominantTrap",
    "MotivationMode",
    "MotivationProfilePattern",
    "TaskClass",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "MOTIVATION_TRAPS",
    "MOTIVATION_MODES",
    "MOTIVATION_PROFILE_PATTERNS",
    "TASK_CLASSES",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_trap_score",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "MOTIVATION_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # Prompts
    "SAXBERG_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_TRAPS_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_WEINER_PROMPT",
    "FORENSIC_ABANDONMENT_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "TRAPS_PROMPT",  # legacy
    "INTERVENTIONS_PROMPT",  # legacy
    "assemble_prompt",
]

__version__ = "0.2.0"
