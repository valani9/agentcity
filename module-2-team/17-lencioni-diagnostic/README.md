# Lencioni Five Dysfunctions Diagnostic — for Multi-Agent Systems

> *"Effective teams are built on a foundation of trust, and missing this base leads to poor results and dysfunctional teams."*
> — Patrick Lencioni, *The Five Dysfunctions of a Team* (2002)

**Status:** 🟡 in progress
**Module:** 2 (Team)
**Anchor framework:** Patrick Lencioni — *The Five Dysfunctions of a Team* (Jossey-Bass, 2002), 10M+ copies sold.

---

## The OB framework

Lencioni's model is a pyramid. Each dysfunction sits on top of the one below it. Higher dysfunctions cannot be fixed unless the lower foundations are in place.

```
                    5. INATTENTION TO RESULTS
                  4. AVOIDANCE OF ACCOUNTABILITY
                3. LACK OF COMMITMENT
              2. FEAR OF CONFLICT
            1. ABSENCE OF TRUST
```

| # | Dysfunction | Human-team behavior |
|---|---|---|
| 1 | **Absence of Trust** | Members hide mistakes, hold grudges, refuse to be vulnerable. Foundation of every other dysfunction. |
| 2 | **Fear of Conflict** | Artificial harmony, boring meetings, decisions not debated. Avoidance disguised as politeness. |
| 3 | **Lack of Commitment** | Ambiguous decisions, revisited endlessly. Members agree in the room and dissent outside it. |
| 4 | **Avoidance of Accountability** | Members tolerate poor performance from peers. Standards drift. No one calls out misalignment. |
| 5 | **Inattention to Results** | Members optimize for personal status, ego, or team-internal metrics — not the collective outcome. |

## How this maps to multi-agent AI systems

Multi-agent systems are teams. Each agent has a role, a tool stack, a memory, and information that other agents in the system may or may not have. They communicate, delegate, disagree, decide, and produce a collective output. Every Lencioni dysfunction has a direct analog in production multi-agent failures.

| # | Human-team dysfunction | Multi-agent failure mode |
|---|---|---|
| 1 | Absence of Trust | **Agents don't verify each other's outputs.** Cascading hallucinations — one agent's confabulated fact propagates to every downstream agent that queries it. |
| 2 | Fear of Conflict | **Premature consensus / groupthink.** Sub-agents agree with the orchestrator's plan because they're trained to defer; no devil's-advocate role; debate converges in one round. |
| 3 | Lack of Commitment | **Loop on ambiguous decisions.** Same task delegated three times because no agent claims it. Agents revisit decisions when intermediate results are ambiguous. |
| 4 | Avoidance of Accountability | **No error attribution.** When the system fails, which agent owned the bad step? Currently invisible in most observability tools. |
| 5 | Inattention to Results | **Local-metric optimization.** Sub-agent optimizes its own token budget / tool-call success / latency over the user's actual goal. |

These are not metaphors. Each can be detected in a structured multi-agent trace. Each maps to a concrete intervention (prompt patch, scaffold change, role reassignment, new eval).

## What this pattern does

The `vstack.lencioni` library takes a structured multi-agent trace (the messages exchanged between agents, the tools each used, the final outcome) and produces:

1. **A pyramid score** — 0.0-1.0 severity per dysfunction, in pyramid order.
2. **A dominant-dysfunction diagnosis** — the highest-impact dysfunction blocking the team.
3. **Per-dysfunction evidence** — specific message sequences in the trace that illustrate the dysfunction.
4. **Concrete interventions** — prompt patches, scaffold changes, role assignments, new evals, ranked by impact on the dominant dysfunction.
5. **An overall team-health label** — `healthy`, `stressed`, or `dysfunctional` — for at-a-glance dashboard usage.

The library reuses the same LLM-client interface as the AAR Generator (Anthropic, OpenAI, Ollama, Stub). Multi-agent traces from CrewAI, AutoGen, LangGraph (with the multi-agent state), Microsoft Agent Framework, Mastra, or custom orchestrators all serialize into the same `MultiAgentTrace` schema.

## How this differs from existing tools

- **Observability platforms** (LangSmith, Braintrust, Phoenix, AgentOps, Latitude) capture multi-agent traces. They do not assign a *team-level diagnosis*. The Lencioni Diagnostic consumes their trace export and produces the diagnosis.
- **Single-agent post-mortems** (the AAR Generator, pattern #30) explain *one agent's* failure. The Lencioni Diagnostic explains *the team's* failure as a system. The two are complementary — run the AAR Generator per-agent, run the Lencioni Diagnostic per-team-run.
- **Existing multi-agent debugging** (Anthropic's multi-agent research, OpenAI's swarm patterns) describes architectural choices. The Lencioni Diagnostic describes which of five named dysfunctions is producing the bad outcome — vocabulary builders and managers already know.

## Design

```python
from vstack.lencioni import LencioniDiagnostic, MultiAgentTrace, AgentMessage
from vstack.lencioni.clients import AnthropicClient

trace = MultiAgentTrace(
    goal="Generate a marketing campaign for SaaS launch",
    agents=["researcher", "strategist", "critic"],
    messages=[
        AgentMessage(from_agent="researcher", to_agent=None,
                     content="I propose LinkedIn ads for enterprise CTOs",
                     message_type="task"),
        AgentMessage(from_agent="strategist", to_agent=None,
                     content="Agreed, LinkedIn ads",
                     message_type="agreement"),
        AgentMessage(from_agent="critic", to_agent=None,
                     content="Agreed",
                     message_type="agreement"),
        # ... no debate, no challenge, no alternative considered
    ],
    outcome="Campaign launched, performed 12% of target",
    success=False,
)

diagnostic = LencioniDiagnostic(llm_client=AnthropicClient()).run(trace)

print(diagnostic.dominant_dysfunction)        # "fear-of-conflict"
print(diagnostic.pyramid_score)               # {"absence-of-trust": 0.4, "fear-of-conflict": 0.9, ...}
print(diagnostic.overall_team_health)         # "dysfunctional"
print(diagnostic.to_markdown())               # full report
```

## Integrations (planned)

- **CrewAI** — first integration target; CrewAI's multi-agent shape maps directly to Lencioni's team-level dysfunctions.
- **AutoGen / Microsoft Agent Framework** — group chat as a Lencioni team.
- **LangGraph** — multi-agent state graph; messages between graph nodes become `AgentMessage`s.
- **OpenAI Agents SDK** — multi-agent orchestration patterns.
- **Mastra** — workflow + agent orchestration.

## Benchmarks (planned)

- **Synthetic dysfunction corpus** — 10+ hand-crafted multi-agent traces, each tagged with the expected dominant dysfunction. The library should recall the correct dysfunction.
- **GAIA multi-step + CrewAI failure traces** — when multi-step agent collaborations fail, does the diagnostic explain *why*?
- **Real production failures** (community donations) — open call for trace donations once the public repo is live.

## Status of layers

| Layer | Status |
|---|---|
| 1. Documented (this README) | ✅ |
| 2. Implemented (lib/) | 🟡 schema + diagnostic generator + prompts ready, integration adapters pending |
| 3. Demoed (demo/) | 🟡 self-contained synthetic demo runs |
| 4. Benchmarked (eval/) | 🟡 synthetic dysfunction corpus + scoring runner ready |
| 5. Written up (essay.md) | ✅ first draft ready |

---

*Pattern #17 of 34 planned. Maintained by [@valani9](https://github.com/valani9). MIT.*
