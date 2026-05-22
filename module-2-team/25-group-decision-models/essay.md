# Your multi-agent vote is hiding a blocker. The facilitator canon fixed this.

*An eighteenth essay from AgentCity — organizational behavior, practiced on AI agents.*

---

Four agents — `architect`, `sre`, `data-eng`, `security` — vote on which database to use for a new high-stakes analytics workload. The orchestrator collects their votes and runs the standard tally:

- `postgres`: 3 votes
- `clickhouse`: 1 vote

The orchestrator ships the postgres recommendation. The decision is "majority approved."

Three weeks later, the rollout stalls. The data-eng agent — the one who voted for clickhouse — has been quietly producing requirements documents that don't quite match what postgres can do, asking clarifying questions that re-litigate the decision, and surfacing technical objections that should have been raised in the vote. The other three agents are frustrated. The team's velocity is half what it should be.

What happened isn't groupthink — there was real disagreement. It isn't a hallucination — the votes were genuine. It's something more banal: **the wrong aggregation method was used.** Majority voting handed the decision to the larger group, leaving the dissenter's substantive concern unaddressed. On a decision where post-decision buy-in mattered, the team needed an aggregation method that surfaced lukewarm support and required engagement with the holdout. Majority hides what fist-to-five reveals.

The facilitator canon — Sam Kaner's *Facilitator's Guide to Participatory Decision-Making*, Marnie Stewart's training materials, Roger Schwarz's *The Skilled Facilitator* — converged on five canonical aggregation methods decades ago. None of them is universally correct. Each has a trade-off:

- **Concurring** — fastest. One decisive vote with no objection. Right for low-stakes, reversible, urgent decisions where one expert can call it. Wrong for anything where buy-in matters.
- **Majority** — fast. >50% threshold. Right for moderate stakes where the 49% minority accepts the outcome. Wrong for high-stakes decisions where dissent costs you later.
- **Consensus** — slow. Everyone affirms or at least does not block. Right for high-stakes irreversible decisions where buy-in matters more than speed. Wrong for low-stakes choices (you'll burn budget on glacial debate).
- **Fist-to-Five** — medium speed. Graded support per agent (0 = block, 5 = champion). The under-used star of the canon. Right when *degree of agreement matters*, not just yes/no. A "fist" (score 0) is an explicit block that should never be overridden by averaging.
- **Unanimous** — slowest. Every agent positively votes for the same option. Reserve for high-stakes irreversible regulated decisions and decisions that require visible team alignment.

The interesting empirical finding across the literature: most teams default to **majority voting regardless of context** — because it's the model everyone knows. This is the most-common-and-least-context-appropriate choice. For low-stakes decisions, majority is overkill. For high-stakes decisions with required buy-in, majority's hidden dissent shows up later as execution failure.

Multi-agent AI crews have the same default. Most production systems use one of:

1. **Implicit concurring** — orchestrator picks one agent and delegates ("decider"). Fast, but no real aggregation happens.
2. **Plurality voting** — naïve `Counter(votes).most_common()`. Treated as "majority" but doesn't enforce the >50% threshold; ties are silent.
3. **LLM-as-judge synthesis** — a separate agent reads all positions and emits one decision. Effectively *consensus by fiat* — no real aggregation primitive.

None of these are wrong universally; all of them are wrong on some non-trivial subset of decisions. **Picking the right method is itself a decision-quality lever** — separate from the substance of the decision being made.

## What `agentcity.group_decision` does

The library takes a `DecisionRequest` with:

- The decision title and options
- The agents participating
- Decision properties: `stakes`, `reversibility`, `time_pressure`, `expertise_asymmetry`, `regulatory_exposure`, `buy_in_required`
- Optional `forced_model` override (when the team has already decided which method to use)

and produces a `DecisionProtocol` with:

1. **Recommended model** — one of the five canonical methods
2. **Rationale** — why this method fits the decision properties
3. **Protocol steps** — concrete, ordered, executable by the agent team
4. **Threshold** — the pass criterion in plain language
5. **Quorum** — minimum agents who must vote
6. **Tie-breaker** — how ties resolve
7. **Fallback model** — what to use if the primary doesn't converge
8. **Tally result** (optional) — when votes are supplied in the request, a deterministic local tally runs without a second LLM call

Single LLM pass for the protocol generation; the tally is pure Python with one function per method. Same retry / graceful-degradation infrastructure as the rest of AgentCity. Output exposes `to_orchestrator_preamble()` for prepending to the orchestrator's system prompt — the orchestrator literally executes the recommended method, not a default.

## Why this matters operationally

The two most operationally important features are the **fist-to-five tally** and the **forced_model override**.

The fist-to-five tally is the cleanest fix for the database-decision incident above. Under fist-to-five, the votes would have looked like: architect 4, sre 4, data-eng 3, security 5. Mean for postgres: 4.0. No blocking fist (no score of 0). Postgres wins — but `data-eng` is recorded as a dissenter on the winner. The orchestrator now has *structured visibility* into the lukewarm support and can take a follow-up step (pair-program, address the specific concern, override explicitly) instead of discovering the dissent three weeks later as execution drag.

The forced_model override lets teams who've already chosen their method skip the recommendation pass entirely. The library still produces the protocol spec, threshold, and (if votes are supplied) deterministic tally. Useful when a team has standardized on, say, fist-to-five for all decisions and just wants the protocol + tally machinery.

The third under-appreciated feature is `to_orchestrator_preamble()`. The orchestrator gets a condensed text block that's literally prepended to its system prompt. So the orchestrator doesn't *interpret* a decision-making policy; it *executes* one. This is the operational analog of the SMART Goal Generator's `to_agent_preamble()` — the generated artifact becomes the runtime context.

## How this fits with the rest of AgentCity

This is pattern #25 of 34 — the eighteenth pattern shipped. AgentCity now has **three generative patterns**:

- **#13 GRPI Working Agreement Generator** — team-level: goals + roles + processes + interactions
- **#24 SMART Goal Generator** — individual-goal level: Specific, Measurable, Achievable, Relevant, Time-bound (with kill criteria)
- **#25 Group Decision Models Generator** (this pattern) — collective-choice level: how the team makes binding decisions

The three compose. GRPI sets up the team; SMART specs each agent's individual goals; Group Decision Models specifies the aggregation method for the choices the team makes together. A multi-agent crew configured with all three is materially more likely to ship clean decisions than one configured with none.

Pattern #25 also closes the multi-agent diagnostic loop: where #14 (Process Gain/Loss), #15 (Social Loafing), #26 (Groupthink), and #28 (Devil's Advocate) *diagnose* multi-agent decision failures, #25 *provides the aggregation primitive* whose absence often causes them.

Install:

```bash
pip install git+https://github.com/valani9/agentcity.git
```

Run the demo without an API key:

```bash
cd module-2-team/25-group-decision-models
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping AgentCity in public.*
