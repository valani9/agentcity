# AAR Generator — Benchmarks

The AAR Generator is benchmarked on its ability to (a) produce a high-quality AAR from a known agent failure trace, and (b) **improve agent performance on subsequent runs** when its prompt-patch suggestion is applied.

## Planned benchmarks

| Dataset | Task | Metric | Status |
|---|---|---|---|
| **SWE-Bench-multi** | Failed coding tasks across multiple repos | Δ-success-rate after AAR-derived prompt patch is applied | ⚪ TODO |
| **GAIA** | Multi-step reasoning failures | Lesson-quality score (LLM-graded against gold-standard postmortems) | ⚪ TODO |
| **AppWorld** | Long-horizon application tasks | Δ-success-rate + Δ-token-cost after lesson injected into agent memory | ⚪ TODO |
| **AgentBench** | Broad task suite | Per-task AAR quality + retry-improvement rate | ⚪ TODO |
| **Synthetic failures** | Hand-crafted multi-agent traces tagged with known OB-failure patterns | Did the AAR correctly identify the OB framework? | ⚪ TODO |

## Methodology

For each benchmark task:

1. **Pre-AAR baseline.** Run the agent on the task. Record success rate, token cost, retry count.
2. **Failure trace capture.** When the agent fails, capture the trace.
3. **AAR generation.** Run `AARGenerator(...).generate(trace)`.
4. **Intervention application.** Apply the AAR's `suggested_prompt_patch` and/or inject `lesson_record_for_memory`.
5. **Post-AAR re-run.** Run the agent again on the same task with the intervention applied.
6. **Delta measurement.** Compare success rate, token cost, retry count, latency.

## LLM-grader rubric (for AAR quality scoring)

For benchmarks without a clean automated metric, an LLM grader (model: claude-opus-4-7) scores the AAR on a 0-5 scale across four dimensions:

| Dimension | What we're scoring |
|---|---|
| **Goal fidelity** | Does the AAR's restated goal match what the agent was actually told to do? |
| **Results fidelity** | Does the AAR's results narrative match the trace evidence? |
| **Lesson plausibility** | Are the named failure patterns defensible from the trace? |
| **Intervention concreteness** | Is the suggested prompt patch / eval test / scaffold change implementable as written? |

A second LLM (model: gpt-5) re-scores 20% of the corpus for inter-grader reliability.

## How to contribute a benchmark

If you have a public agent-failure dataset or a custom corpus and want to benchmark the AAR Generator on it, open an issue.
