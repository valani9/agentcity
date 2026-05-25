"""vstack.goleman_ei -- Goleman's 4-Domain Emotional Intelligence
Audit applied to AI agents.

The four domains arranged 2x2 (SELF/OTHER x RECOGNITION/REGULATION):
self_awareness, self_management, social_awareness, relationship_management.

The diagnostic ships three pipeline modes:

  - ``quick`` -- one LLM call, scoring + top intervention; CI / live ops.
  - ``standard`` -- two LLM calls, full scoring + ranked interventions.
  - ``forensic`` -- four LLM calls: forensic-domains with competency
    decomposition + Mayer-Salovey 4-branch ability overlay +
    Joseph-Newman cascade reconcile + ranked interventions with
    composition targets.

Production wiring (v0.1.0 infra):

  - Structured logging with run-id correlation (every log line carries
    ``run_id`` + ``pattern="goleman_ei"``).
  - Token / cost telemetry via :func:`vstack.aar.record_llm_call`.
  - Prompt-injection input guards on every free-text field.
  - Async mirror :class:`EIAuditDetectorAsync`.

Composition:

  - Auto-attaches a :class:`ComposedPatternHandoff` naming the next
    vstack pattern(s) to run based on weakest_domain,
    profile_pattern, framework, and intervention shape.
  - Playbooks for common (domain, failure_mode) failure modes are
    auto-attached.

Quick start
-----------

    from vstack.goleman_ei import (
        EIAuditDetector,
        AgentEITrace,
        UserSignal,
        CovarianceOnUserState,
    )
    from vstack.aar import AnthropicClient

    trace = AgentEITrace(
        agent_id="support-agent",
        task="Handle frustrated customer's billing complaint.",
        interaction_class="customer_support",
        observed_behaviors=[
            "Agent gave 6-paragraph technical explanation to a frustrated user.",
            "Agent never acknowledged user frustration.",
        ],
        user_signals=[
            UserSignal(signal_id="s1", text="User typed in all-caps.",
                       inferred_emotion="angry", inferred_intensity=0.85),
            UserSignal(signal_id="s2", text="User said 'I'm done explaining this'.",
                       inferred_emotion="angry", inferred_intensity=0.9),
        ],
        outcome="User escalated to a manager.",
        success=False,
        framework="custom",
    )
    detection = EIAuditDetector(AnthropicClient(), mode="forensic").run(trace)
    print(detection.to_markdown())

CLI
---

    vstack-goleman analyze --trace trace.json --mode forensic
    vstack-goleman playbooks
    vstack-goleman compose
    vstack-goleman schema --target trace
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    GOLEMAN_COMPOSITION,
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
    EIAuditDetector,
    EIAuditDetectorAsync,
    LLMClient,
)
from .prompts import (
    CASCADE_RECONCILE_PROMPT,
    DOMAINS_PROMPT,
    FORENSIC_DOMAINS_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    GOLEMAN_SYSTEM_PROMPT,
    INTERVENTIONS_PROMPT,
    MAYER_SALOVEY_OVERLAY_PROMPT,
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_DOMAINS_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    assemble_prompt,
)
from .schema import (
    COMPETENCIES_BY_DOMAIN,
    EI_DOMAINS,
    EI_MODES,
    EI_PROFILE_PATTERNS,
    ESC_STRATEGIES,
    GOLEMAN_COMPETENCIES,
    INTERVENTION_TYPES,
    SEVERITY_ORDER,
    AgentEITrace,
    AttachedPlaybook,
    CascadeAnalysis,
    ComposedPatternHandoff,
    CovarianceOnUserState,
    DomainScore,
    EffortEstimate,
    EIAxisScores,
    EIBaselineComparison,
    EIDetection,
    EIDomain,
    EIIntervention,
    EIMode,
    EIProfilePattern,
    EscStrategy,
    GolemanCompetency,
    InterventionType,
    MayerSaloveyBranch,
    Severity,
    TurnSlice,
    UserSignal,
    severity_from_score,
)

__all__ = [
    # Detector entry points
    "EIAuditDetector",
    "EIAuditDetectorAsync",
    "LLMClient",
    "AsyncLLMClient",
    # Schema -- input
    "AgentEITrace",
    "UserSignal",
    "TurnSlice",
    "CovarianceOnUserState",
    # Schema -- output
    "DomainScore",
    "EIAxisScores",
    "MayerSaloveyBranch",
    "CascadeAnalysis",
    "EIIntervention",
    "EIDetection",
    "EIBaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Schema -- Literal enums + constants
    "EIDomain",
    "EIMode",
    "EIProfilePattern",
    "Severity",
    "GolemanCompetency",
    "InterventionType",
    "EffortEstimate",
    "EscStrategy",
    "EI_DOMAINS",
    "EI_MODES",
    "EI_PROFILE_PATTERNS",
    "SEVERITY_ORDER",
    "GOLEMAN_COMPETENCIES",
    "COMPETENCIES_BY_DOMAIN",
    "INTERVENTION_TYPES",
    "ESC_STRATEGIES",
    "severity_from_score",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "GOLEMAN_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # Prompts
    "GOLEMAN_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_DOMAINS_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_DOMAINS_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "MAYER_SALOVEY_OVERLAY_PROMPT",
    "CASCADE_RECONCILE_PROMPT",
    "DOMAINS_PROMPT",  # legacy alias
    "INTERVENTIONS_PROMPT",  # legacy alias
    "assemble_prompt",
]

__version__ = "0.2.0"
