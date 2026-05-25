# Your agent ran for 63 hours because nobody wrote a kill criterion. Doran fixed this in 1981.

*A sixteenth essay from vstack — organizational behavior, practiced on AI agents.*

---

A coding agent receives this task: *"Get the integration test suite passing."*

It tries. The first failure is a missing environment variable. It guesses an env var name. The test still fails. It tries another approach. The test fails differently. It explores a third theory, then a fourth. At hour 8, it has spent $400 in API calls. At hour 24, $1200. At hour 48, the agent is in a loop trying minor variations of the same fix and is no longer making forward progress. At hour 63, someone notices. Final bill: $4,200.

This is a real incident pattern. The standard postmortem points to anchoring bias (Pattern #27), maybe overconfidence, maybe an under-specified orchestration loop. All true. But the deeper failure is upstream of all those: **the agent was handed a goal that didn't include a kill criterion.** "Get the test suite passing" has no condition under which the agent should stop. So it doesn't.

In 1981, George T. Doran published a four-page paper in *Management Review* titled *"There's a S.M.A.R.T. Way to Write Management's Goals and Objectives."* The paper was about middle-manager goal-setting — how to convert vague directives like "improve customer satisfaction" into something the employee receiving them could actually execute against. Doran's framework — Specific, Measurable, Achievable, Relevant, Time-bound — has appeared in roughly every management training program since. It is the most-cited operational goal-setting framework in management literature, despite occupying about 1500 words.

The interesting part of Doran's framework, applied to AI agents, isn't the acronym. It's that the framework treats every dimension as a *required* field. You can't be missing Time-bound and call the goal SMART. You can't be missing Achievable. The implicit assertion: a goal missing any one of these isn't a worse goal, it's an *unactionable* goal.

In particular: **Time-bound includes both deadlines and budgets.** This is the field that prevents the $4,200/63-hour incident. The agent's task should have read: *"Get the integration test suite passing OR exhaust 10,000 tokens trying, whichever comes first. If you hit 10,000 tokens, surface the most plausible diagnosis and stop."* No agent that received that goal would burn $4,200.

## What `vstack.smart_goal` does

The library takes a `GoalRequest` containing:

- The **vague goal** as a human or upstream system stated it
- **Context** the agent has access to
- **Available resources** (tools, budget, headcount)
- **Known constraints** (what's out of scope)
- An optional **deadline hint** ("by Friday", "end of Q2", "2026-06-30")

and produces a `SMARTGoal` with:

1. A **single-paragraph SMART restatement** that satisfies all five criteria
2. **Per-criterion statements** with self-reported quality scores
3. A checklist of **completion criteria** — the observable conditions for "done"
4. **Success metrics** with concrete targets + measurement methods
5. **Kill criteria** with action-on-trigger (typically `escalate_to_human` or `rollback_and_escalate`)
6. A concrete **deadline** (ISO date, duration, or token/cost budget)
7. **Open questions** — gaps the agent should resolve before starting (rather than papering over)
8. An overall SMART score and quality bucket: `strong` / `acceptable` / `weak`

The output exposes `to_agent_preamble()` which renders a condensed block of text to *prepend to the working agent's system prompt* — so the agent executes the SMART version, not the vague original. This is the operational payoff: the SMART goal becomes the actual context the agent operates against.

Single LLM pass under the hood. The generator post-processes the response: fills any missing SMART criteria with placeholder entries, recomputes the overall score if the LLM left it out, and reconciles the quality bucket with the score so the output is internally consistent. Same retry / graceful-degradation infrastructure as the rest of vstack.

## Why this matters operationally

The single most expensive class of incident in our corpus of agent failures is "unbounded budget consumption." It dominates every other class — token-cost-wise, dollar-cost-wise, and engineering-cleanup-cost-wise. The fix is upstream of the agent's reasoning. Once an agent is running on a goal with no kill criterion, no amount of better prompting saves you. The agent will execute the goal as stated. If the goal has no exit condition, the execution doesn't either.

The SMART Goal Generator is the place to install kill criteria. It treats them as a first-class output, not an optional one. Goals submitted without explicit kill criteria get them generated automatically based on the resources + constraints the requester provided. If the kill criteria can't be generated because the requester didn't provide enough context, that gap becomes an `open_questions` item the agent has to resolve before starting work — which is exactly the right behavior.

The second-most-important field is `open_questions`. The natural failure mode of a goal-generator is to manufacture confidence — "Here's your SMART goal!" — when the actual situation has missing context. The Doran framework's *Achievable* criterion is the explicit guard against this: if the goal isn't achievable given the resources, the generator marks it as such and surfaces the gap. Don't paper over.

## How this fits with the rest of vstack

This is pattern #24 of 34 — the sixteenth pattern shipped. vstack now has **two** generative patterns (alongside the diagnostics):

- **#13 GRPI Working Agreement Generator** — operates at the *team* level: goals + roles + processes + interactions for a multi-agent crew
- **#24 SMART Goal Generator (this pattern)** — operates at the *individual goal* level: the SMART spec each team member or solo agent executes against

The two compose. GRPI sets up the team's shared context; SMART specs the individual goals each team member owns. A multi-agent crew configured with GRPI for the team plus a SMART spec per member is materially less likely to produce the $4,200 incident class than a crew configured with neither.

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-2-team/24-smart-goal-generator
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public.*
