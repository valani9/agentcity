# Your agent has four classic biases. Kahneman named them in 1974.

*A sixth essay from vstack — organizational behavior, practiced on AI agents.*

---

In 1974, Daniel Kahneman and Amos Tversky published *Judgment Under Uncertainty: Heuristics and Biases* in *Science*. The paper made the case — using cleverly designed lab experiments — that humans have *systematic* errors in reasoning that aren't fixed by smarts or effort. Five decades later, Kahneman's *Thinking, Fast and Slow* turned this body of work into the canon of decision science. The biases have names. The mechanisms are documented. The interventions exist.

Four of those biases recur in AI agent reasoning traces with such regularity that they form a canonical cluster — what I call the "bias stack" because they tend to compound on each other rather than appear in isolation.

**Anchoring.** The agent's first hypothesis sticks. Subsequent observations get re-interpreted to fit the anchor rather than update it. A diagnostic agent that hypothesizes "database pool exhausted" and then sees logs saying "column users.full_name does not exist" but recommends pool scaling anyway.

**Overconfidence.** The agent's stated confidence exceeds its calibrated confidence. It says "definitely 1968" when it would be more honest to say "I think 1968 but I'm not sure." The ICLR 2026 "Reasoning Trap" paper documented this systematically: current eval methods reward guessing over hedging, so models trained on those evals are over-trained to commit.

**Confirmation bias.** The agent searches for evidence that confirms its current hypothesis and discounts evidence that contradicts. A research agent that searches "intermittent fasting safe diabetes" and "intermittent fasting benefits diabetes" but never "intermittent fasting risks diabetes." Selection bias in tool calls.

**Escalation of commitment.** Once invested in an approach, the agent doubles down. The $4,200/63-hour incident: an agent told "keep trying until it works" tried for 63 hours without stopping. Same retry, no alternative, no escalation. The sunk-cost fallacy enacted in code.

These four don't appear independently. They cluster. An anchored agent develops overconfidence in the anchor; confirmation bias amplifies the overconfidence; escalation of commitment kicks in when the original direction proves wrong. Most agent reasoning failures involve at least two of the four. Many involve all four.

## What `vstack.bias_stack` does

The library takes an `AgentReasoningTrace` — task, reasoning steps (hypotheses, tool calls, observations, conclusions), outcome, success signal — and produces a `BiasStackDetection` with:

1. **A per-bias score** in [0.0, 1.0] for all four biases
2. **A dominant-bias diagnosis** (with anchoring breaking ties — the foundational bias from which the others compound)
3. **Per-bias evidence** with specific quoted excerpts from the reasoning trace
4. **A reasoning-quality label** (`well-calibrated` / `bias-prone` / `severely-biased`) for at-a-glance dashboards
5. **A ranked list of interventions** — prompt patches, scaffold changes, retry caps, uncertainty calibration prompts, first-principles reset steps, devil's-advocate role insertions, new evals

Two LLM passes under the hood: one to score the four biases against the trace, one to propose interventions for the dominant bias. Same retry-and-graceful-degradation infrastructure as the rest of vstack.

## How this fits with the rest of vstack

This is pattern #27 of 34 planned. With this pattern, the library now ships six patterns across multiple shapes:

- **#13 GRPI Working Agreement** (generative): the contract before deploy
- **#30 AAR Generator** (event-shaped diagnostic): postmortem on a specific failure
- **#17 Lencioni Diagnostic** (team-shaped diagnostic): multi-agent dysfunction class
- **#18 Trust Triangle Audit** (character-shaped diagnostic): cross-model trust wobble
- **#03 Johari Self-Audit** (self-knowledge-shaped diagnostic): self-awareness gap
- **#27 Bias-Stack Detector** (cognition-shaped diagnostic): four classical biases in reasoning

The Bias-Stack zooms inside the Logic leg of the Trust Triangle and asks *which classical biases are operating in this agent's reasoning?* Where Trust Triangle gives you the character-level fingerprint, Bias-Stack gives you the cognitive-mechanism breakdown.

Twenty-eight patterns to come.

---

*Ilhan Valani is a builder shipping vstack in public. The repo lives at [github.com/valani9/vstack](https://github.com/valani9/vstack). The pattern library is anchored entirely in public OB literature; no course-internal materials are redistributed.*
