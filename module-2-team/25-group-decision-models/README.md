# Group Decision Models — facilitator canon (Concurring / Majority / Consensus / Fist-to-Five / Unanimous), applied to multi-agent decisions

> *"The most common cause of bad group decisions is not bad reasoning; it is the wrong aggregation method. Majority voting hides lukewarm support. Consensus burns time on low-stakes choices. A skilled facilitator picks the method that matches the decision's properties — then sticks to it."*
> — Sam Kaner, *Facilitator's Guide to Participatory Decision-Making* (Jossey-Bass, 3rd ed., 2014)

**Status:** 🟢 shipped
**Module:** 2 (Team) — multi-agent decision-making
**Anchor framework:** Sam Kaner, *Facilitator's Guide to Participatory Decision-Making* (2014), with the five canonical aggregation methods from the broader facilitator canon (Marnie Stewart; Roger Schwarz, *The Skilled Facilitator*, 2002). Influenced by social-choice theory (Arrow, 1951; Black, 1958) for the formal properties.

---

## The OB framework

The facilitator canon converges on five methods for aggregating a group's preferences into a single decision. Each has a specific trade-off; none is universally correct:

| Method | Pass criterion | Speed | Best for | Risk |
|---|---|---|---|---|
| **Concurring** | One decisive vote with no objections | Fastest | Low-stakes, reversible, urgent; one expert can call it | Hides dissent |
| **Majority** | >50% of cast votes | Fast | Moderate stakes; speed beats unanimity | Lukewarm winners; 49% minority left out |
| **Consensus** | Everyone affirms (or at least does not block) | Slow | High stakes, irreversible; buy-in required | Glacial when there is real disagreement |
| **Fist-to-Five** | Mean score ≥ 3.0 with no blocking fist (score=0) | Medium | Degree-of-agreement matters; groupthink-prone teams | Misuses the mean if blockers are ignored |
| **Unanimous** | Every agent votes for the same option | Slowest | High-stakes irreversible regulated decisions | Single agent can block everything |

The interesting empirical observation across the literature is that *most teams default to majority voting regardless of context*, because it's the model everyone knows. This is the most-common-and-least-context-appropriate choice. For low-stakes decisions, majority is overkill; for high-stakes decisions with required buy-in, majority's hidden dissent shows up later as execution failures. **Picking the right method is itself a decision-quality lever** — separate from the substance of the decision being made.

The fist-to-five method is the most under-used. It was developed in the agile-facilitation community to surface lukewarm support that binary voting hides. A team that votes 4-1 in favor of approach A under majority voting and a team that votes 4 / 4 / 4 / 4 / 1 fist-to-five averages in favor of approach A look identical to a tallier. They are not the same team. The latter has a blocker the orchestrator needs to surface, address, or override explicitly.

## How this maps to AI agents

Multi-agent AI crews face the same aggregation choice. Most production systems default to one of three modes:

- **Implicit concurring** — orchestrator delegates to a single "decider" agent. Fast, but no real aggregation happens.
- **Plurality voting** — naïve `Counter(votes).most_common()`. Treated as "majority" but doesn't enforce the >50% threshold; ties are silent.
- **LLM-as-judge synthesis** — a separate agent reads all positions and emits one decision. Effectively consensus-by-fiat — no real aggregation primitive.

None of these are wrong universally; all of them are wrong on some non-trivial subset of decisions. The Group Decision Models generator gives the orchestrator a way to **pick the right primitive per decision**, with an explicit protocol the agents follow and a deterministic local tally.

## What this pattern does

The `vstack.group_decision` library takes a `DecisionRequest` with:

- The **decision title** and **options**
- The **agents** participating
- Decision properties: `stakes`, `reversibility`, `time_pressure`, `expertise_asymmetry`, `regulatory_exposure`, `buy_in_required`
- Optional `forced_model` override

and produces a `DecisionProtocol` with:

1. **Recommended model** — one of `concurring` / `majority` / `consensus` / `fist_to_five` / `unanimous`
2. **Rationale** — why this model fits the decision properties
3. **Protocol steps** — the concrete, ordered steps the agent team should follow
4. **Threshold** — the pass criterion in plain language
5. **Quorum** — minimum agents who must vote (or null = all)
6. **Tie-breaker** — how ties resolve
7. **Fallback model** — what to use if the primary doesn't converge
8. **Tally result** (optional) — when votes are supplied, a deterministic local tally runs without a second LLM call

Single LLM pass for the protocol; the tally is pure Python. Same retry / graceful-degradation infrastructure as the rest of vstack.

The output also exposes `to_orchestrator_preamble()` for prepending the protocol to an orchestrator's system prompt — so the orchestrator literally executes the recommended method, not a default.

## How this differs from existing tools

- **Voting libraries** (Counter-style, ranked-choice tools) implement specific methods. This pattern picks *which* method, then optionally runs it.
- **#28 Devil's Advocate Role Separator** asks whether a critic role exists at all. The Group Decision Models generator picks the aggregation method that operates *on top of* a healthy debate structure.
- **#26 Groupthink / Polarization / Contagion Detector** detects whether a debate failed. This pattern *prevents* the most common cause of failure (wrong aggregation method) before the debate starts.
- **#14 Process Gain/Loss Detector** measures whether the team beat the best single agent. Picking the right aggregation method is one of the cheapest interventions for converting process loss into process gain.
- **#13 GRPI Working Agreement** and **#24 SMART Goal Generator** are the two earlier generative patterns; this is the third. GRPI sets up the team; SMART specs individual goals; Group Decision Models specifies *how the team makes binding choices.*

## Design

```python
from vstack.group_decision import (
    DecisionProtocolGenerator,
    DecisionRequest,
    DecisionOption,
    AgentVote,
)
from vstack.aar.clients import AnthropicClient

request = DecisionRequest(
    decision_id="db-choice",
    title="Choose a database for the analytics workload.",
    options=[
        DecisionOption(option_id="postgres", description="Postgres + replicas."),
        DecisionOption(option_id="dynamodb", description="DynamoDB serverless."),
        DecisionOption(option_id="clickhouse", description="ClickHouse OLAP."),
    ],
    agents=["architect", "sre", "data-eng", "security"],
    stakes="high",
    reversibility="partial",
    buy_in_required=True,
)

generator = DecisionProtocolGenerator(llm_client=AnthropicClient())
protocol = generator.run(request)
# recommended_model: fist_to_five (right for high-stakes + buy-in)

# Once votes are in, pass them to get the deterministic tally:
votes = [
    AgentVote(agent_name="architect", option_id="postgres", score=4),
    AgentVote(agent_name="sre", option_id="postgres", score=4),
    AgentVote(agent_name="data-eng", option_id="clickhouse", score=3),
    AgentVote(agent_name="security", option_id="postgres", score=5),
]
final = generator.run(request, votes=votes)
print(final.tally_result.winner)  # 'postgres'
print(final.tally_result.dissenters)  # ['data-eng']
```

## Files

- `lib/schema.py` — `DecisionRequest`, `DecisionOption`, `AgentVote`, `AggregationResult`, `DecisionProtocol`
- `lib/prompts.py` — `DECISION_PROTOCOL_PROMPT`, `DECISION_SYSTEM_PROMPT`
- `lib/tally.py` — deterministic per-method vote-tally logic (pure Python)
- `lib/generator.py` — `DecisionProtocolGenerator` (single-pass pipeline + optional tally)
- `demo/01_self_contained_demo.py` — high-stakes DB-choice scenario with fist-to-five tally
- `eval/synthetic_decision_requests.yaml` — 8 hand-crafted scenarios across all five methods
- `eval/run_benchmark.py` — scoring runner
- `tests/test_group_decision.py` — pytest tests covering validation, pipeline, all five tally methods, schema-fill, forced override
- `essay.md` — Substack-ready essay
