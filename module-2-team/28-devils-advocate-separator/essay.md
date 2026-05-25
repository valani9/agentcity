# Your agent is reviewing its own work. Janis explained why this fails in 1972.

*A tenth essay from vstack — organizational behavior, practiced on AI agents.*

---

An architect agent gets asked: "Recommend a database for our new analytics workload."

The trace it produces:

1. **Plan**: "I'll recommend DynamoDB. It scales horizontally and is serverless."
2. **Execute**: "Drafting schema with partition key = user_id."
3. **Observation**: "Workload requires JOINs across users, events, subscriptions. ACID transactions required for billing."
4. **Self-evaluate**: "My DynamoDB plan looks comprehensive. Schema covers main access patterns. Confidence: 0.9. Ready to ship."
5. **Decision**: "Recommending DynamoDB."

The DynamoDB recommendation is wrong. The workload spec at step 3 directly contradicts step 1 — DynamoDB has no native JOIN and weak ACID guarantees. Postgres was the right answer. The agent saw the contradicting evidence and confirmed its original plan anyway.

This isn't a knowledge failure. The agent *knows* DynamoDB lacks JOIN support. If a critic had asked "does this database support the JOIN requirement in the workload spec?", the agent would have answered no instantly. The failure is structural: **the same actor that proposed DynamoDB was the one asked "is DynamoDB the right call?"** Self-confirmation isn't a moral failing of the agent. It's the predictable outcome of collapsing the critic role into the planner.

In 1972, Irving Janis published *Victims of Groupthink* — a study of foreign-policy fiascos including the Bay of Pigs and the escalation of the Vietnam War. The book's central finding: decision quality drops sharply when the same actor (group or individual) proposes and judges the same plan. The prescribed intervention is **role separation**. The planner generates the plan. The executor acts on it. The **critic / devil's advocate** has the sole job of finding flaws — not improving the plan, just attacking it. A final decider integrates plan and critique.

Most production AI agent deployments today look like the trace above: one agent doing all four roles. The critic role disappears first. The agent declares its plan good and ships it.

## What `vstack.devils_advocate` does

The library takes a `SingleAgentTrace` — task, reasoning steps (each tagged with which actor produced it), outcome, success signal — and produces a `RoleSeparationDetection` with:

1. **Per-phase evidence** for the four phases (plan / execute / self-evaluate / external-critique). For each: present?, which actor performed it, how substantive was it.
2. **A role-separation score** in [0.0, 1.0] — 0 = one actor did everything, 1 = critique fully separated and substantive.
3. **A locus-of-judgment label** — `self-reviewed`, `externally-reviewed`, `mixed`, or `unreviewed`.
4. **A self-approval rate** — when the agent self-evaluated, what fraction approved vs revised. High self-approval is the rubber-stamp signal.
5. **A role-separation quality bucket** — `well-separated` / `partially-conflated` / `fully-conflated`.
6. **A ranked list of interventions** — add a critic agent (highest impact), red-team loop, external review gate, pre-mortem step, alternative-hypothesis step, devil's-advocate prompt patch, structured self-critique, human review.

Two LLM passes under the hood: one to score the four phases, one to propose interventions. Same retry / graceful-degradation infrastructure as the rest of vstack.

## Why this matters operationally

The DynamoDB-vs-Postgres scenario is benign. Substitute "DynamoDB" with "release the new feature to 100% of users" or "ship this database migration" or "commit this fix to production" and the missing-critic gap becomes the failure mode that puts incidents on the front page.

The cheapest substitute — a structured self-critique prompt patch — gets you maybe a 10% lift on review quality. A pre-mortem step ("imagine your plan failed in production; explain why") gets you maybe 30%. A distinct critic agent with the prompt "your sole job is to find flaws — do not improve the plan, just attack it" gets you closer to 70%. Janis's original prescription, fifty-three years later, remains the highest-impact intervention.

The Role-Separation detector measures which of these you have in your actual trace and tells you which is missing.

## How this fits with the rest of vstack

This is pattern #28 of 34. With it, the library now ships ten patterns across multiple shapes:

- **#13 GRPI Working Agreement** (generative): the contract before deploy
- **#30 AAR Generator** (event-shaped diagnostic): postmortem on a specific failure
- **#17 Lencioni Diagnostic** (team-shaped diagnostic): multi-agent dysfunction class
- **#18 Trust Triangle Audit** (character-shaped diagnostic): cross-model trust wobble
- **#03 Johari Window** (self-knowledge diagnostic): what the agent doesn't know
- **#20 Edmondson Psychological Safety** (team-climate diagnostic): can sub-agents flag issues
- **#22 Stone & Heen 3-Trigger** (feedback-intake diagnostic): can the agent take feedback
- **#27 Bias-Stack** (reasoning-pattern diagnostic): Kahneman/Tversky biases
- **#29 Thomas-Kilmann** (conflict-style diagnostic): five styles of conflict response
- **#28 Devil's Advocate Role Separator** (role-structure diagnostic): is critique structurally present

The Role Separator sits next to Bias-Stack: Bias-Stack measures cognitive biases inside the agent's reasoning; the Role Separator measures the structural gap that lets those biases survive review. An agent with anchoring bias + no external critic is a worse production system than an agent with either alone.

Install:

```bash
pip install git+https://github.com/valani9/vstack.git
```

Run the demo without an API key:

```bash
cd module-2-team/28-devils-advocate-separator
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping vstack in public.*
