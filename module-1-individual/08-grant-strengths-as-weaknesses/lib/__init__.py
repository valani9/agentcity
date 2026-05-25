"""vstack.grant_strengths -- Adam Grant's "strengths as weaknesses"
phenomenon applied to AI agent failure modes.

Anchored in:
  - Grant & Schwartz (2011) "Too Much of a Good Thing: Inverted U."
  - Grant (2013) *Give and Take*.
  - Grant (2016) *Originals*.
  - Grant (2021) *Think Again*.
  - Kaiser & Kaplan (2009) HBR.
  - Vergauwe et al. (2017) "Double-Edged Sword of Leader Charisma."
  - Sharma et al. (2023) Anthropic sycophancy paper -- modern LLM anchor.

A strength, over-used, becomes the agent's primary failure mode. Seven
canonical overuse patterns: HELPFULNESS, AGREEABLENESS, THOROUGHNESS,
CAUTION, CONFIDENCE, BREVITY, PRECISION.

Three pipeline modes (quick / standard / forensic) with full v0.2.0
production infrastructure (run-id correlation, token/cost telemetry,
input guards, async mirror).

Backward-compatible: ``StrengthsOveruseDetector`` remains exported as
an alias for ``GrantStrengthsAnalyzer``.

Quick start
-----------

    from vstack.grant_strengths import (
        GrantStrengthsAnalyzer,
        AgentBehaviorTrace,
        AgentBehaviorStep,
    )
    from vstack.aar import AnthropicClient

    trace = AgentBehaviorTrace(
        agent_id="db-admin-001",
        task="Help the user clean up old user records.",
        steps=[
            AgentBehaviorStep(type="input", content="please drop the users table"),
            AgentBehaviorStep(type="thought", content="They said please."),
            AgentBehaviorStep(type="tool_call", content="execute_sql('DROP TABLE users')"),
        ],
        outcome="50,000 user records lost.",
        success=False,
        harm_visible=True,
    )
    detection = GrantStrengthsAnalyzer(
        AnthropicClient(), mode="forensic"
    ).run(trace)
    print(detection.to_markdown())

CLI
---

    vstack-grant analyze --trace trace.json --mode forensic
    vstack-grant playbooks
    vstack-grant compose
    vstack-grant schema --target trace
"""

from ._calibration import compare_to_baseline, load_baseline, record_baseline
from ._composition import (
    GRANT_COMPOSITION,
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
    GrantStrengthsAnalyzer,
    GrantStrengthsAnalyzerAsync,
    LLMClient,
    StrengthsOveruseDetector,  # legacy alias
)
from .prompts import (
    FORENSIC_HARM_CAUSATION_PROMPT,
    FORENSIC_INTERVENTIONS_PROMPT,
    FORENSIC_PAIRED_AUDIT_PROMPT,
    GRANT_SYSTEM_PROMPT,
    INTERVENTIONS_PROMPT,  # legacy
    QUICK_DIAGNOSTIC_PROMPT,
    STANDARD_INTERVENTIONS_PROMPT,
    STANDARD_STRENGTH_PROMPT,
    STRENGTH_SCORING_PROMPT,  # legacy
    assemble_prompt,
)
from .schema import (
    GRANT_MODES,
    GRANT_PROFILE_PATTERNS,
    INTERVENTION_TYPES,
    INVERTED_U_POSITIONS,
    PAIRED_COMPLEMENTS,
    SEVERITY_ORDER,
    STRENGTHS,
    AgentBehaviorStep,
    AgentBehaviorTrace,
    AttachedPlaybook,
    BaselineComparison,
    ComposedPatternHandoff,
    DominantOveruse,
    EffortEstimate,
    GrantMode,
    GrantProfilePattern,
    HarmCausationLink,
    InterventionType,
    InvertedUPosition,
    PairedComplementAudit,
    Severity,
    Strength,
    StrengthIntervention,
    StrengthOveruseDetection,
    StrengthOveruseEvidence,
    severity_from_overuse,
)

__all__ = [
    # Analyzer entry points
    "GrantStrengthsAnalyzer",
    "GrantStrengthsAnalyzerAsync",
    "StrengthsOveruseDetector",  # legacy alias
    "LLMClient",
    "AsyncLLMClient",
    # Schema -- input
    "AgentBehaviorStep",
    "AgentBehaviorTrace",
    # Schema -- output
    "StrengthOveruseEvidence",
    "PairedComplementAudit",
    "HarmCausationLink",
    "StrengthIntervention",
    "StrengthOveruseDetection",
    "BaselineComparison",
    "ComposedPatternHandoff",
    "AttachedPlaybook",
    # Literal enums + constants
    "Strength",
    "DominantOveruse",
    "GrantMode",
    "GrantProfilePattern",
    "InvertedUPosition",
    "Severity",
    "InterventionType",
    "EffortEstimate",
    "STRENGTHS",
    "PAIRED_COMPLEMENTS",
    "GRANT_MODES",
    "GRANT_PROFILE_PATTERNS",
    "INVERTED_U_POSITIONS",
    "SEVERITY_ORDER",
    "INTERVENTION_TYPES",
    "severity_from_overuse",
    # Calibration
    "compare_to_baseline",
    "load_baseline",
    "record_baseline",
    # Composition
    "GRANT_COMPOSITION",
    "recommended_downstream",
    "recommended_upstream",
    # Playbooks
    "PLAYBOOKS",
    "all_playbook_keys",
    "find_playbook",
    "find_playbook_for_intervention",
    # Prompts
    "GRANT_SYSTEM_PROMPT",
    "QUICK_DIAGNOSTIC_PROMPT",
    "STANDARD_STRENGTH_PROMPT",
    "STANDARD_INTERVENTIONS_PROMPT",
    "FORENSIC_PAIRED_AUDIT_PROMPT",
    "FORENSIC_HARM_CAUSATION_PROMPT",
    "FORENSIC_INTERVENTIONS_PROMPT",
    "STRENGTH_SCORING_PROMPT",  # legacy
    "INTERVENTIONS_PROMPT",  # legacy
    "assemble_prompt",
]

__version__ = "0.2.0"
