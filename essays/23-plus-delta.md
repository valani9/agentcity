# Plus/Delta — "LGTM" is not feedback

*#23 vstack_plus_delta* · *Module 2 — Multi-agent team (generative)*

> A senior-eng agent received a junior agent's auth-middleware refactor for review. The full review was one line: *"LGTM. Good work on the structure."* The junior shipped. Three days later, an incident: `validate_token` was catching `Exception` and returning `False`, losing the underlying error. Ops couldn't tell whether the failure was token expiration, signature mismatch, or malformed payload. The review wasn't *wrong* — the structure really was good. The review had also failed to say *anything* about the error-handling, which was the actual production hazard. The senior-eng agent had produced the appearance of review without doing the work of review. It had also given the junior nothing actionable: no instruction on what to repeat, no instruction on what to change. Three days of incident toil traced back to four words and the absence of a forcing format.

## What the pattern catches

Multi-agent crews almost universally produce generic feedback. The default agent-on-agent review looks like:

- *Reviewer:* "LGTM."
- *Reviewer:* "Looks good to me."
- *Reviewer:* "Good work. This could be better in some places."

None of these are actionable. The subject agent can't tell *which* parts to keep doing or *which* parts to change. The reviewer is producing the *shape* of review without the substance — a textbook social-loafing pattern (#15) with a verification-role mask.

The plus/delta format is a structural fix. Two columns, an ironclad rule. **Plus**: what worked, *specific, behavioral, reusable*. Not "good structure" but *"splitting the middleware into three modules gave each function ONE responsibility, which made the next agent's job tractable."* **Delta**: what to do differently, *specific, behavioral, names the alternative*. Not "could be better" but *"before each tool call, restate the goal in one sentence."*

The format disciplines the reviewer to stop producing generic praise and generic critique. When asked to apply the format strictly, most reviewers discover they have less to say than they thought — and that what they have to say is much more actionable.

The pattern answers: *what does substantive agent-on-agent feedback on this specific artifact look like?*

## Why the OB literature is the right reference

The diagnostic is anchored in two primary lineages: Joiner Associates 1990s facilitator training materials (the original format definition) and Brown 2018 (*Dare to Lead*, the modern re-popularization). Supporting anchors include Stone & Heen 2014 (the companion text — plus/delta works because it neutralizes the three feedback triggers) and Doran 1981 (SMART goals; the keep-doing and alternative fields lean on goal-specificity).

**The Joiner / Brown lineage's core claim** is that the hardest thing about giving feedback is keeping it specific and behavioral. *"Good work"* is not feedback. *"You did a great job"* is not feedback. Feedback is: *"When you opened the meeting by restating last week's commitments, the team got to the substance in five minutes instead of twenty. Keep doing that."* The format's enduring usefulness across thirty years of meeting-design literature is that it disciplines the reviewer to be specific or drop the item entirely.

The transfer to agent crews is exact because RLHF-trained reviewer agents *gravitate* toward generic affirmation. The training rewards politeness; politeness reads as "LGTM." The structural format forces a different output shape — evidence + impact + alternative per delta item — that LGTM cannot satisfy.

## How the analyzer works

Input is `FeedbackRequest` — `reviewer_agent`, `subject_agent`, `task_context`, `contribution_summary`, `contribution_artifact` (the actual artifact being reviewed), `success_criteria` (optional, sharpens deltas), `style` (`balanced` / `delta-leaning` / `plus-leaning`), `max_items` (default 4). The pipeline:

- **quick** — one LLM call. Plus + delta items + overall assessment.
- **standard** — two LLM calls. Adds evidence/impact/alternative per item + ranked commitments.
- **forensic** — four LLM calls. Adds `BehavioralVsGenericAudit` (rejects items that fail the specificity rule), reviewer/subject commitments, and composition handoffs.

```python
from vstack.plus_delta import PlusDeltaFeedbackAnalyzer, FeedbackRequest
feedback = PlusDeltaFeedbackAnalyzer(llm, mode="forensic").run(
    FeedbackRequest(
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
)
print(feedback.to_markdown())          # full structured artifact
print(feedback.to_inline_feedback())   # condensed chat-style block
print(feedback.overall_assessment)     # 'keep-going' / 'iterate' / 'rework'
```

The prompt enforces the behavioral-specificity rule explicitly: no `PlusItem` may be a generic affirmation; no `DeltaItem` may be a generic critique. Generic items get replaced or dropped. Post-processing enforces max-item caps, infers `overall_assessment` from delta severities if the LLM omits it, and reconciles the quality score.

## What the playbooks say to do

The generated artifact is itself the intervention. Each item carries:

- **`PlusItem`** → `statement` + `evidence` (citing the artifact) + `impact` + optional `keep_doing` instruction for next round.
- **`DeltaItem`** → `statement` + `evidence` + `impact` + `alternative_behavior` + `severity` (`nit` / `moderate` / `critical`).
- **`Commitment`** → reviewer or subject commits to a specific change for next round.

The format closes three failure modes: rubber-stamp review ("LGTM" is no longer a valid output once evidence + impact + alternative is required per delta), generic critique that can't be acted on (forcing the reviewer to name the alternative behavior gives the subject a concrete action), and praise that hides risk (the format requires at least one delta even on mostly-good contributions — preventing the safe retreat into praise that obscured the auth-refactor hazard above).

## How it composes with adjacent patterns

Plus/Delta is the **fourth generative pattern** in vstack — it doesn't diagnose, it produces structured artifacts. Composes with:

- `vstack_stone_heen` (#22) is the *complement* — plus/delta produces *high-quality* feedback; Stone & Heen catches when even high-quality feedback gets rejected by truth/relationship/identity triggers.
- `vstack_social_loafing` (#15) catches reviewer rubber-stamping; plus/delta gives reviewers something *substantive to produce instead*.
- `vstack_grpi` (#13) generates the team contract; plus/delta is the per-contribution feedback format within that contract.
- `vstack_smart_goal` (#24) and `vstack_aar` (#30) compose naturally — plus/delta sits between SMART's individual goals and AAR's event-shaped postmortems as the contribution-shaped peer review.

## Comparison to adjacent tools

- **LLM-as-judge** is a different shape — a single judge produces a verdict against a rubric. Plus/Delta is *peer review* — one agent gives structured feedback to a peer with explicit reusable structure.
- **CrewAI / LangGraph review hooks** capture review messages without enforcing structure; plus/delta enforces the structure.
- **`vstack_devils_advocate` (#28)** measures whether critique is structurally present; plus/delta produces the critique itself in a form the subject can act on.

## Paper outline

1. **Background** — Joiner Associates 1990s, Brown 2018, Derby & Larsen 2006, Stone & Heen 2014, Doran 1981.
2. **Translation** — RLHF politeness bias produces generic affirmation; the format is the structural fix.
3. **Method** — single-pass generation with behavioral-specificity rule enforcement, max-item caps, overall-assessment inference.
4. **Evaluation** — paired benchmark: same artifact reviewed with vs without plus/delta enforcement; measure downstream incident rate, subject-agent revision quality, reviewer specificity scores.
5. **Limitations** — needs the artifact in-context; very long artifacts may truncate.
6. **Related work** — agile retrospective tooling; code-review automation literature.
7. **Future work** — auto-graded feedback quality; plus/delta as a default mode in multi-agent review hooks.

## Citations

- Brown, B. (2018). *Dare to Lead: Brave Work. Tough Conversations. Whole Hearts*. Random House.
- Derby, E., & Larsen, D. (2006). *Agile Retrospectives: Making Good Teams Great*. Pragmatic Bookshelf.
- Stone, D., & Heen, S. (2014). *Thanks for the Feedback*. Penguin.
- Doran, G. T. (1981). There's a S.M.A.R.T. way to write management's goals and objectives. *Management Review*, 70(11), 35-36.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-plus-delta generate --request examples/auth_refactor.json --mode forensic
```

Generate plus/delta feedback as the default in every agent-on-agent review hook. If a downstream incident traces to feedback that should have caught the issue, pair with `vstack_stone_heen` to verify whether the feedback was rejected at intake rather than missing at generation.
