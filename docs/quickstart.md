# Quick start

## 60-second flow: install → first detection

```bash
pip install 'valanistack[anthropic]'
export ANTHROPIC_API_KEY="sk-ant-..."
```

```python
from vstack.aar import AnthropicClient, AARAnalyzer, AgentTrace, TraceStep

trace = AgentTrace(
    goal="Refactor the auth module to use JWTs.",
    steps=[
        TraceStep(type="tool_call",   content="edit_file(path='auth/middleware.py')"),
        TraceStep(type="observation", content="session-middleware test failures"),
        TraceStep(type="output",      content="Created JWT tokens but broke sessions."),
    ],
    outcome="Auth module half-migrated; session middleware broken.",
    success=False,
)

aar = AARAnalyzer(AnthropicClient(), mode="standard").run(trace)
print(aar.to_markdown())
```

That's the foundational diagnostic: an After-Action Review. The output is a structured detection with `lessons[]`, `next_steps[]`, `trace_quality_audit`, plus a list of recommended downstream patterns to chain into.

## From there

**Want the full failure-attribution chain?** AAR → Lewin → downstream is the `vstack-post-incident` skill (or just call the patterns directly):

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
        initial_attribution="model bug",
    )
)
print(lewin.dominant_locus)   # 'internal' / 'environmental' / 'interactional'
```

**Want vstack inside your AI client?** Set up the MCP server:

```bash
pip install 'valanistack[anthropic,mcp]'
vstack-mcp config-snippet claude-desktop   # prints a paste-ready JSON block
```

Paste the block into `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS), restart Claude Desktop, ask: _"Use the AAR pattern on this trace…"_

**Want vstack inside a LangChain agent?**

```bash
pip install 'valanistack[anthropic,langchain]'
```

```python
from vstack.adapters.langchain import as_langchain_tools
tools = as_langchain_tools()  # 34 StructuredTool instances
# hand them to your LangChain agent
```

See [Framework adapters](surfaces/framework-adapters.md) for the full set.

## Next steps

- [The 5-layer pattern shape](concepts/pattern-shape.md) — read this before anything else.
- [Composition runbook](concepts/composition.md) — the canonical chains: F1 confidently-wrong, T1 audit-crew, S1 bottleneck, C1 culture, D1 baselines.
- [The pattern catalogue](patterns/index.md) — all 34 patterns, organized by module.
