# Your 5-agent crew is worse than your best single agent. Steiner explained this in 1972.

*A fifteenth essay from AgentCity — organizational behavior, practiced on AI agents.*

---

You assemble a 5-agent research crew — `lead`, `researcher`, `writer`, `reviewer`, `fact-checker` — and assign it to write a 1-page summary of the prompt-injection defense literature. The team ships a polished-looking 1-pager.

Three numbers tell the rest of the story:

- The same task, attempted by *solo Claude* with no team around it: quality 0.85.
- The same task, attempted by *solo GPT*: quality 0.78.
- The 5-agent crew's output: quality 0.62.

The team's output is *worse* than either single-agent baseline. And the team cost 5.2× as much. So you paid five times more for a worse result.

This isn't an exotic failure mode. In our corpus of multi-agent runs, it's the *median* outcome for crews assembled on tasks that one capable agent could have done alone. The team underperformed the best individual. This is the canonical phenomenon Ivan Steiner named in 1972: **process loss.**

Steiner's framework is one of social psychology's least flattering:

> Actual productivity = Potential productivity − Process Loss + Process Gain

Potential productivity is what the team *could* produce if every member contributed their best work with no friction. Process loss is the friction subtracted by the act of working together. Process gain is what's added when the team's interaction produces something no single member could have. The empirical literature — going back to Hill's 1982 meta-analysis on brainstorming groups — has consistently found that for most tasks, **process loss dominates process gain.** Groups don't add value by default. They subtract it.

Steiner identified the canonical loss factors:

- **Coordination cost** — cycles spent on coordination that didn't improve the output. The 5-agent crew's interaction log has 5× the message count and 5× the cost of a single-agent run; if the messages don't move quality, those cycles are pure loss.
- **Social loafing** — some members free-ride. The reviewer's only output is "LGTM"; the fact-checker's only output is "Citations look fine to me" with zero verification tool calls. (See Pattern #15 for the dedicated detector.)
- **Groupthink** — premature convergence; dissent suppressed. The researcher flags one citation as "needs verification"; no agent verifies it, and the wrong figure ships. (Pattern #26.)
- **Handoff loss** — information lost at agent-to-agent transfers. The writer paraphrases the researcher without preserving the qualifications. The fact-checker receives the report without preserving the flag.
- **Context dilution** — each agent saw a slice of the task; no agent has the full picture that the single-agent baseline did.
- **Consensus dilution** — strong individual answers get averaged into bland team answers. The crew's final 1-pager is recognizably the *mean* of the researcher's framing and the reviewer's preferences, with neither's strongest argument intact.

The diagnostic counts which of these is doing the most damage. The intervention catalog runs in order of impact:

1. **Use the single best agent.** When the gain/loss score is large-negative and cost overhead is large-positive, the strongest fix is the one nobody wants to hear: retire the multi-agent crew. Steiner's framework is unambiguous on this. If process loss dominates and the task class doesn't have non-overlapping subgoals, the team is the wrong tool.
2. **Smaller team.** Loss scales with size. A 3-agent crew loses less than a 5-agent crew.
3. **Decompose the task.** Process loss collapses when each member owns a *non-overlapping subgoal*. Section-1-author, section-2-author, section-3-author beats lead-researcher-writer-reviewer-fact-checker.
4. **Nominal group aggregation.** Agents work *independently*, then a separate judge selects the best (rather than blending). The classic process-gain construction.
5. **Explicit critic.** A named devil's-advocate role (Pattern #28).
6. **Structured handoffs** + **context summarization** — preserve information across transitions.
7. **Fixed vote aggregation** — replace consensus with median/max/plurality.

## What `agentcity.process_gain_loss` does

The library takes a `ProcessTrace` containing:

- Two or more **individual baselines** (each scored 0-1 on quality, optionally with cost)
- The **team result** (also scored 0-1 on quality, optionally with cost)
- The **interaction log** (the team's actual messages — optional)
- Task and outcome

and produces a `ProcessGainLossDetection` with:

1. **Process-quality bucket**: `process-gain`, `neutral`, or `process-loss`
2. **Gain/loss score**: team_quality − best individual quality
3. **Cost overhead ratio**: team cost / best single-agent cost
4. **Per-factor evidence** for the six canonical loss factors (each scored 0-1 with severity + evidence quotes)
5. **A ranked list of interventions** from the catalog above

Two LLM passes: one to score the six factors, one to propose interventions. *Skipped entirely on process gain* — when the team beat the best single, there's nothing to fix. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## Why this matters operationally

This is the **only** multi-agent metric that answers the question whose answer is required to justify the multi-agent architecture at all: *did the team's combined cost produce something the best single agent couldn't?* Most multi-agent observability dashboards measure activity (tokens, latency, message counts). Activity is not value. The process-gain/loss diagnostic measures value-relative-to-counterfactual, which is what the engineering decision actually needs.

The OVERTURNS-style verdict from this pattern is high-impact: a 5-agent crew that has been running in production for months, with a budget line item and an internal owner, gets diagnosed as process-loss-with-5x-cost-overhead and the recommendation is *use the single best agent.* This is the moment that justifies the rest of AgentCity's diagnostic catalog — when the verdict is "the right answer is to use less" rather than "tune the prompt better."

## How this fits with the rest of AgentCity

This is pattern #14 of 34 — the fifteenth pattern shipped. AgentCity now ships **five** patterns that diagnose multi-agent crews at different levels of the diagnostic hierarchy:

- **Outcome-level (this pattern, #14)** — did the team beat the best single agent?
- **Team-shape (#17 Lencioni)** — which of the 5 dysfunctions does the team have?
- **Role-structure (#28 Devil's Advocate)** — is critique structurally present?
- **Per-agent contribution (#15 Social Loafing)** — given the roles exist, are they being done?
- **Round-by-round dynamics (#26 Groupthink/Polarization/Contagion)** — what's happening in the actual debate?

The five compose into a layered diagnostic stack. Pattern #14 sits at the top: if a team has process loss, *one of the lower-level patterns* will tell you which factor caused it. If the top-level metric reports process gain, none of the lower-level diagnostics are urgent.

Install:

```bash
pip install git+https://github.com/valani9/agentcity.git
```

Run the demo without an API key:

```bash
cd module-2-team/14-process-gain-loss-detector
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping AgentCity in public.*
