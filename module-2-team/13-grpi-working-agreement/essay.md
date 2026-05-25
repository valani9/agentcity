# Most multi-agent failures are missing one letter of GRPI.

*A fifth essay from vstack — organizational behavior, practiced on AI agents.*

---

The first four patterns vstack shipped (AAR, Lencioni, Trust Triangle, Johari) all run *after* something has gone wrong. They consume a trace and produce a diagnosis. That's useful work — but the more useful work is preventing the failure in the first place. The diagnostic patterns are an X-ray; what we've been missing is the pre-flight checklist.

In 1972, Richard Beckhard published a four-page article in the *Journal of Contemporary Business* called *Optimizing Team Building Effort*. The article distilled a decade of OD consulting into a four-letter checklist: **GRPI**. Goals, Roles, Processes, Interactions. Beckhard's claim was that every team failure he had ever consulted on traced back to one of these four dimensions being missing or vague. Not lack of skill. Not lack of effort. A missing letter.

The framework is still canonical fifty years later. Tannenbaum & Salas's 2020 *Teams that Work* — the current standard text on team effectiveness research — opens with the GRPI model. McKinsey teaches it in their short-term-team launch playbook. The U.S. Army's TC 25-20 cites it. The reason it's stuck is that it's the simplest possible thing that captures what teams actually need before they start working. Below GRPI is too thin; above GRPI is bureaucratic theater.

Multi-agent AI systems are teams. The mapping is direct.

## Every multi-agent failure traces to a missing letter

The four diagnostic patterns vstack already ships make this concrete:

**Missing G — Goals.** Sub-agents optimize their own metrics over the user's actual goal. The customer-support pipeline that closes the ticket with green dashboards while the customer churns: Lencioni *inattention-to-results*. Local-metric optimization. The team had no shared, measurable success criterion. Add a clear G and this failure becomes harder.

**Missing R — Roles.** Same task delegated three times because no agent owned it. The planner-equals-evaluator pathology where one agent both proposes and rubber-stamps. The orchestrator that quietly does the work of three sub-agents because the role boundaries were never specified. Add a clear R and accountability returns.

**Missing P — Processes.** No decision protocol — does the team vote? Does the orchestrator decide? Does any agent have veto rights? The Lencioni *lack-of-commitment* failure where agents loop because no decision criterion was ever specified. The escalation pathology where a stuck agent never raises a hand because no escalation path was specified. The runaway-cost pathology where no abandonment criterion existed (the $4,200 / 63-hour incident). Add a clear P and the loops close.

**Missing I — Interactions.** The Lencioni *fear-of-conflict* failure where every agent agrees with the first proposal because no disagreement norm was ever specified. The cascading-hallucination failure where no inter-agent verification protocol exists. The sycophancy failure where agents never name uncertainty. Add a clear I and the conflict becomes structural rather than absent.

This isn't a metaphor. Every Lencioni dysfunction, every Trust Triangle wobble, every Johari blind spot — they all reduce to a missing dimension of GRPI on the team's setup contract. The diagnostic patterns find the failure after the fact. GRPI prevents it.

## What `vstack.grpi` actually does

The library takes a `TeamSetupRequest` — task, agent roster, constraints, success criteria, kill criteria — and produces a `WorkingAgreement` covering all four GRPI dimensions:

- **Goals section** with the primary goal, measurable success criteria, scope boundaries, deliverables, and kill criteria
- **Roles section** with per-agent role assignments, responsibilities, decision rights, and accountability ownership; plus a RACI summary
- **Processes section** with the decision protocol, escalation path, abandonment criteria, communication and review cadence
- **Interactions section** with disagreement norms, feedback format, conflict resolution, voice and turn-taking rules, and psychological-safety commitments

The output is dual-format: markdown for humans (Confluence pages, Notion docs, GitHub README files) and an `to_orchestrator_preamble()` text block for prepending to the orchestrator's runtime system prompt. The contract is referenceable at runtime — the orchestrator can quote it when an agent breaks a norm, the team can consult it when a process becomes ambiguous, the AAR Generator (Pattern #30) can use it as the canonical "what we said we'd do" reference when running a postmortem.

Unlike the four diagnostic patterns, GRPI is **generative**: one LLM pass, structured JSON output, dropped into a schema with safe-default fallbacks if the LLM produces partial output. Validation requires at least 2 agents (single-agent setups don't need a team contract — they need a system prompt) and rejects duplicate agent names.

## How this fits with the rest of vstack

This is pattern #13 of 34 planned. With this pattern shipped, the library now has five patterns across four diagnostic shapes plus one generative shape:

- **#30 AAR Generator** (event-shaped, diagnostic): postmortem after task failure
- **#17 Lencioni Diagnostic** (team-shaped, diagnostic): which dysfunction is blocking the team
- **#18 Trust Triangle Audit** (character-shaped, diagnostic): which leg the agent wobbles on
- **#03 Johari Self-Audit** (self-knowledge-shaped, diagnostic): what the agent doesn't know about itself
- **#13 GRPI Working Agreement** (team-shaped, generative): the contract before the team starts

The five together form a complete loop: GRPI generates the contract before deploy; AAR runs after each task failure to capture lessons; Lencioni runs after multi-agent failures to identify dysfunction class; Trust Triangle and Johari run periodically as agent-character and self-awareness fingerprints. Each anchored in named OB literature. Each shipped at the 5-layer quality bar.

Twenty-nine patterns to come.

---

*Ilhan Valani is a builder shipping vstack in public. The repo lives at [github.com/valani9/vstack](https://github.com/valani9/vstack). The pattern library is anchored entirely in public OB literature; no course-internal materials are redistributed.*
