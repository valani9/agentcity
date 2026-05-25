# Your multi-agent system has trust issues. Patrick Lencioni called it.

*A second essay from vstack — organizational behavior, practiced on AI agents.*

---

Multi-agent AI is everywhere in 2026. Anthropic's Claude Agent SDK ships orchestration patterns. OpenAI's Agents SDK has multi-agent workflows. Microsoft Agent Framework, LangGraph's multi-agent graphs, CrewAI, AutoGen, Mastra — every major framework now treats "multi-agent" as the headline. The pitch is universal: complex tasks decompose into specialized agents, each playing a role, coordinated by an orchestrator.

The reality, when these systems hit production, is uglier.

A 3-agent crew agrees on the first proposal in under a minute. No debate. No alternatives surfaced. The campaign ships and underperforms at 12% of target.

A research crew built around a planner-summarizer-verifier loop confidently cites a paper that does not exist. The verifier approved the summary. The summary trusted the planner. The planner hallucinated. Each layer of trust was unearned.

A database migration crew of two — planner and reviewer, same model with different prompts — runs a migration that locks the production table for 40 minutes. The reviewer rubber-stamped the planner. Both agents stayed in their lane.

A customer support pipeline closes a ticket with all internal metrics green: response time 4 minutes (under SLA), refund $20 (authorized), retention email sent. The customer churns. No agent owned "did this actually help."

These are not different failure modes. They are the same five failure modes, repeated across frameworks and stacks. And every one of them was diagnosed and named by a management consultant named Patrick Lencioni twenty-three years ago.

## The pyramid that explains every multi-agent failure

In 2002, Lencioni published *The Five Dysfunctions of a Team* — a short, fable-style business book that has since sold over ten million copies and has become canonical in MBA curricula. Its central claim is that teams fail in five named ways, and the five sit on top of each other in a pyramid:

```
                    5. INATTENTION TO RESULTS
                  4. AVOIDANCE OF ACCOUNTABILITY
                3. LACK OF COMMITMENT
              2. FEAR OF CONFLICT
            1. ABSENCE OF TRUST
```

The pyramid order is the punchline. Higher dysfunctions cannot be repaired while lower ones are still present. A team that avoids conflict cannot commit. A team that doesn't commit cannot be held accountable. A team that lacks accountability cannot focus on results. You fix the foundation first or you don't fix anything.

Translate each layer to multi-agent AI:

**Absence of Trust** — agents do not verify each other's work. One agent's confabulated fact propagates to every downstream agent that reads it. The verifier trusts the summarizer trusts the planner. The chain is only as strong as the weakest link, and there is no link calling out the weakness.

**Fear of Conflict** — sub-agents agree with the orchestrator's plan because they were trained to defer. There is no devil's-advocate role. There is no "we should consider three alternatives before committing." Consensus is achieved by silence, which is not consensus at all. This is the marketing-crew failure.

**Lack of Commitment** — agents revisit decisions endlessly. The same task gets delegated three times because no agent claims it. The orchestrator loops because no sub-agent has fully owned a decision. This is the hosting-provider failure where 47 messages produce no resolution.

**Avoidance of Accountability** — when the system fails, which agent owned the bad step? Currently invisible in most observability tools. Traces show *what* happened but not *who* was supposed to prevent what. Without attribution, the team cannot learn.

**Inattention to Results** — agents optimize their local metric (token budget, tool-call success rate, latency) over the user's actual goal. The customer support pipeline that closes the ticket with green dashboards while the customer churns.

Each of these is detectable in a structured multi-agent trace. Each maps to a concrete intervention. Each is named by a vocabulary that anyone who has read Lencioni — which is roughly every MBA and every Fortune-500 manager — recognizes instantly.

## Why this framing matters more than another observability tool

The AI agent observability market is crowded. LangSmith, Braintrust, Phoenix, Langfuse, AgentOps, Latitude, Laminar — every observability platform now claims multi-agent support. They all do the same job: capture the trace, render it as a tree, let humans pan and zoom.

What none of them do is *diagnose the team*. They surface the data. Diagnosis is left to the human operator, who is left to invent vocabulary on the fly.

The Lencioni Diagnostic is the missing layer. It consumes the same trace data, runs a structured five-pass diagnostic, and produces an output that any business stakeholder can read: a pyramid score, a dominant-dysfunction diagnosis, a team-health label, and a ranked list of interventions. The output is not "agent #3 had high latency on step #47." The output is "this team has a Fear-of-Conflict problem — the critic agent has agreed with every proposal in the last 12 runs without raising a single objection. Recommended intervention: assign explicit devil's-advocate role with a quota."

That second framing is what gets the multi-agent system fixed. It is the framing managers use when human teams have the same problem. The vocabulary is portable. The interventions are concrete. The dysfunction is named.

## What `vstack.lencioni` actually does

The library takes a `MultiAgentTrace` — the goal, the team roster, the message log, the outcome, the success signal — and produces a `LencioniDiagnosis` with:

1. A **pyramid score** (0.0-1.0 per dysfunction, in pyramid order)
2. A **dominant-dysfunction diagnosis** (foundation-favoring tie-break per Lencioni's model)
3. **Per-dysfunction evidence** with specific message quotes from the trace
4. A ranked list of **interventions** (prompt patches, scaffold changes, role assignments, new evals, communication protocols)
5. An **overall team-health label** (healthy / stressed / dysfunctional) for at-a-glance dashboard use

The library is framework-agnostic. It accepts traces serialized from CrewAI, AutoGen, LangGraph (with multi-agent state), Microsoft Agent Framework, Mastra, OpenAI Agents SDK, or custom orchestrators. The output is structured JSON with a markdown renderer, so it drops cleanly into a Confluence postmortem, a Slack alert, a LangSmith annotated trace, or a dashboard.

Two LLM passes under the hood: one to score the pyramid against the trace, one to propose interventions targeting the dominant dysfunction. Both passes ship with retry-on-rate-limit, graceful degradation when the LLM returns malformed JSON, and the same `LLMClient` interface as the AAR Generator — bring your own Anthropic, OpenAI, Ollama, or stub client.

## How this fits with the rest of vstack

This is pattern #17 of 34 planned. The first pattern shipped — pattern #30, the After-Action Review Generator — diagnoses *one agent's* failure as a learning event. The Lencioni Diagnostic diagnoses *the team's* failure as a system. They are complementary tools for complementary jobs:

- A single agent fails a task → run the AAR Generator on its trace
- A multi-agent crew fails a job → run the Lencioni Diagnostic on the team's trace
- A multi-agent crew fails repeatedly with the same dysfunction → run the Lencioni Diagnostic across multiple traces and look for which dysfunction is structurally embedded

Pattern #18 (next) is the Trust Triangle Audit (Frei & Morriss), a cross-model benchmark that diagnoses *which leg* a specific model wobbles on — Logic, Authenticity, or Empathy. With AAR + Lencioni + Trust Triangle, vstack covers the three orthogonal axes: time (postmortem), team (Lencioni), and identity (Trust Triangle).

Thirty-one more patterns to ship after that. Each anchored in named OB literature. Each shipping with all five layers: documented framework, working library, runnable demo, public benchmark, Substack-ready essay.

## The invitation

If you ship multi-agent systems in production and you have noticed that the failures rhyme — that the same kinds of failures keep happening across different deployments — the Lencioni Diagnostic is for you. Start there. The library is part of [vstack](https://github.com/valani9/vstack); install via `pip install git+https://github.com/valani9/vstack.git` and import as `vstack.lencioni`. First integration target is CrewAI; LangGraph, AutoGen, and OpenAI Agents SDK follow.

If you are an OB researcher and the application of Lencioni's pyramid to AI teams intrigues you, please open an issue. The mapping is anchored in the public framework but the verifier-trust-summarizer-trust-planner chain is an agent-specific instantiation that deserves academic critique.

If you have a real production multi-agent failure trace you want to validate the diagnostic against, please reach out. Real failures beat synthetic ones every time.

Two patterns shipped. Thirty-two to come.

---

*Ilhan Valani is a builder shipping vstack in public. The repo lives at [github.com/valani9/vstack](https://github.com/valani9/vstack). The pattern library is anchored entirely in public OB literature; no course-internal materials are redistributed.*
