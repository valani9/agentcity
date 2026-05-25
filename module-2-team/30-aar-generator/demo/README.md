# AAR Generator — Demos

Each demo shows the AAR Generator running on a real agent failure trace from one of the supported frameworks.

## Planned demos (in order)

| Framework | Demo file | Failure scenario | Status |
|---|---|---|---|
| Claude Agent SDK | `01-claude-agent-sdk/` | Multi-step web-research task that hallucinates a URL and never recovers | ⚪ TODO |
| LangGraph | `02-langgraph/` | Cyclic graph that loops on the same retry without escalating | ⚪ TODO |
| OpenAI Agents SDK | `03-openai-agents-sdk/` | Function-calling agent that re-calls the same broken tool 5 times | ⚪ TODO |
| CrewAI | `04-crewai/` | Multi-agent crew where the planner and the executor disagree silently | ⚪ TODO |
| AutoGen | `05-autogen/` | Group chat that converges too quickly on a flawed plan (groupthink) | ⚪ TODO |

## Demo conventions

Every demo follows the same shape so the AAR output across frameworks is comparable:

1. **Trace capture** — run the agent on the scenario, capture the trace via the framework's native tracing.
2. **Trace conversion** — convert the framework-native trace to `AgentTrace` using the adapter in `vstack.aar.adapters.<framework>`.
3. **AAR generation** — run `AARGenerator(...).generate(trace)`.
4. **Output** — markdown AAR + prompt patch + new eval test + lesson record, written to `demo/<framework>/output/`.

## How to add a demo

If you ship production agents and have a failure trace you'd like the AAR Generator validated against, open an issue. Real failures > synthetic.
