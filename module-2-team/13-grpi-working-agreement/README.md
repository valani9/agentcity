# GRPI Working Agreement Generator — Beckhard's GRPI model for multi-agent setup

> *"For groups to function effectively, four conditions must be met: clear goals, clear roles, clear processes, and clear interpersonal relations."*
> — Richard Beckhard, *Optimizing Team Building Effort* (Journal of Contemporary Business, 1972)

**Status:** 🟢 shipped
**Module:** 2 (Team)
**Anchor framework:** Richard Beckhard — *Optimizing Team Building Effort* (Journal of Contemporary Business, 1972). Re-popularized in Tannenbaum & Salas, *Teams that Work: The Seven Drivers of Team Effectiveness* (2020), Chapter 3.

---

## The OB framework

The GRPI model is the canonical pre-flight checklist for any team being formed. Four dimensions, in order — each builds on the previous:

| Letter | Dimension | The question it answers |
|---|---|---|
| **G** | **Goals** | What is the team trying to achieve? What is the measurable success criterion? |
| **R** | **Roles** | Who owns what? Who decides what? What does each member commit to deliver? |
| **P** | **Processes** | How will the team work together? What are the rules of engagement, the decision protocol, the escalation path? |
| **I** | **Interactions** | How will members treat each other? What does respectful disagreement look like? What's the communication cadence? |

The framework's punchline: **most team failures trace back to a missing G, R, P, or I** — not to lack of skill or effort. A team with clear goals but unclear roles produces work that doesn't ladder. A team with clear roles but no decision process loops indefinitely. A team with clear processes but no interaction norms blows up in conflict the first time stress hits.

The intervention is structural: write the working agreement *before* the team starts, sign it explicitly, refer back to it when the team falters.

## How this maps to AI agents

Multi-agent AI systems are teams in literally the same sense Beckhard meant: a group of autonomous entities working interdependently toward a shared outcome. Every multi-agent failure category in this library maps to a missing GRPI dimension:

| GRPI dimension missing | Multi-agent failure pattern |
|---|---|
| **Goals** | Sub-agents optimize their own metrics over the user's goal (Lencioni inattention-to-results). Plans that ladder differently per agent. |
| **Roles** | Same task delegated three times; agents step on each other; "who owns this?" silence. Planner-equals-evaluator pathology (Pattern #28). |
| **Processes** | No decision protocol (majority vote? consensus? planner-rules?). No escalation path. No abandonment criterion. Loop pathology. |
| **Interactions** | No norms for inter-agent challenge. No structured disagreement format. The Lencioni "fear of conflict" failure (Pattern #17). |

The first four patterns AgentCity shipped (AAR, Lencioni, Trust Triangle, Johari) are all *diagnostic* — they look at what happened after the failure. **GRPI is the opposite shape: it's the pre-flight contract that prevents many of those failures in the first place.**

## What this pattern does

The `agentcity.grpi` library is a *generative* pattern, not a diagnostic. It takes a team-setup request — a task description, an agent roster, optional constraints — and produces a structured **Working Agreement** document covering all four GRPI dimensions:

1. **Goals section** — measurable success criteria, scope boundaries, deliverables, kill criteria
2. **Roles section** — per-agent role definition, decision rights, accountability owner per work-stream
3. **Processes section** — decision protocol, escalation path, abandonment criteria, communication cadence
4. **Interactions section** — disagreement norms, feedback format, conflict resolution, voice/turn-taking rules

The output is both human-readable markdown and machine-readable JSON — the JSON can be embedded directly into orchestrator prompts, used as a checklist gate in CI, or stored in agent memory as a referenceable contract.

## What this is NOT

- Not a diagnostic for *existing* multi-agent failures. For that, use Pattern #17 (Lencioni) or #18 (Trust Triangle).
- Not an executor — this generates the contract, doesn't enforce it. The contract is meant to be referenced by the orchestrator at runtime.
- Not a replacement for a system prompt — the agreement *augments* the system prompt with team-level structure that individual-agent prompts can't express.

## Design

```python
from agentcity.grpi import (
    GRPIWorkingAgreementGenerator,
    TeamSetupRequest,
    AgentRole,
)
from agentcity.aar.clients import AnthropicClient

request = TeamSetupRequest(
    team_id="marketing-campaign-crew-q3",
    task="Design and launch a Q3 SaaS marketing campaign within 14 days.",
    agents=[
        AgentRole(name="researcher", description="Market and competitor research"),
        AgentRole(name="strategist", description="Campaign strategy and channel selection"),
        AgentRole(name="critic", description="Devil's-advocate review"),
        AgentRole(name="executor", description="Asset production and launch"),
    ],
    constraints=[
        "Budget cap: $20K",
        "Must include 1 mandatory dissent round before any decision is locked",
        "All agents must read the working agreement before first run",
    ],
    success_criteria=[
        "≥3 distinct campaign concepts proposed",
        "≥1 alternative considered per decision",
        "Launch within 14 days",
    ],
)

agreement = GRPIWorkingAgreementGenerator(llm_client=AnthropicClient()).generate(request)

print(agreement.to_markdown())                    # human-readable contract
print(agreement.to_orchestrator_preamble())       # condensed text for orchestrator system prompt
print(agreement.model_dump_json(indent=2))        # machine-readable JSON
```

## How this differs from existing tools

- **Multi-agent framework "team templates"** (CrewAI's Crew config, Microsoft Agent Framework workflows, LangGraph state machines): these specify *what* the team does. GRPI specifies *how the team works together* — the meta-level contract that survives changes to specific tasks.
- **System prompts**: capture individual-agent behavior but cannot express team-level interaction norms (e.g. "the critic agent must raise ≥2 alternatives before consensus is allowed").
- **Pattern #28 (Critical Evaluator / Devil's Advocate Role Separator)**: addresses one specific R within GRPI. GRPI is the full contract; #28 is one role within it.

## Integrations (planned)

- **CrewAI** — auto-generate the GRPI agreement when a new Crew is instantiated; embed it in the crew's shared memory.
- **LangGraph** — generate the agreement as a state-graph annotation; runtime can reference it during routing decisions.
- **Microsoft Agent Framework** — equivalent integration once the SDK exposes a stable team-config hook.
- **Claude Agent SDK** — for multi-subagent orchestrations, prepend the agreement to the orchestrator system prompt.

## Benchmarks

The corpus in `eval/synthetic_grpi_requests.yaml` contains 8 hand-crafted team-setup requests, each tagged with the expected GRPI structure (which dimensions are explicitly required by the request). The benchmark scores whether the generator surfaces all four dimensions with non-trivial content per request.

## Status of layers

| Layer | Status |
|---|---|
| 1. Documented (this README) | ✅ |
| 2. Implemented (lib/) | ✅ |
| 3. Demoed (demo/) | ✅ |
| 4. Benchmarked (eval/) | ✅ |
| 5. Written up (essay.md) | ✅ |

---

*Pattern #13 of 34 planned. Maintained by [@valani9](https://github.com/valani9). MIT.*
