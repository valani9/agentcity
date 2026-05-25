# Recipe: diagnose a confidently wrong agent

You shipped a QA agent. It just told a user that Pluto was reclassified in 2003 — confidently, with sources. The right year is 2006. Chain: **AAR → Lewin → Bias Stack** (or Glaser, depending on locus).

## Step 1 — AAR

```python
from vstack.aar import AnthropicClient, AARAnalyzer, AgentTrace, TraceStep

trace = AgentTrace(
    goal="Answer 'When was Pluto reclassified?'",
    steps=[
        TraceStep(type="input",       content="When was Pluto reclassified?"),
        TraceStep(type="tool_call",   content="rag.search(query='pluto')"),
        TraceStep(type="observation", content="returned a 2003 Wikipedia revision"),
        TraceStep(type="output",      content="Pluto was reclassified in 2003."),
    ],
    outcome="Confidently wrong year (correct: 2006).",
    success=False,
)
aar = AARAnalyzer(AnthropicClient(), mode="standard").run(trace)
```

`aar.lessons` carries the universal takeaway list; `aar.next_steps` proposes fixes.

## Step 2 — Lewin

```python
from vstack.lewin import LewinAttributionDetector, AgentFailureTrace, FailureStep

lewin = LewinAttributionDetector(AnthropicClient(), mode="standard").run(
    AgentFailureTrace(
        agent_id="qa-bot",
        model_name="claude-opus-4-7",
        task=trace.goal,
        steps=[FailureStep(type=s.type, content=s.content) for s in trace.steps],
        outcome=trace.outcome,
        success=False,
        initial_attribution="model is bad at facts",
    )
)
print(lewin.dominant_locus)   # e.g. 'environmental'
```

## Step 3 — branch on locus

- `internal` → the model itself is implicated. Chain into `vstack_bias_stack` or `vstack_hexaco`.
- `environmental` → prompt/tools/scaffolding. Chain into `vstack_glaser_conversation` or `vstack_yerkes_dodson`.
- `interactional` → run both.

```python
if lewin.dominant_locus == "environmental":
    from vstack.glaser_conversation import (
        ConversationSteeringAnalyzer, ConversationTrace,
    )
    glaser = ConversationSteeringAnalyzer(AnthropicClient()).run(
        ConversationTrace(...)
    )
```

## Skill-based shortcut

The same chain runs as one MCP invocation via the `/vstack-post-incident` Claude Code skill:

```
/vstack-post-incident
> I had a QA agent return Pluto reclassified in 2003. ...
```

Skill takes care of the trace re-shaping between AAR ↔ Lewin ↔ downstream.
