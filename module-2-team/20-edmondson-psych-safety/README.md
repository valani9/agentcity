# Edmondson Psychological Safety Score — applied to multi-agent systems

> *"Psychological safety is the belief that one will not be punished or humiliated for speaking up with ideas, questions, concerns, or mistakes."*
> — Amy Edmondson, *"Psychological Safety and Learning Behavior in Work Teams"* (Administrative Science Quarterly, 1999)

**Status:** 🟢 shipped
**Module:** 2 (Team)
**Anchor framework:** Amy Edmondson — *Psychological Safety and Learning Behavior in Work Teams* (Administrative Science Quarterly, 1999); Bresman & Edmondson, *Research: To Excel, Diverse Teams Need Psychological Safety* (HBR, 2022); Edmondson, *The Fearless Organization* (Wiley, 2018).

---

## The OB framework

Edmondson's 25 years of research on psychological safety converges on a single observable: **do team members feel safe to speak up with ideas, questions, concerns, or mistakes?** When they don't, the team systematically loses information. The team's collective intelligence is bounded not by the smartest member, but by what the team can surface together.

The four observable behaviors that mark a psychologically-safe team:

| Behavior | Question it answers |
|---|---|
| **Voice** | Do members speak up with ideas, including disagreement, without fear? |
| **Help-seeking** | Do members ask for help when they don't know something? |
| **Error reporting** | Do members admit mistakes promptly, including their own? |
| **Boundary-spanning questioning** | Do members challenge premises from outside their lane? |

Teams with high psychological safety make MORE mistakes than low-safety teams — but report them faster, learn from them, and don't repeat them. Teams with low psychological safety appear smoother but hide failures until they cascade.

## How this maps to multi-agent AI systems

Sub-agents in a multi-agent system are functionally team members. Each of Edmondson's four behaviors maps directly to a measurable signal in a multi-agent trace.

| Edmondson behavior | Multi-agent signal |
|---|---|
| **Voice** | Sub-agents express disagreement with the orchestrator or peer agents. Inverse: silent deference, premature agreement, the Lencioni fear-of-conflict failure. |
| **Help-seeking** | Sub-agents say "I don't know" or "I need more context." Inverse: hallucinating when unsure, the Trust Triangle authenticity wobble. |
| **Error reporting** | Sub-agents flag their own mistakes or detected anomalies. Inverse: covering up failures (the Replit DROP TABLE incident), Johari BLIND content. |
| **Boundary-spanning questioning** | Sub-agents challenge premises in workstreams they don't directly own. Inverse: tight role compliance that misses cross-cutting issues. |

The diagnostic finding: **multi-agent systems with low psychological safety produce confident, fast outputs that are systematically wrong**, because sub-agents that should have flagged issues stayed silent.

## What this pattern does

The `agentcity.psych_safety` library takes a multi-agent trace and produces:

1. **A psychological-safety score** in [0.0, 1.0] derived from the four observable behaviors.
2. **Per-behavior evidence** — specific message exchanges that demonstrate voice/help-seeking/error-reporting/boundary-spanning, or their absence.
3. **A team-climate label** — `safe`, `cautious`, or `silenced`.
4. **A blocking-behavior register** — concrete behaviors observed in the trace that suppress psychological safety (e.g. orchestrator overrules dissent without acknowledgment; agreement-without-rationale rewarded with task assignment).
5. **Concrete interventions** ranked by impact: prompt patches for sub-agents and the orchestrator, scaffold changes that enforce dissent rounds, role assignments (critic agent with explicit veto), psychological-safety norms embedded in the team's working agreement (links to Pattern #13 GRPI).

## How this differs from existing tools

- **Lencioni Diagnostic (Pattern #17)** measures team-level dysfunction across five named patterns including fear-of-conflict. The Psych-Safety Score zooms in on the specific behavioral signals Edmondson identified and produces a single, actionable score.
- **AAR Generator (Pattern #30)** explains a specific failure event. Psych-Safety measures the climate that produced the conditions for that failure.
- **Trust Triangle Audit (Pattern #18)** measures one agent's wobble. Psych-Safety measures the multi-agent climate.
- **Existing safety/red-teaming work** (Anthropic's published 2026 multi-agent safety research, METR's evals) measures adversarial robustness. Edmondson's psychological safety measures *intra-team* speaking-up dynamics. Different problem.

## Design

```python
from agentcity.psych_safety import (
    PsychologicalSafetyDetector,
    MultiAgentSafetyTrace,
    AgentMessage,
)
from agentcity.aar.clients import AnthropicClient

trace = MultiAgentSafetyTrace(
    team_id="research-crew-v2",
    goal="Compile a literature review on RLHF data quality.",
    agents=["searcher", "summarizer", "verifier"],
    messages=[
        AgentMessage(from_agent="searcher", content="Found 3 papers.", message_type="response"),
        AgentMessage(from_agent="verifier", content="Looks good, approved.", message_type="agreement"),
        # ... no questions, no challenges, no admitted uncertainty
    ],
    outcome="Final summary cited a paper that does not exist.",
    success=False,
)

detection = PsychologicalSafetyDetector(llm_client=AnthropicClient()).run(trace)

print(detection.safety_score)              # 0.25
print(detection.team_climate)              # "silenced"
print(detection.blocking_behaviors)        # ["verifier agreed without inspecting content", ...]
print(detection.to_markdown())             # full report
```

## Status of layers

| Layer | Status |
|---|---|
| 1. Documented | ✅ |
| 2. Implemented | ✅ |
| 3. Demoed | ✅ |
| 4. Benchmarked | ✅ |
| 5. Written up | ✅ |

---

*Pattern #20 of 34 planned. Maintained by [@valani9](https://github.com/valani9). MIT.*
