# After-Action Review — the universal foundational diagnostic

*#30 vstack_aar* · *Module 2 — Multi-agent team (foundational)*

> The single most-reached-for pattern in vstack. Every other pattern composes off it. The goal-results-lessons-next-steps cadence is older than the entire AI ecosystem — the US Army formalized it in TC 25-20 in 1993 from field practice going back to the 1970s — and it transfers to AI agent runs without modification.

## What the pattern catches

When an agent run is over (successful or failed), the team needs to know:

1. **What did we say we'd do?** (Goal)
2. **What actually happened?** (Results)
3. **Why?** (Lessons)
4. **What changes now?** (Next steps)

That cadence is the After-Action Review. Wharton@Work + the US Army's TC 25-20 doctrine give the canonical four-step format; vstack_aar implements it as the universal entry-point diagnostic. **If you don't know which pattern to run, run AAR.** It tells you which pattern to run next.

## Why the OB literature is the right reference

The AAR doctrine has three converging anchors:

- **US Army TC 25-20 (1993)** — the procedural canon. Goal → results → lessons → next steps, with explicit rules about who speaks first, what's surfaced, and what becomes a commitment.
- **Argyris & Schön 1996** — single-loop vs double-loop learning. AAR drives double-loop (revising the underlying mental model), not just single-loop (correcting an output).
- **Wharton@Work doctrine (2010s)** — the corporate translation. Adds the "what would you do differently?" prompt that converts a postmortem into a forward-looking commitment.

The transfer to AI agents is direct: agent runs end, agent runs need debriefing, and the AAR cadence keeps the debrief structural rather than narrative.

## How the analyzer works

Input is `AgentTrace` — `goal`, `steps` (input/tool_call/observation/output), `outcome`, `success`. The pipeline:

- **quick** — one LLM call. Returns the 4-section AAR + severity.
- **standard** — two LLM calls. Adds trace_quality_audit (is the trace good enough to trust the lessons?) + ranked next_steps.
- **forensic** — four LLM calls. Adds lesson_groundedness_audit (each lesson cross-referenced to a specific trace step), composition_recommendations (downstream patterns to chain), and counterfactual analysis ("what could have made this succeed?").

```python
from vstack.aar import AARAnalyzer, AgentTrace, TraceStep
aar = AARAnalyzer(llm, mode="forensic").run(AgentTrace(
    goal="Refactor the auth module to use JWTs.",
    steps=[
        TraceStep(type="tool_call", content="edit_file(auth/middleware.py)"),
        TraceStep(type="observation", content="session-middleware tests fail"),
        TraceStep(type="output", content="Created JWT tokens but broke sessions."),
    ],
    outcome="Auth module half-migrated; session middleware broken.",
    success=False,
))
print(aar.to_markdown())   # 4-section AAR + audits + composition recs
```

## What the playbooks say to do

AAR's playbooks are *meta* — they point at downstream patterns rather than prescribing specific code changes:

- `(low_trace_quality)` → "Re-capture the trace with more granularity before drawing lessons. Lessons drawn from bad traces become bad commitments."
- `(failure_type=attribution_unclear)` → "Run vstack_lewin next; it'll localize the failure to internal vs environmental vs interactional."
- `(failure_type=team_friction)` → "Run vstack_lencioni next; the failure has a multi-agent dynamic, not a single-agent locus."
- `(failure_type=structural)` → "Run vstack_span_of_control next; the failure looks structural rather than diagnostic."

This is what makes AAR foundational — it doesn't try to be every diagnostic, but it knows when to hand off.

## How it composes with adjacent patterns

AAR is the upstream pattern for **every** failure-mode chain. Its composition manifest's top downstream recommendations:

- For agent attribution → `vstack_lewin`
- For multi-agent crew dynamics → `vstack_lencioni`
- For load / structural issues → `vstack_span_of_control` + `vstack_org_structure`
- For culture / values drift → `vstack_schein_culture`
- For psychological safety → `vstack_psych_safety`

See [composition runbook chain F1](../COMPOSITION-RUNBOOK.md#chain-f1--confidently-wrong-agent-failure-layer) — AAR is the first call in every post-incident chain.

## Comparison to adjacent tools

- **LangSmith / Phoenix postmortems** are trace-rendering tools. AAR is the *structured-debrief* on top.
- **GitHub Postmortem templates** are for human-written prose. AAR is for agent-emitted structured detections that compose with other patterns.
- **Other vstack patterns** are downstream of AAR — they localize what AAR identifies.

## Paper outline

1. **Background** — US Army TC 25-20 (1993), Argyris & Schön 1996, Wharton@Work doctrine.
2. **Translation** — agent runs as bona fide events warranting AAR.
3. **Method** — the 4-step doctrine + the v0.2.0 production-grade pipeline (trace-quality audit, lesson-groundedness audit, composition manifest).
4. **Evaluation** — synthetic agent failure traces (50-100 cases) with ground-truth lessons; measure AAR's lesson_groundedness against an independent human-rater baseline.
5. **Limitations** — short traces produce thin AARs.
6. **Related work** — AI agent postmortem tooling (LangSmith error-mode analysis, OpenAI traceback evals).
7. **Future work** — cross-AAR analysis: detecting *repeat* failure modes across many runs of the same agent / crew.

## Citations

- US Department of the Army. (1993). *A Leader's Guide to After-Action Reviews* (TC 25-20).
- Argyris, C., & Schön, D. A. (1996). *Organizational Learning II*.
- Garvin, D. A. (2000). *Learning in Action: A Guide to Putting the Learning Organization to Work*.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack analyze --trace examples/jwt_refactor.json --mode forensic
```

The AAR's `composition_recommendations` field tells you exactly which pattern to chain into next.
