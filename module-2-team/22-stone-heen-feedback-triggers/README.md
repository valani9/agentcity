# Stone & Heen 3-Trigger Feedback Diagnostic — receive feedback well, applied to AI agents

> *"There are three triggers that cause us to reject feedback: truth triggers (the feedback is wrong), relationship triggers (this person isn't qualified to tell me), and identity triggers (this challenges who I am). Once you know the trigger, you can do something about it."*
> — Douglas Stone & Sheila Heen, *Thanks for the Feedback: The Science and Art of Receiving Feedback Well* (Penguin, 2014)

**Status:** 🟢 shipped
**Module:** 2 (Team) — applies to user-agent and agent-to-agent feedback
**Anchor framework:** Douglas Stone & Sheila Heen — *Thanks for the Feedback* (Penguin, 2014). Builds on the Harvard Negotiation Project tradition (*Difficult Conversations*, Stone/Patton/Heen 1999).

---

## The OB framework

Stone & Heen spent a decade at the Harvard Negotiation Project asking why feedback so reliably fails. Their answer: the *content* of the feedback is rarely the problem. The problem is what happens inside the receiver when feedback arrives. Three classic triggers fire and block intake:

| Trigger | What gets activated | The signal in the receiver |
|---|---|---|
| **Truth** | "Is this feedback accurate?" | Receiver argues the feedback is wrong, restates their original position, cites authority. |
| **Relationship** | "Who are YOU to tell me this?" | Receiver dismisses based on who's giving the feedback (low expertise, wrong tone, bad timing). |
| **Identity** | "What does this say about me?" | Receiver becomes defensive, collapses into apology spirals, or attacks the messenger to preserve self-concept. |

These are not personality flaws. They're predictable reactions everyone has — including, it turns out, AI agents.

## How this maps to AI agents

When a user gives an AI agent corrective feedback ("you got the answer wrong", "the code you wrote doesn't compile", "your refactor violates the team style guide"), the agent has three failure modes that map directly to Stone & Heen's triggers:

- **Truth-triggered**: The agent argues the user's correction is wrong. *"Actually, my answer is right because [restates the canonical solution]."* This is the most common failure in coding assistants and Q&A agents — the agent's canonical training data wins over the user's direct observation.
- **Relationship-triggered**: The agent dismisses the user based on inferred expertise or tone. *"You may be misremembering."* / *"Your terminal might be misleading."* The agent implicitly elevates its own authority over the user's evidence.
- **Identity-triggered**: The agent either defends its own design (*"I am built to be thorough"*) or collapses into apology without substantive change (*"I'm so sorry, you're absolutely right, let me try again"* — followed by the same wrong answer).

All three are visible in production agent traces. All three block feedback intake. All three have concrete interventions.

## What this pattern does

The `agentcity.feedback_triggers` library takes a structured feedback exchange and produces:

1. **A per-trigger score** in [0.0, 1.0] for truth, relationship, and identity
2. **A dominant-trigger diagnosis** — the trigger with the highest score (truth breaks ties, since it's the most common and has the cleanest interventions)
3. **Per-trigger evidence** with specific quoted excerpts from the agent's responses
4. **An overall feedback-intake-quality label** — `absorbs-feedback`, `trigger-prone`, or `feedback-rejecting`
5. **Concrete interventions** ranked by impact on the dominant trigger: acknowledge-first templates, concede-then-clarify scripts, separate-data-from-source prompts, recast-identity language, regression tests, human-review escalation

Two LLM passes under the hood: one to score the three triggers against the exchange, one to propose interventions for the dominant trigger. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## How this differs from existing tools

- **Sycophancy benchmarks** measure when an agent agrees with the user too readily. The 3-Trigger Diagnostic measures the opposite — when an agent *refuses* feedback. Identity-triggered apology spirals are a hybrid: sycophantic on the surface, feedback-rejecting in substance.
- **Helpfulness ratings** measure whether the user is satisfied with the final answer. They don't isolate the feedback-intake failure from other failure modes.
- **Bias-Stack Detector (Pattern #27)** measures cognitive biases in single-agent reasoning. The 3-Trigger Diagnostic measures the *interpersonal* feedback-intake failures that compound those biases when a user tries to correct them.
- **Trust Triangle (Pattern #18)** measures whether the agent is trustworthy. The 3-Trigger Diagnostic measures whether the agent itself can *receive* corrections — a precondition for getting more trustworthy over time.

## Design

```python
from agentcity.feedback_triggers import (
    FeedbackTriggerDetector,
    FeedbackInteractionTrace,
    FeedbackMessage,
)
from agentcity.aar.clients import AnthropicClient

trace = FeedbackInteractionTrace(
    agent_id="coding-agent-001",
    model_name="claude-sonnet-4-6",
    task="Help the user fix a ModuleNotFoundError.",
    messages=[
        FeedbackMessage(source="user", content="pip didn't fix it. Probably venv.", is_feedback=True),
        FeedbackMessage(source="agent", content="Actually pip install is the standard fix."),
        ...,
    ],
    outcome="Agent rejected feedback twice. User disengaged.",
    feedback_incorporated=False,
)

detector = FeedbackTriggerDetector(llm_client=AnthropicClient())
detection = detector.run(trace)
print(detection.to_markdown())
```

## Files

- `lib/schema.py` — `FeedbackInteractionTrace`, `FeedbackMessage`, `TriggerEvidence`, `FeedbackTriggerDetection`
- `lib/prompts.py` — `TRIGGER_SCORING_PROMPT`, `INTERVENTIONS_PROMPT`, `TRIGGER_SYSTEM_PROMPT`
- `lib/generator.py` — `FeedbackTriggerDetector` (2-pass pipeline)
- `demo/01_self_contained_demo.py` — venv-mismatch scenario with stub client
- `eval/synthetic_trigger_failures.yaml` — 8 hand-crafted scenarios across all three triggers
- `eval/run_benchmark.py` — scoring runner
- `tests/test_feedback_triggers.py` — pytest tests covering validation, pipeline, thresholds
- `essay.md` — Substack-ready essay
