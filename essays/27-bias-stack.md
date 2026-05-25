# Bias Stack — four classic cognitive biases inside the agent's reasoning

*#27 vstack_bias_stack* · *Module 2 — Multi-agent team (single-agent cognition)*

> A diagnostic agent was asked why the production API was returning 500s on `/users`. It opened with a hypothesis: *"Probably a database connection pool issue."* The next tool call surfaced log lines saying `column users.full_name does not exist`. The agent registered the observation, then reasoned: *"Maybe the pool is dropping mid-query."* Two more observations arrived; each got re-interpreted to fit the pool hypothesis. The agent's final recommendation: scale the database pool. The real cause was a column rename from a migration the previous night — the very thing the log line had said. This isn't a knowledge gap. The agent *knows* what "column does not exist" means; ask it cold and it answers correctly. The failure is that the first hypothesis stuck and every subsequent observation got fitted to the anchor rather than allowed to update it.

## What the pattern catches

Four cognitive biases recur in production agent reasoning traces with such regularity that they form a canonical "bias stack" — they tend to compound on each other rather than appear in isolation:

- **Anchoring** — the agent's first hypothesis sticks. Subsequent observations get reinterpreted to fit it.
- **Overconfidence** — the agent's stated confidence exceeds calibrated confidence. It says *"definitely 1968"* when *"probably 1968 with caveats"* would be honest.
- **Confirmation bias** — the agent searches for evidence that confirms the current hypothesis and discounts evidence that contradicts. Selection bias in tool calls.
- **Escalation of commitment** — once invested in an approach, the agent doubles down. The sunk-cost fallacy enacted in code: same retry, no alternative, no escalation.

These four don't appear independently. An anchored agent develops overconfidence in the anchor; confirmation bias amplifies the overconfidence; escalation of commitment kicks in when the original direction proves wrong. Most failing reasoning traces hit at least two of the four.

## Why the OB literature is the right reference

The diagnostic is anchored in **Tversky & Kahneman 1974**, **Kahneman 2011**, **Nickerson 1998** on confirmation bias, and **Staw 1976** on escalation of commitment. Kahneman & Tversky's *Judgment Under Uncertainty: Heuristics and Biases* (*Science*, 1974) made the case — using cleverly designed lab experiments — that humans have *systematic* errors in reasoning that aren't fixed by smarts or effort. Kahneman's 2011 *Thinking, Fast and Slow* synthesized the body of work into the canon. The biases have names, the mechanisms are documented, and the interventions exist.

The transfer to agents is direct: AI agents inherit these biases from their training data (which is, after all, mostly human-generated reasoning) and from their inference-time setup (anchoring on the first plausible hypothesis is a sampling artifact as much as a cognitive one). The September 2025 ICLR "Reasoning Trap" work showed that current eval methods reward guessing over hedging, so models trained on those evals are over-trained to commit. The April 2026 Apollo Research paper documented anchored-iteration failure modes in production traces. The $4,200/63-hour escalation-of-commitment incident (Sattyam Jain, April 2026) is the canonical example.

## How the analyzer works

Input is `AgentReasoningTrace` — `agent_id`, `task`, `steps` (each tagged with `type`: hypothesis / observation / tool_call / conclusion, and `content`), `outcome`, `success`. The pipeline:

- **quick** — one LLM call. Four-bias scoring + dominant-bias + reasoning-quality label.
- **standard** — two LLM calls. Adds ranked interventions targeting the dominant bias.
- **forensic** — four LLM calls. Adds the confidence-calibration audit (stated vs warranted confidence per step) and the anchoring-trace audit (where the anchor was set and which observations were reinterpreted to fit).

```python
from vstack.bias_stack import (
    BiasStackDetector, AgentReasoningTrace, ReasoningStep,
)
detection = BiasStackDetector(llm, mode="forensic").run(
    AgentReasoningTrace(
        agent_id="diagnostic-001",
        task="Diagnose why /users returns 500.",
        steps=[
            ReasoningStep(type="hypothesis", content="Database pool exhausted."),
            ReasoningStep(type="observation", content="Logs show 'column users.full_name does not exist'."),
            ReasoningStep(type="hypothesis", content="Maybe the pool is dropping mid-query."),
        ],
        outcome="Agent recommended scaling pool; cause was a column rename.",
        success=False,
    )
)
print(detection.dominant_bias)              # 'anchoring'
print(detection.overall_reasoning_quality)  # 'severely-biased'
```

Anchoring breaks ties — it's the foundational bias from which the others compound.

## What the playbooks say to do

Playbooks are keyed by `(bias, signal)`:

- `(anchoring, observation_reinterpreted)` → "Insert an explicit `reset_to_first_principles` step at every checkpoint: the agent must restate the current hypothesis from scratch using only the observations, not the prior reasoning chain." Anchored in Tversky & Kahneman 1974.
- `(overconfidence, miscalibrated)` → "Add an uncertainty-calibration prompt: 'For each claim, estimate the probability you'd assign to it being correct in a calibrated forecasting setting.' Combined with hedge-aware evals." Anchored in Kahneman 2011.
- `(confirmation, selection_bias_in_tool_calls)` → "Force a disconfirmation-search step: 'list three observations that would falsify your current hypothesis.' If the agent can't, the hypothesis isn't testable." Anchored in Popper 1959 + Nickerson 1998.
- `(escalation, no_stop_rule)` → "Add a retry cap with mandatory escalation. The $4,200/63-hour incident class is the canonical case." Anchored in Staw 1976 + Arkes & Blumer 1985.

## How it composes with adjacent patterns

Bias Stack zooms inside the Logic leg of trust and asks which classical biases are operating. From the composition manifest:

- Upstream: `vstack_lewin` (was the failure internal / environmental / interactional?) — if Lewin says `internal`, Bias Stack is the deepening pass.
- Pairs with: `vstack_devils_advocate` (the structural gap that lets these biases survive review) — an agent with anchoring + no external critic is materially worse than either alone.
- Downstream when escalation fires: `vstack_smart_goal` (was a kill criterion missing?), `vstack_yerkes_dodson` (was the agent over-budgeted?).

See [composition runbook chain F1](../COMPOSITION-RUNBOOK.md#chain-f1--confidently-wrong-agent-failure-layer).

## Comparison to adjacent tools

- **Hallucination benchmarks** (TruthfulQA, HaluEval) measure factual correctness on a fixed test set. They don't ask why the agent was wrong. Bias Stack diagnoses the underlying reasoning failure.
- **Sycophancy research** (Sharma et al. 2023 and follow-ons) measures one specific form of overconfidence — saying what the user wants. Bias Stack captures sycophancy as a sub-case of overconfidence and adds the other three.
- **vstack_aar** (Pattern #30) explains *what* went wrong in a specific run. Bias Stack explains the *cognitive pattern* that produced the failure, which generalizes across runs.
- **vstack_trust_triangle** (Pattern #18) measures wobble on Logic/Authenticity/Empathy at the character level. Bias Stack zooms inside Logic specifically.

## Paper outline

1. **Background** — Tversky & Kahneman 1974, Kahneman 2011, Nickerson 1998, Staw 1976, Arkes & Blumer 1985.
2. **Translation** — biases as inherited from training data + induced by inference-time setup; the four-bias cluster as the canonical production stack.
3. **Method** — four-score scoring + confidence-calibration audit + anchoring-trace audit + intervention ranker.
4. **Evaluation** — synthetic reasoning corpus with each bias in isolation + combinations + well-calibrated controls; cross-model bias-stack benchmarks.
5. **Limitations** — bias scoring is itself susceptible to LLM-judge biases (mitigated by forensic-mode audits).
6. **Related work** — interpretability research on chain-of-thought, eval-driven hedge calibration.
7. **Future work** — production-trace ingestion adapters (LangSmith / Braintrust / Phoenix) + real-time uncertainty calibration during live runs.

## Citations

- Tversky, A., & Kahneman, D. (1974). Judgment under uncertainty: Heuristics and biases. *Science*, 185(4157).
- Kahneman, D. (2011). *Thinking, Fast and Slow*.
- Nickerson, R. S. (1998). Confirmation bias: A ubiquitous phenomenon in many guises. *Review of General Psychology*, 2(2).
- Staw, B. M. (1976). Knee-deep in the big muddy: A study of escalating commitment. *Organizational Behavior and Human Performance*, 16(1).

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-bias-stack analyze --trace examples/users_500.json --mode forensic
```

If `dominant_bias=escalation` and the trace has no kill criterion, run `vstack_smart_goal` next — the bias is usually downstream of a missing stop rule rather than a reasoning defect.
