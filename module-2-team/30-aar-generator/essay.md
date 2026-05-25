# Your agents have amnesia. Borrow this trick from the US Army.

*A first essay from vstack — organizational behavior, practiced on AI agents.*

---

In February 2026, a developer wrote a Medium post titled *["Why Your AI Agent Keeps Making the Same Mistake (And How to Fix It)."](https://medium.com/@oadiaz/why-your-ai-agent-keeps-making-the-same-mistake-and-how-to-fix-it-eeb19dd9758c)* It begins like this:

> Most AI agents have amnesia. Every conversation starts from zero. They forget context. They ask the same questions repeatedly. The fundamental problem is that agents can't learn from rejection.

A few paragraphs later:

> One developer experienced five iterations with five rejections of the same fundamental mistake, because the agent couldn't learn from rejection.

In April, another developer wrote a postmortem titled *["The Agent That Burned $4,200 in 63 Hours."](https://medium.com/@sattyamjain96/the-agent-that-burned-4-200-in-63-hours-a-production-ai-postmortem-d38fd9586a85)* An agent had been instructed to "keep trying until it works." It did. It tried 63 hours straight, burning $4,200 in API costs, without ever stopping to ask whether the approach was viable.

These are not edge cases. A widely-shared 2026 analysis of 847 agent deployments found that **76% of them fail in production**. A separate study found 47% user abandonment after one week when the agent had no proper memory of prior failures. The APEX-Agents 2026 benchmark found that even the best models complete only 24% of real-world agentic tasks on the first attempt. The PwC 2026 Agent Survey found that 79% of organizations have adopted AI agents, but "most cannot trace failures through multi-step workflows or measure quality systematically."

The pattern is consistent. Agents are getting deployed faster than they're getting *better*. Each agent run is essentially a one-shot try. When it fails, no structural lesson is captured. The next run starts fresh. The same mistake recurs.

This is not a model-capability problem. The 2026 frontier models are good at single-step reasoning. The 76% failure rate is a problem of **organizational learning** — or rather, the absence of it. AI agents are being treated as functions, when they should be treated as teams. And teams that don't have rituals for capturing what they learn from failure do not improve.

Humans have known how to solve this since 1973.

## The US Army figured this out fifty years ago

In the early 1970s, the United States Army was emerging from Vietnam with a hard question: how do military units actually get better between operations? Reading manuals didn't work. Doctrinal updates from higher command took years to filter down. After-the-fact debriefs with senior officers tended to focus on assigning blame.

The Army's answer was a structured ritual called the **After-Action Review** (AAR), formalized in Training Circular 25-20. The AAR has four steps, conducted immediately after every mission — successful or failed:

1. **Goal.** What did we want to accomplish?
2. **Results.** What did we actually do?
3. **Lessons.** Why was there a difference?
4. **Next Steps.** What will we do differently next time?

Three things make the AAR work where post-hoc debriefs don't:

- It runs **after every mission**, not just the failures. This normalizes the ritual and removes the implicit blame frame. (If you only AAR your failures, the AAR itself signals "you screwed up.")
- It runs **immediately**, not days later. The trace evidence is still fresh in everyone's heads.
- It produces a **behavioral change**, not a Confluence page. The deliverable is *what we will do differently next time*. The whole point is the next step, not the historical narrative.

The framework escaped military doctrine and spread. Wharton@Work published a 2014 article making the AAR the canonical leadership pattern. BP credited the AAR for reducing well-completion time by 50% in the late 1990s. Toyota uses an AAR variant (their "hansei" reflection ritual) on every project. The Center for Army Lessons Learned at Fort Leavenworth maintains a public AAR corpus that doctrine writers still mine for patterns.

The OB literature on AAR converges on the same observation: **organizations that ritualize structured reflection on completed work improve faster than organizations that don't.** Not because the reflection itself is magic. Because the reflection produces a *next step* that closes the loop between failure and behavior change.

## AI agents are organizations without rituals

Consider the structure of a modern agent system. There is a task. There is an agent with some prompt, some tools, some scaffolding. The agent attempts the task. It succeeds or it fails. If it fails, a developer either rewrites the prompt, swaps the model, adds a tool, or runs it again with retry logic.

What is missing — visibly missing — is the AAR. There is no ritual between the failure and the next attempt that asks: *Why was there a difference between goal and result?* There is no structured lesson record that gets captured anywhere durable. There is no behavioral change beyond the developer's own implicit memory of "oh, the agent does this thing now, I'll avoid it."

When the same developer who watched the agent fail at task X six months ago hires the agent to do task Y today, that developer remembers (sometimes). The *agent* does not. There is no organizational memory in the system, because there is no organization. There is just an agent and a function call.

This is the gap vstack exists to close. And specifically, this is the gap pattern #30 — the **AAR Generator** — exists to close.

## What the AAR Generator does

`vstack.aar` is an open-source library that takes a structured agent run trace and produces, automatically, the four AAR artifacts:

1. **A written AAR document** — Goal / Results / Lessons / Next Steps, formatted as markdown, ready to drop in a Confluence page or attached to a LangSmith trace.
2. **A specific prompt-patch suggestion** — a concrete edit to the agent's system prompt or instructions that, if applied, would prevent the failure on the next run.
3. **A new eval test** — a regression test that catches the specific failure mode going forward, so subsequent prompt edits don't silently reintroduce it.
4. **A lesson record** — a structured object that can be injected into the agent's long-term memory, so the *agent itself* can reference the lesson on later runs.

The library is framework-agnostic. It consumes traces from LangSmith, Braintrust, Phoenix, Langfuse, Claude Agent SDK's built-in tracing, OpenAI Agents SDK, CrewAI, AutoGen, Microsoft Agent Framework, Mastra — anywhere a trace exists. It produces the four artifacts using an LLM (you bring your own client; Anthropic, OpenAI, and a local-Ollama adapter ship with the library).

The Wharton 4-step structure is honored exactly. The library's primary class — `AARGenerator.generate(trace)` — runs four sequential LLM passes, one per step, with prompts that explicitly anchor in the AAR posture: development-focused, future-focused, evidence-grounded, terse.

The output is the *organizational memory* that current agent systems do not have. With one line of code per agent run.

## How this is different from what's already out there

Several adjacent things exist in the agent-tooling ecosystem in mid-2026:

- **Anthropic's [Claude Agent SDK site-reliability-agent cookbook](https://platform.claude.com/cookbook/claude-agent-sdk-03-the-site-reliability-agent)** ships post-mortem templates via PagerDuty and Confluence MCP tools. These are *SRE-flavored* postmortems — they fire when an alert goes off, the agent investigates, and a Confluence page gets written. Different shape from AAR. SRE postmortems are for *incidents*. AARs are for *every run, success or failure*. The AAR is closer to a reflection ritual than an incident response.
- **Anthropic published a public postmortem** in April 2026 on a quality regression in one of their AI assistant products: [anthropic.com/engineering/april-23-postmortem](https://www.anthropic.com/engineering/april-23-postmortem). Frontier labs do this practice for themselves. They have not packaged it as a runtime library applicable to every developer.
- **Observability platforms** (Phoenix, AgentOps, Braintrust, Latitude, LangSmith, Langfuse) capture traces and let humans dig through them. They do not produce the *organizational learning artifact* — the lesson record that closes the loop between failure and the next attempt.
- **Memory / RAG libraries** (LangChain Memory, MemGPT, Mem0) capture context but not lessons. They remember *what happened* without naming *why it went wrong* or *what we'll do about it*.

The AAR Generator is the thing that sits in the gap between observability (we see what happened) and memory (we remember context). It is the *reflection layer*: it takes the trace, produces the lesson, and feeds the lesson back into the agent so the agent can reference it.

## Why this is just the first of thirty-four patterns

The AAR is one organizational ritual. There are thirty-three more in the vstack library, each anchored in named OB literature, each addressing a specific named failure mode in AI agent systems:

- The **Lencioni Five Dysfunctions Diagnostic** (pattern #17) classifies multi-agent system failures by the same five-layer dysfunction pyramid Patrick Lencioni gave human teams in 2002.
- The **Trust Triangle Audit** (pattern #18) applies Frei & Morriss's three-leg trust model — Logic, Authenticity, Empathy — to cross-model agent comparison. Some models wobble on Authenticity (they hedge instead of guess, or guess instead of hedge). Some wobble on Empathy. The wobble determines where each model fits.
- The **Johari Window Self-Audit** (pattern #03) maps the four quadrants of Joseph Luft's 1955 model — Open / Blind / Hidden / Unknown — to four agent failure modes: confabulation lives in Blind, silent reasoning lives in Hidden, latent capability lives in Unknown.
- The **GRPI Working Agreement Generator** (pattern #13) produces an explicit Goals / Roles / Processes / Interactions contract for multi-agent deployments — the team-formation ritual McKinsey teaches its short-term teams, adapted for orchestrator + sub-agents.

Thirty-four patterns. Each shipped with five layers: a documented framework, a working library, a runnable demo, a public benchmark, a Substack-ready essay.

It is the *gstack* model applied to AI agents — Garry Tan's open-source-tools-as-credibility-engine pattern, with organizational behavior as the curatorial lens.

## The invitation

If you ship production AI agents and have noticed that they fail in patterns that look more like organizational problems than engineering problems, the AAR Generator is for you. Start there. The library is on GitHub at [github.com/valani9/vstack](https://github.com/valani9/vstack) (early; feedback issues welcome). The first integration target is the Claude Agent SDK; LangGraph and OpenAI Agents SDK follow.

If you are an OB researcher and the cross-application of named frameworks (Lencioni, Edmondson, Frei, Stone & Heen) to AI agents intrigues you, please tell me where I have anchored a framework imprecisely. The pattern library is meant to honor the source literature, not pattern-match on names.

If you are an AI builder who has a real production failure trace and would like the AAR Generator validated against it, open an issue. Real failures > synthetic.

There are thirty-three patterns to come. The first one is here.

---

*Ilhan Valani is a builder shipping vstack in public. The repo lives at [github.com/valani9/vstack](https://github.com/valani9/vstack). The pattern library is anchored entirely in public OB literature; no course-internal materials are redistributed.*
