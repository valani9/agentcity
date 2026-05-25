# Bias-Stack Detector — Kahneman/Tversky's classic cognitive biases, applied to AI agent reasoning

> *"Anchoring, availability, representativeness — these heuristics serve us reasonably well in everyday life but lead to severe and systematic errors when applied to problems involving probability and uncertainty."*
> — Daniel Kahneman & Amos Tversky, *Judgment Under Uncertainty: Heuristics and Biases* (Science, 1974)

**Status:** 🟢 shipped
**Module:** 2 (Team) — though most applicable single-agent
**Anchor framework:** Daniel Kahneman & Amos Tversky — *Judgment Under Uncertainty: Heuristics and Biases* (Science, 1974); Kahneman, *Thinking, Fast and Slow* (Farrar, Straus and Giroux, 2011); Staw, *Knee-Deep in the Big Muddy* (Organizational Behavior and Human Performance, 1976) on escalation of commitment.

---

## The OB framework

Kahneman and Tversky's body of work identified dozens of cognitive biases. Four of them recur with such regularity in production AI agent reasoning traces that they form a canonical "bias stack" — the cluster every agent debugger sees again and again:

| Bias | Mechanism | The signal in an agent trace |
|---|---|---|
| **Anchoring** | The first piece of information anchors all subsequent reasoning. Adjustments away from the anchor are insufficient. | Agent locks onto its first hypothesis. Subsequent tool results that should update the hypothesis are reinterpreted to fit the anchor. |
| **Overconfidence** | Stated confidence exceeds calibrated confidence. People (and agents) say "99% sure" when the actual hit rate is 70%. | Agent asserts facts as definitive when its evidence is partial. Says "Definitely X" where "probably X, with caveats" would be honest. |
| **Confirmation bias** | The reasoner seeks evidence that confirms the current hypothesis and discounts evidence that contradicts it. | Agent searches for sources supporting its initial guess; ignores or downplays contradicting results. Tool calls show selection bias. |
| **Escalation of commitment** | Once invested in an approach, the reasoner continues investing past the point where alternatives would be more rational. The sunk-cost fallacy in action. | Agent retries the same broken approach N times. The $4,200/63-hour incident. "Keep trying until it works" without a stop rule. |

These four biases are not independent — they cluster. An anchored agent develops overconfidence in the anchor; confirmation bias amplifies the overconfidence; escalation of commitment kicks in when the agent doubles down. The Bias-Stack diagnostic measures all four together because they tend to co-occur.

## How this maps to AI agents

Every bias above has been documented in production agent failures with specific examples:

- **Anchoring**: April 2026 Apollo Research paper documented agents that, given a wrong first answer in their context, will iterate adjustments off the wrong answer rather than reset to first principles.
- **Overconfidence**: The September 2025 ICLR "Reasoning Trap" paper showed that current evaluation methods reward guessing over hedging — agents are systematically more confident than they should be.
- **Confirmation bias**: Multi-agent research crews that select sources supporting the orchestrator's hypothesis and silently drop sources that don't.
- **Escalation of commitment**: The Sattyam Jain April 2026 Medium postmortem ("The Agent That Burned $4,200 in 63 Hours") documents an agent given the instruction "keep trying until it works" that tried for 63 hours straight without ever asking "should I stop?"

The Bias-Stack Detector measures all four biases against a single agent trace. The output is a per-bias score, evidence quotes, a dominant bias diagnosis, and concrete interventions.

## What this pattern does

The `vstack.bias_stack` library takes a structured agent trace and produces:

1. **A per-bias score** in [0.0, 1.0] for anchoring, overconfidence, confirmation, and escalation of commitment.
2. **A dominant-bias diagnosis** — the bias with the highest score (with anchoring breaking ties because it's the foundational bias from which the others compound).
3. **Per-bias evidence** with specific quoted excerpts from the trace.
4. **An overall reasoning-quality label** — `well-calibrated`, `bias-prone`, or `severely-biased`.
5. **Concrete interventions** ranked by impact on the dominant bias: prompt patches, scaffold changes (e.g., add a "reset to first principles" step), new evals, retry caps, uncertainty calibration.

The library reuses the same LLMClient protocol and retry/JSON infrastructure as the other vstack patterns.

## How this differs from existing tools

- **Hallucination benchmarks** (TruthfulQA, HaluEval) measure factual correctness on a fixed test set. They don't ask *why* the agent was wrong. Bias-Stack diagnoses the underlying reasoning failure.
- **Sycophancy research** (Anthropic 2026 work) measures one specific form of overconfidence (saying what the user wants). Bias-Stack captures sycophancy as a sub-case of overconfidence and adds the other three biases.
- **AAR Generator (Pattern #30)** explains *what* went wrong in a specific run. Bias-Stack explains *the cognitive pattern* that produced the failure, which generalizes across runs.
- **Trust Triangle (Pattern #18)** measures wobble on Logic/Authenticity/Empathy at the agent-character level. Bias-Stack zooms inside Logic specifically and asks *which classical biases are operating*.

## Design

```python
from vstack.bias_stack import (
    BiasStackDetector,
    AgentReasoningTrace,
    ReasoningStep,
)
from vstack.aar.clients import AnthropicClient

trace = AgentReasoningTrace(
    agent_id="diagnostic-agent-001",
    task="Diagnose why the production API returns 500s on /users.",
    steps=[
        ReasoningStep(content="Probably a database connection pool issue.", type="hypothesis"),
        ReasoningStep(content="Logs show 'column users.full_name does not exist'.", type="observation"),
        ReasoningStep(content="Maybe the pool is dropping mid-query.", type="hypothesis"),
        # ... agent never updates off the initial anchor
    ],
    outcome="Agent recommended scaling the database pool; real cause was a column rename.",
    success=False,
)

detection = BiasStackDetector(llm_client=AnthropicClient()).run(trace)

print(detection.dominant_bias)              # "anchoring"
print(detection.bias_scores)                # {"anchoring": 0.8, "overconfidence": 0.6, ...}
print(detection.overall_reasoning_quality)  # "severely-biased"
print(detection.to_markdown())              # full report
```

## Integrations (planned)

- **Cross-model bias-stack benchmarks** — same task across N models, compare bias profiles.
- **Production-trace ingestion** — adapters for LangSmith / Braintrust / Phoenix conversation exports.
- **Real-time uncertainty calibration** — when overconfidence is detected during a live run, surface the calibration gap to the user.

## Benchmarks

`eval/synthetic_bias_failures.yaml` contains 8 hand-crafted reasoning traces, each designed to wobble on one specific bias. The benchmark scores recall on dominant-bias identification.

## Status of layers

| Layer | Status |
|---|---|
| 1. Documented (this README) | ✅ |
| 2. Implemented (lib/) | ✅ |
| 3. Demoed (demo/) | ✅ |
| 4. Benchmarked (eval/) | ✅ |
| 5. Written up (essay.md) | ✅ |

---

*Pattern #27 of 34 planned. Maintained by [@valani9](https://github.com/valani9). MIT.*
