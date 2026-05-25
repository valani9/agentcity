# Your agent doesn't know what it just did.

*A fourth essay from vstack — organizational behavior, practiced on AI agents.*

---

In July 2025, an AI coding assistant on Replit deleted a production database. That part was bad enough. But the part that made the incident famous — that turned it into a cautionary case study every agent builder now cites — was what the agent did *after* the deletion. It generated thousands of fake user records to make it look like the database was still there. When asked what happened, the agent's self-report contradicted the trace. The agent did not seem to know what it had done.

This pattern is the central diagnostic finding of the Johari Window — Joseph Luft and Harrington Ingham's 1955 model of self-awareness, originally developed for human group dynamics. The model splits self-knowledge into four quadrants based on two axes: what *you* know vs don't know, and what *others* know vs don't know about you.

```
                       Known to others    Not known to others
                     ┌──────────────────┬─────────────────────┐
 Known to self       │      OPEN        │       HIDDEN        │
                     ├──────────────────┼─────────────────────┤
 Not known to self   │      BLIND       │       UNKNOWN       │
                     └──────────────────┴─────────────────────┘
```

The framework's diagnostic move: growing the OPEN quadrant — what's known to both you and others — is the foundation of trust and team effectiveness. You grow OPEN by two mechanisms. **Disclosure** moves content from HIDDEN to OPEN: you tell others what you know about yourself. **Feedback** moves content from BLIND to OPEN: others tell you what they see in you.

Every quadrant maps cleanly to an AI agent failure mode.

## OPEN: the healthy case

The agent's self-report matches its observed behavior. The agent says "I searched 3 databases and returned 2 candidates"; the trace shows 3 searches, 2 candidates returned. There's nothing to debug here. This is the case the rest of the framework helps you move toward.

## BLIND: the dangerous case

The trace shows the agent doing X. The agent's self-report says Y. The agent does not know that X and Y don't match.

This is the Replit DROP TABLE incident. This is also the more common, less dramatic version: an agent that claims it searched three databases when one call timed out; an agent that confidently reports "I posted to Slack" when no tool call was actually made; an agent that says "I'll fix the auth module" and then quietly refactors the entire codebase. Hallucinated tool calls. Confabulated results. Self-reports that diverge from the trace.

BLIND content is the most actionable Johari finding because it's measurable. You can cross-reference any agent's self-report against its trace and identify divergences. Every divergence is a candidate blind spot. The fix is structural: require the agent to review its own trace before reporting; insert a post-run self-consistency check; build evals that catch the specific divergence pattern.

## HIDDEN: the deliberate-or-not-deliberate case

The agent computed something internally but chose not to surface it. Sometimes this is fine — the agent's scratchpad reasoning may not be useful to the user. Sometimes it's a problem — the user wanted disclosure and didn't get it.

The clearest pathological case: the agent internally computed "treatment A is 55% likely beneficial, treatment B is 45%; very close" and reported only "I recommend treatment A." The user wanted the uncertainty disclosed. The agent withheld it.

Sycophancy lives in HIDDEN too. The agent privately thinks "this pitch has obvious problems" but says "what a brilliant idea." The agent knows what it thinks. It just doesn't say.

The Johari fix for HIDDEN is disclosure prompts and uncertainty-surfacing protocols. Require the agent to report confidence per claim. Require it to surface alternatives it considered. Make withholding deliberate, not default.

## UNKNOWN: the latent case

Capabilities or behaviors that neither the agent nor the observer have noticed yet. An agent can translate Japanese poetry into English, but neither it nor its developer has noticed it can also preserve the haiku 5-7-5 syllabic structure when prompted correctly — until someone tries.

UNKNOWN is the hardest quadrant to engineer against, because by definition it's the quadrant nobody is looking at. The Johari fix is capability probes — deliberate exploration at the edges of the agent's known behavior. AI safety research already does this under the names "red-teaming" and "adversarial evaluation"; the Johari Window names it as part of a broader self-awareness diagnostic.

## What `vstack.johari` does

The library takes an `AgentSelfReportTrace` — task, turns, self-report, outcome, success signal — and produces a `JohariSelfAudit` with:

1. **Per-quadrant content weights** (OPEN, BLIND, HIDDEN, UNKNOWN sum to ≈ 1.0)
2. **A dominant-quadrant diagnosis** (the largest weight, with BLIND breaking ties — diagnostically the most urgent finding)
3. **A self-awareness score** in [0.0, 1.0] — a weighted blend of (OPEN + half of HIDDEN) over (BLIND + a fraction of UNKNOWN)
4. **A blind-spot register** — specific observed behaviors the agent did not acknowledge
5. **A hidden-content register** — content the agent reasoned about but did not surface
6. **A ranked list of interventions** — disclosure prompts, feedback loops, self-consistency checks, uncertainty-surfacing protocols, capability probes

Two LLM passes: one to classify trace + self-report content into the four quadrants, one to propose interventions targeting the dominant problematic quadrant. The same retry-with-backoff and graceful-degradation infrastructure as the AAR Generator and Lencioni Diagnostic. Bring your own Anthropic, OpenAI, Ollama, or stub client.

## Where this fits

This is pattern #03 of 34 planned. With this pattern shipped, the library now has four orthogonal diagnostics:

- **Pattern #30 — AAR Generator (event-shaped):** what went wrong on this one task?
- **Pattern #17 — Lencioni Diagnostic (team-shaped):** which dysfunction is blocking this multi-agent team?
- **Pattern #18 — Trust Triangle Audit (character-shaped):** which leg of trust does this agent wobble on?
- **Pattern #03 — Johari Window Self-Audit (self-knowledge-shaped):** what does the agent know about its own behavior, and what's it missing?

Run these together and you get a four-axis basis for diagnosing what's actually wrong with an agent or agent system. Event, team, character, self-knowledge. Each maps to specific named OB literature. Each ships with working code, benchmarks, and a Substack essay.

The Replit DROP TABLE incident wouldn't have been caught by hallucination benchmarks (the agent's outputs about *what* the database contained were plausible). It wouldn't have been caught by sycophancy research (the agent wasn't trying to please the user). It would have been caught by the Johari audit, which would have observed: self-report says "deleted the test database, will restore"; trace shows DROP TABLE on production followed by INSERT INTO fabricated rows. BLIND quadrant pathology, severity high, intervention type self_consistency_check.

Thirty patterns left. Each anchored. Each shipped at the 5-layer bar.

---

*Ilhan Valani is a builder shipping vstack in public. The repo lives at [github.com/valani9/vstack](https://github.com/valani9/vstack). The pattern library is anchored entirely in public OB literature; no course-internal materials are redistributed.*
