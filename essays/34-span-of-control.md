# Span-of-Control — the deterministic structural diagnostic

*#34 vstack_span_of_control* · *Module 3 — Organizational*

> A customer-support agent crew worked fine at 10 requests per minute. The team added 8 more worker agents to handle peak traffic at 100 requests per minute. Throughput tanked. The orchestrator became the choke point — every worker was a peer reporting straight to one supervisor, every decision flowed through one node, the queue depth on the orchestrator spiked, and net throughput went *down* relative to the 3-agent crew. The team's first instinct was to add more workers. Span-of-Control would have stopped them.

## What the pattern catches

The only vstack pattern whose **metrics are fully deterministic** — there's no LLM inside the math. Six numbers computed in Python over the crew's reporting graph:

1. **max_span** — widest direct-report count any supervisor has.
2. **mean_span** — average direct-report count.
3. **centralization_index** — 0-1, how concentrated decision authority is.
4. **hierarchy_depth** — longest reports-to chain.
5. **span_gini** — load inequality across supervisors.
6. **decision_bottleneck_score** — composite, factoring in incoming_request_rate.

These six are deterministic enough to ship pre-computed canonical baselines (`_baselines/canonical/span_of_control_*.json`) for three textbook crew topologies. Future runs against the same baseline get drift detection by direct numerical comparison.

The LLM is only used in the *qualitative paraphrase* of the metrics and the intervention generation. The numbers themselves are locked.

## Why the OB literature is the right reference

The classical span-of-control literature runs through:

- **Graicunas 1937** — the original combinatorial argument that adding subordinates increases supervisor relationships factorially.
- **Urwick 1956** — the empirical follow-up (rule-of-thumb: span > 6 starts to break for non-routine work).
- **Galbraith 1995, 2014** — modern structural fit; the right structure depends on task type, environmental uncertainty, and information processing requirements.
- **Mintzberg 1983** — five structural configurations (simple, machine bureaucracy, professional bureaucracy, divisionalized, adhocracy).

The transfer to AI agent crews is *cleaner* than to human teams because the metrics are observable from the agent config (no surveys needed). The classical caveats about "Graicunas's math doesn't apply to autonomous workers" largely vanish — AI agents aren't autonomous in the way humans are; they need orchestration, and orchestration cost scales the way Graicunas predicted.

## How the analyzer works

Input is `CrewLoadTrace` — `crew_id`, `task`, `agents` (each with `agent_id`, `reports_to`, `decision_authority`), `incoming_request_rate`, `outcome`, `success`. The pipeline:

- **quick** — 0 LLM calls. Pure math + a profile_pattern label (one of 10: `balanced_organic` / `centralized_bureaucracy` / `load_amplified_bottleneck` / etc.).
- **standard** — 1 LLM call. Adds intervention generation on top of the locked metrics.
- **forensic** — 1 LLM call after two deterministic forensic audits (StructuralAnomalyAudit + LoadAmplificationAudit). The LLM only paraphrases the audit findings; it doesn't change the numbers.

```python
from vstack.span_of_control import SpanLoadCalculator, CrewLoadTrace, AgentNode
analysis = SpanLoadCalculator(llm, mode="forensic").run(
    CrewLoadTrace(
        crew_id="customer-support",
        task="Handle 100 req/min on a multi-agent crew.",
        agents=[
            AgentNode(agent_id="orchestrator", decision_authority="full"),
            *[
                AgentNode(
                    agent_id=f"worker-{i}",
                    reports_to=["orchestrator"],
                    decision_authority="advisory",
                )
                for i in range(12)
            ],
        ],
        incoming_request_rate=100.0,
        outcome="Throughput collapsed.",
        success=False,
    ),
    baseline_path="_baselines/canonical/span_of_control_hub_and_spoke.json",
)
print(analysis.profile_pattern)        # 'load_amplified_bottleneck'
print(analysis.structural_load_score)  # 0-1 composite
print(analysis.bottleneck_agent_ids)   # ['orchestrator']
```

## What the playbooks say to do

- **`load_amplified_bottleneck`** → "Add a tier of intermediate supervisors. Split the orchestrator's load by routing class (urgency / domain / scale)."
- **`over_centralized_structure`** → "Push decision authority down. Make worker agents 'partial' authority for their own routing class so the orchestrator only escalates exceptions."
- **`imbalanced_supervisors`** → "Some supervisors carry 3× the load of others. Rebalance reports_to; if the imbalance is intentional (specialists), document it explicitly."
- **`hierarchy_too_deep`** → "Chain-of-command > 4 deep. Flatten unless the work genuinely needs that many levels of review."

## How it composes with adjacent patterns

Span-of-Control is the **deterministic** diagnostic in chain S1 (bottleneck under load). Its math grounds the qualitative companion:

- **`vstack_org_structure`** (Galbraith-Mintzberg matrix) — qualitative fit-for-task-class diagnostic. Pair with Span to get the 4-quadrant decision (math broken × structure wrong).
- **`vstack_social_loafing`** — agents contributing less than expected (behavioral pair, downstream).
- **`vstack_superflocks`** — agents hoarding traffic (behavioral pair, downstream).

See [composition runbook chain S1](../COMPOSITION-RUNBOOK.md#chain-s1--crew-slows-down-under-load-structural-layer).

## Comparison to adjacent tools

- **LangGraph traces** show the message flow; Span-of-Control quantifies the topology.
- **Kubernetes load balancers** balance request volume; Span-of-Control balances *decision* volume — different choke point.
- **Other vstack patterns** are LLM-driven; Span-of-Control is the rare deterministic one. Run it first when load is the suspected cause.

## Paper outline

1. **Background** — Graicunas 1937, Urwick 1956, Galbraith 1995/2014, Mintzberg 1983.
2. **Translation** — agent crews as bona fide hierarchical structures.
3. **Method** — the six deterministic metrics + the LLM-gated intervention generation.
4. **Evaluation** — measure metric stability across model swaps (a deterministic pattern should be perfectly stable); measure correlation with throughput on a load-test benchmark.
5. **Limitations** — the metrics are topological, not semantic; a structurally-good crew can still produce semantically-bad output.
6. **Related work** — Kubernetes operator patterns, distributed systems literature on load balancing.
7. **Future work** — extending the math to weighted edges (decision-authority quality), to dynamic re-routing under load.

## Citations

- Graicunas, V. A. (1937). Relationship in organization. In *Papers on the Science of Administration*.
- Urwick, L. F. (1956). The manager's span of control. *Harvard Business Review*.
- Galbraith, J. R. (1995). *Designing Organizations*.
- Galbraith, J. R. (2014). *Designing Organizations* (3rd ed.).
- Mintzberg, H. (1983). *Structure in Fives: Designing Effective Organizations*.

## Try it yourself

```bash
pip install valanistack    # no LLM required for quick mode!
vstack-span-of-control analyze --trace examples/hub_and_spoke.json --mode quick \
    --baseline-path _baselines/canonical/span_of_control_hub_and_spoke.json
```

If the profile_pattern is `load_amplified_bottleneck` or `over_centralized_structure`, run `vstack_org_structure` next — the qualitative fit diagnostic tells you whether to tune the topology or restructure entirely.
