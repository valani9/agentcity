# Plus/Delta Inter-Agent Feedback Format — structured agent-on-agent feedback, applied to multi-agent crews

> *"The hardest thing about giving feedback is keeping it specific and behavioral. 'Good work' is not feedback. 'You did a great job' is not feedback. Feedback is: 'When you opened the meeting by restating last week's commitments, the team got to the substance in five minutes instead of twenty. Keep doing that.'"*
> — Brené Brown, *Dare to Lead* (Random House, 2018), riffing on the plus/delta format from the facilitator canon

**Status:** 🟢 shipped — fourth generative pattern in vstack
**Module:** 2 (Team) — multi-agent crews
**Anchor framework:** The plus/delta format originated in Joiner Associates training materials in the 1990s and became the dominant retrospective protocol across agile, lean, and design-thinking communities. Re-popularized by Brené Brown's *Dare to Lead* (2018) and Esther Derby & Diana Larsen's *Agile Retrospectives* (Pragmatic, 2006). Variants include "start/stop/continue" and "what worked / what to change."

---

## The OB framework

The plus/delta format is brutally simple and has one ironclad rule:

| | What it is | What it is NOT |
|---|---|---|
| **Plus** | What worked — specific, behavioral, reusable next time. "The way you decomposed the problem into three steps was the move that made the next agent's job tractable." | Generic affirmation: "good work", "great structure", "well done". These are not pluses; they are noise. |
| **Delta** | What to change next time — specific, behavioral, names the alternative. "Before each tool call, restate the goal in one sentence." | Generic critique: "could be better", "needs improvement", "more clarity". These are not deltas; they are also noise. |

The format is intentionally **forward-looking**, not retrospective-judgmental. A plus answers *"what should you keep doing?"* A delta answers *"what would I do differently, and what's the alternative?"* Both must be behavioral and specific. Both must cite evidence from the artifact under review.

The format's enduring usefulness — across thirty years of meeting-design literature — is that it disciplines the reviewer to **stop producing generic praise and generic critique.** When a reviewer's plus is "you did a great job", the format requires them to either replace it with a specific behavioral observation or drop it entirely. Same for the delta side.

## How this maps to AI agents

Multi-agent AI crews almost universally produce generic feedback. The default agent-on-agent review looks like:

- *Reviewer agent:* "LGTM."
- *Reviewer agent:* "Looks good to me."
- *Reviewer agent:* "Good work. This could be better in some places."

None of these are actionable. The subject agent can't tell *which* parts to keep doing or *which* parts to change. The reviewer agent is producing the appearance of review without doing the work of review — a textbook social-loafing pattern (see Pattern #15).

The Plus/Delta Feedback Format generator replaces this with a structured artifact:

```
+ 1: Splitting the middleware into 3 modules gave each function ONE responsibility.
  Evidence: Module 1 only validates; Module 2 only loads; Module 3 only routes.
  Impact: A new engineer can find the validation logic without reading routing logic.
  Keep doing: Always lead with module-level single responsibility on auth code.

Δ 1: validate_token swallows the underlying exception, so errors lose information. (critical)
  Evidence: Module 1 except Exception: return False. Original decode_jwt error is lost.
  Impact: Violates success criterion #4 (errors surface underlying cause).
  Alternative: Catch jwt.ExpiredSignatureError, jwt.InvalidSignatureError separately
               and raise typed AuthError subclasses carrying the underlying cause.
```

This is what a productive agent-on-agent review looks like. The format enforces the specificity.

## What this pattern does

The `vstack.plus_delta` library takes a `FeedbackRequest` with:

- **Reviewer agent** and **subject agent** names
- **Task context** — what the team is working on overall
- **Contribution summary** + **contribution artifact** — what's being reviewed
- **Success criteria** for the task (optional but improves delta quality)
- **Style** preference: `balanced`, `delta-leaning`, or `plus-leaning`
- **Max items per category** (default 4)

and produces a `PlusDeltaFeedback` artifact with:

1. **Plus items** with statement + evidence + impact + (optional) keep-doing instruction
2. **Delta items** with statement + evidence + impact + alternative behavior + severity (`nit` / `moderate` / `critical`)
3. **Optional commitments** (reviewer or subject explicit commitments for next round)
4. **Overall assessment**: `keep-going` / `iterate` / `rework`
5. **Feedback quality score** in [0.0, 1.0] (self-reported specificity)

Single LLM pass. The generator enforces max-items caps, infers the overall assessment from delta severities if the LLM omitted it, and reconciles the quality score. Same retry / graceful-degradation infrastructure as the rest of vstack.

Two output formats:
- `to_markdown()` — full structured artifact for storage / display
- `to_inline_feedback()` — condensed inline block for chat-style returns

## How this differs from existing tools

- **Pattern #22 Stone & Heen 3-Trigger Feedback Diagnostic** measures whether the agent can *receive* feedback. Pattern #23 (this) generates the *structured feedback itself* for one agent to deliver to another. They're complements: #23 produces feedback that's actionable; #22 catches when #23-quality feedback gets rejected anyway.
- **Pattern #15 Social Loafing Detector** measures whether reviewer agents are producing rubber-stamps. Pattern #23 *gives them something specific to produce instead* — converting "LGTM" reviewers into substantive critics.
- **Pattern #25 Group Decision Models** picks the aggregation method; Pattern #23 produces the structured feedback that informs each agent's vote.
- **LLM-as-judge** is a different shape — a single judge produces a verdict. Plus/Delta is *peer review* — one agent gives feedback to a peer, with explicit reusable structure.

## Design

```python
from vstack.plus_delta import (
    PlusDeltaFeedbackGenerator,
    FeedbackRequest,
)
from vstack.aar.clients import AnthropicClient

request = FeedbackRequest(
    reviewer_agent="senior-eng",
    subject_agent="junior-eng",
    task_context="Refactor auth middleware for clarity.",
    contribution_summary="Junior split the middleware into 3 modules.",
    contribution_artifact="<the actual code diff>",
    success_criteria=[
        "Code is readable in <10 minutes",
        "No new dependencies",
        "Errors surface root cause",
    ],
    style="balanced",
)

generator = PlusDeltaFeedbackGenerator(llm_client=AnthropicClient())
feedback = generator.run(request)
print(feedback.to_markdown())
# Or for inline chat returns:
print(feedback.to_inline_feedback())
```

## Files

- `lib/schema.py` — `FeedbackRequest`, `PlusItem`, `DeltaItem`, `Commitment`, `PlusDeltaFeedback`
- `lib/prompts.py` — `PLUS_DELTA_PROMPT`, `PLUS_DELTA_SYSTEM_PROMPT`
- `lib/generator.py` — `PlusDeltaFeedbackGenerator` (single-pass pipeline with post-processing)
- `demo/01_self_contained_demo.py` — junior-eng auth-refactor scenario with detailed plus/delta
- `eval/synthetic_feedback_requests.yaml` — 8 scenarios across `keep-going` / `iterate` / `rework`
- `eval/run_benchmark.py` — scoring runner
- `tests/test_plus_delta.py` — pytest tests covering validation, pipeline, item caps, overall inference, malformed-input handling
- `essay.md` — Substack-ready essay
