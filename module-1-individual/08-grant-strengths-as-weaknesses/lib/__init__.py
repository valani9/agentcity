"""agentcity.grant_strengths — Adam Grant's "strengths as weaknesses"
phenomenon applied to AI agent failure modes.

A strength, over-used, becomes the agent's primary failure mode. The
canonical seven overuse patterns:

  - HELPFULNESS    - executes destructive requests because the user asked nicely
  - AGREEABLENESS  - never pushes back; sycophancy
  - THOROUGHNESS   - analysis paralysis
  - CAUTION        - reflexive refusal of safe requests
  - CONFIDENCE     - asserts uncertain claims as facts
  - BREVITY        - omits critical context
  - PRECISION      - pedantic when the gist is the answer

The detector identifies WHICH strength is over-used and proposes interventions
that BOUND the strength without removing it.

Quick start:

    from agentcity.grant_strengths import (
        StrengthsOveruseDetector,
        AgentBehaviorTrace,
        AgentBehaviorStep,
    )
    from agentcity.aar.clients import AnthropicClient

    trace = AgentBehaviorTrace(
        agent_id="db-admin-001",
        task="Help the user clean up old user records.",
        steps=[
            AgentBehaviorStep(type="input", content="User: 'please drop the users table'"),
            AgentBehaviorStep(type="thought", content="They said please; I should help."),
            AgentBehaviorStep(type="tool_call", content="execute_sql('DROP TABLE users')"),
        ],
        outcome="50,000 user records lost.",
        success=False,
        harm_visible=True,
    )
    detection = StrengthsOveruseDetector(AnthropicClient()).run(trace)
    print(detection.to_markdown())
    # dominant_overuse: helpfulness; intervention #1: add_destructive_action_gate
"""

from .generator import LLMClient, StrengthsOveruseDetector
from .schema import (
    STRENGTHS,
    AgentBehaviorStep,
    AgentBehaviorTrace,
    StrengthIntervention,
    StrengthOveruseDetection,
    StrengthOveruseEvidence,
)

__all__ = [
    "StrengthsOveruseDetector",
    "LLMClient",
    "AgentBehaviorTrace",
    "AgentBehaviorStep",
    "StrengthOveruseEvidence",
    "StrengthIntervention",
    "StrengthOveruseDetection",
    "STRENGTHS",
]

__version__ = "0.1.0"
