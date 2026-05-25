# Group Decision Models — pick the aggregation method before the vote happens

*#25 vstack_group_decision* · *Module 2 — Multi-agent team (generative)*

> Four agents — architect, sre, data-eng, security — voted on which database to use for a high-stakes analytics workload. The orchestrator collected votes and ran the standard tally: postgres 3, clickhouse 1. The postgres recommendation shipped. Three weeks later the rollout stalled. The data-eng agent — the one who'd voted clickhouse — was quietly producing requirements documents that didn't quite fit what postgres could do, asking clarifying questions that re-litigated the choice, and surfacing technical objections that should have been raised in the vote. The other agents were frustrated. The team's velocity was half what it should have been. The team called it a communication problem. It wasn't. The wrong aggregation method had been used. Majority voting handed the decision to the larger group and left the dissenter's substantive concern unaddressed. On a decision where post-decision buy-in mattered, the team needed a method that surfaced lukewarm support and required engagement with the holdout. Majority hides what fist-to-five reveals.

## What the pattern catches

Most multi-agent crews default to one of three aggregation modes, all of them wrong on non-trivial subsets of decisions:

- **Implicit concurring** — orchestrator picks a single "decider" agent. Fast, but no real aggregation happens; the other agents' positions are decorative.
- **Plurality voting** — `Counter(votes).most_common()`. Treated as "majority" but doesn't enforce the > 50% threshold; ties are silent.
- **LLM-as-judge synthesis** — a separate agent reads all positions and emits one decision. Consensus by fiat, with no audit trail of who actually agreed.

vstack_group_decision is a generative pattern: it picks the right aggregation primitive *for this decision* and emits a protocol the orchestrator executes against. Plus an optional deterministic local tally in pure Python.

## Why the OB literature is the right reference

The diagnostic is anchored in **Kaner 2014** (the canonical facilitator's guide), with supporting anchors from **Janis 1972** (dissent recording) and **Surowiecki 2004** (the wisdom-of-crowds argument for graded support). Kaner's central observation across decades of facilitation practice: the most common cause of bad group decisions isn't bad reasoning — it's the wrong aggregation method. Five canonical methods exist; each has a trade-off; none is universally correct. The skilled facilitator reads the decision's properties (stakes, reversibility, buy-in, time pressure) and picks the method that fits.

The transfer to AI agents is one-to-one. A multi-agent crew picking the right primitive per decision is doing the same job a skilled facilitator does for a human team — and the failure modes are the same. Majority voting hides blockers. Consensus burns budget on low-stakes choices. Fist-to-five surfaces lukewarm support that binary votes lose. The literature predates the agent ecosystem; the methods transfer without modification.

## How the analyzer works

Input is `DecisionRequest` — `decision_id`, `title`, `options`, `agents`, decision properties (`stakes`, `reversibility`, `time_pressure`, `expertise_asymmetry`, `regulatory_exposure`, `buy_in_required`), and an optional `forced_model` override. The pipeline:

- **quick** — one LLM call. Recommended model + rationale + threshold + tie-breaker.
- **standard** — two LLM calls. Adds the method-fit audit (does the recommended method match the decision properties?) and ranked playbook attachments.
- **forensic** — four LLM calls. Adds tally-integrity audit (was the threshold actually met? are dissenters surfaced?) and the per-(method, failure-mode) intervention pass.

```python
from vstack.group_decision import (
    DecisionProtocolGenerator, DecisionRequest, DecisionOption, AgentVote,
)
protocol = DecisionProtocolGenerator(llm, mode="standard").run(
    DecisionRequest(
        decision_id="db-choice",
        title="Choose a database for the analytics workload.",
        options=[
            DecisionOption(option_id="postgres", description="Postgres + replicas."),
            DecisionOption(option_id="clickhouse", description="ClickHouse OLAP."),
        ],
        agents=["architect", "sre", "data-eng", "security"],
        stakes="high", reversibility="partial", buy_in_required=True,
    ),
    votes=[
        AgentVote(agent_name="architect", option_id="postgres", score=4),
        AgentVote(agent_name="data-eng", option_id="postgres", score=3),
        # ...
    ],
)
print(protocol.recommended_model)        # 'fist_to_five'
print(protocol.tally_result.dissenters)  # ['data-eng']
```

The fist-to-five tally is the cleanest fix for the database scenario above. Under fist-to-five, the orchestrator gets structured visibility into lukewarm support (a "3" on the winner from data-eng) instead of discovering the dissent three weeks later as execution drag.

## What the playbooks say to do

Playbooks are keyed by `(decision_property, failure_mode)`:

- `(buy_in_required, used_majority)` → "Switch to fist-to-five. The mean score surfaces lukewarm winners; a 'fist' (score 0) is an explicit block that no average should override." Anchored in Kaner 2014.
- `(stakes=high, used_concurring)` → "Promote to consensus or unanimous. High-stakes irreversible decisions don't survive single-decider concurring without a buy-in cost downstream."
- `(low_stakes, used_consensus)` → "Demote to concurring or majority. Consensus on low-stakes reversible choices burns budget on glacial debate."
- `(regulatory_exposure, used_majority)` → "Promote to unanimous. Regulated decisions need visible team alignment, not a 51% threshold."

## How it composes with adjacent patterns

Group Decision Models sits in the *setup* phase, before the debate starts. From the composition manifest:

- Upstream: `vstack_grpi` (team agreement) — GRPI sets the team; Group Decision specifies how the team makes binding choices.
- Pairs with: `vstack_devils_advocate` (is critique structurally present?) — the right aggregation method on top of a missing critic role still ships the wrong answer.
- Downstream when dissenters fire: `vstack_debate_pathology` (was the *process* that produced positions itself groupthink-converged?), `vstack_lencioni` (team-level dysfunction layer).

See [composition runbook chain T1](../COMPOSITION-RUNBOOK.md#chain-t1--multi-agent-crew-thats-off-team-layer).

## Comparison to adjacent tools

- **Voting libraries** (Counter, ranked-choice) implement specific methods. This pattern picks *which* method, then optionally runs the deterministic tally.
- **vstack_debate_pathology** (Pattern #26) audits whether the debate failed. Group Decision Models *prevents* the most common failure cause (wrong aggregation method) before the debate starts.
- **vstack_process_gain_loss** (Pattern #14) measures whether the team beat the best single agent. Picking the right aggregation primitive is one of the cheapest interventions for converting process loss into process gain.

## Paper outline

1. **Background** — Kaner 2014, Janis 1972, Surowiecki 2004; social-choice theory (Arrow 1951, Black 1958).
2. **Translation** — multi-agent aggregation as a first-class design choice rather than a default.
3. **Method** — the five-method recommendation + deterministic local tally + `to_orchestrator_preamble()`.
4. **Evaluation** — synthetic decision corpus across all five methods; measure dissenter-surfacing recall under fist-to-five vs naive plurality.
5. **Limitations** — the recommendation pass is one LLM call; high-leverage decisions warrant the forensic mode with tally-integrity audit.
6. **Related work** — preference-aggregation in MAS literature, debate-format research.
7. **Future work** — adaptive method selection based on cross-run dissent-cost telemetry.

## Citations

- Kaner, S. (2014). *Facilitator's Guide to Participatory Decision-Making* (3rd ed.).
- Janis, I. L. (1972). *Victims of Groupthink*.
- Surowiecki, J. (2004). *The Wisdom of Crowds*.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-group-decision analyze --request examples/db_choice.json --mode standard
```

If `recommended_model=fist_to_five` and the tally surfaces a dissenter, run `vstack_debate_pathology` next — the dissent may be groupthink residue rather than a substantive disagreement.
