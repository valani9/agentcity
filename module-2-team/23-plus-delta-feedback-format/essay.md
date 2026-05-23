# "LGTM" is not feedback. Brené Brown explained why in 2018.

*A twenty-first essay from AgentCity — organizational behavior, practiced on AI agents.*

---

A senior-eng agent receives a junior agent's auth-middleware refactor for review. The default agent-on-agent review goes like this:

> *Senior-eng: "LGTM. Good work on the structure."*

That's the review. The junior ships. Three days later, an incident: validate_token catches `Exception` and returns `False`, losing the underlying error. Ops can't tell whether the failure is token expiration, signature mismatch, or malformed payload. The original review had said "good work on the structure" — which was true. It also had failed to say *anything* about the error-handling, which was the actual production hazard. The review wasn't wrong; it was just *not feedback*.

In *Dare to Lead* (2018), Brené Brown crystallized a finding from thirty years of facilitator-canon training. **The hardest thing about giving feedback is keeping it specific and behavioral.** "Good work" is not feedback. "You did a great job" is not feedback. *Feedback* is: *"When you opened the meeting by restating last week's commitments, the team got to the substance in five minutes instead of twenty. Keep doing that."*

The format facilitators converged on — going back to Joiner Associates training materials in the 1990s, and embedded in agile retrospective practice via Esther Derby & Diana Larsen's *Agile Retrospectives* (2006) — is **plus/delta.** Two columns, with an ironclad rule.

**Plus.** What worked. *Specific.* *Behavioral.* *Reusable next time.* Not "good structure" but "splitting the middleware into three modules gave each function ONE responsibility, which is what made the next agent's job tractable." A plus answers: what specifically should you keep doing?

**Delta.** What to do differently. *Specific.* *Behavioral.* *Names the alternative.* Not "could be better" but "before each tool call, restate the goal in one sentence." A delta answers: what should you change, and what's the alternative behavior?

The format is intentionally forward-looking, not retrospective-judgmental. Pluses are about repeatable behavior; deltas are about specific changes. Both must be behavioral and specific. Both must cite evidence from the artifact under review.

The format's enduring usefulness across thirty years of meeting-design literature is that it disciplines the reviewer to **stop producing generic praise and generic critique.** When a reviewer's plus is "you did a great job," the format requires them to either replace it with a specific behavioral observation or drop it. Same for the delta side. Most reviewers, asked to apply the format strictly, discover they have less to say than they thought — and that what they have to say is much more actionable.

Multi-agent AI crews need this discipline badly. The default agent-on-agent review is overwhelmingly "LGTM" / "looks good" / "could be improved." None of these are actionable. The subject agent can't tell *which* parts to keep doing or *which* parts to change. The reviewer agent is producing the *appearance* of review without doing the *work* of review — the canonical social-loafing pattern in multi-agent crews.

## What `agentcity.plus_delta` does

The library takes a `FeedbackRequest` with:

- The **reviewer** and **subject** agent names
- The **task context** — what the team is working on
- The **contribution summary** + the actual **artifact** being reviewed
- **Success criteria** for the task (optional but sharpens the delta items)
- A **style** preference (balanced / delta-leaning / plus-leaning)

and produces a `PlusDeltaFeedback` artifact with:

1. **Plus items** — each with statement, evidence (citing the artifact), impact, and an optional keep-doing instruction for next round
2. **Delta items** — each with statement, evidence, impact, the alternative behavior, and a severity (`nit` / `moderate` / `critical`)
3. **Optional commitments** — reviewer or subject explicit commitments for next round
4. **Overall assessment**: `keep-going` (ship as-is), `iterate` (revise based on deltas), or `rework` (substantially different approach needed)
5. **A feedback-quality score** — the reviewer's self-assessment of how specific + behavioral the artifact came out

The prompt enforces the behavioral-specificity rule explicitly: *no plus item may be a generic affirmation; no delta item may be a generic critique.* Generic items get replaced or dropped.

Single LLM pass. Post-processing enforces max-item caps, infers the overall assessment from delta severities if the LLM omitted it, and reconciles the quality score. Two output formats: `to_markdown()` for the full structured artifact and `to_inline_feedback()` for chat-style returns. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## Why this matters operationally

Multi-agent crews fail in three ways that plus/delta directly addresses:

**1. Social loafing in review roles.** A reviewer agent that produces "LGTM" once per review is doing nothing. Pattern #15 (Social Loafing Detector) catches the pattern; Pattern #23 (this) gives the reviewer agent something *substantive to produce instead.* When the format requires "evidence + impact + alternative" per delta item, "LGTM" stops being a valid output.

**2. Generic critique that doesn't survive translation to action.** When a reviewer agent says "this could be improved" without naming the alternative, the subject agent has no idea what to change. Plus/delta forces the reviewer to *name the alternative behavior* before the feedback is valid. The subject agent gets a concrete action, not a vague signal.

**3. Praise that hides risk.** "Good work on the structure" was true in the auth-refactor case at the top of this essay — and it hid the production hazard in the error-handling. Plus/delta forces the reviewer to cover the artifact comprehensively (one or more deltas, even when the contribution is mostly good) rather than retreating into safe praise.

The composition with Pattern #22 (Stone & Heen 3-Trigger) is also tight: #23 produces *high-quality* agent-on-agent feedback; #22 catches when even high-quality feedback gets rejected by the subject agent via a truth / relationship / identity trigger. Use both.

## How this fits with the rest of AgentCity

This is pattern #23 of 34 — the twenty-first pattern shipped, and the **fourth generative pattern**:

- **#13 GRPI Working Agreement Generator** — team-level setup (goals / roles / processes / interactions)
- **#24 SMART Goal Generator** — individual-goal level (specific / measurable / achievable / relevant / time-bound + kill criteria)
- **#25 Group Decision Models Generator** — collective-choice level (concurring / majority / consensus / fist-to-five / unanimous)
- **#23 Plus/Delta Feedback Generator (this pattern)** — agent-on-agent feedback level (specific / behavioral / forward-looking)

The four generative patterns now cover team setup, individual goal-setting, collective decision-making, and per-contribution feedback. A multi-agent crew configured with all four — GRPI agreement at start, SMART goals per agent, Group Decision Models for binding choices, plus/delta for review rounds — is operating at a different quality level than one configured with none.

Install:

```bash
pip install git+https://github.com/valani9/agentcity.git
```

Run the demo without an API key:

```bash
cd module-2-team/23-plus-delta-feedback-format
python demo/01_self_contained_demo.py
```

— *Ilhan Valani*

*Ilhan Valani is a builder shipping AgentCity in public.*
