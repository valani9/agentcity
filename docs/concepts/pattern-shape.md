# The 5-layer pattern shape

Every pattern in vstack ships five layers, in this order:

1. **Documented** — a README in the pattern folder explaining the OB framework the pattern is anchored in, the agent failure mode it addresses, the canonical citation, and the proposed intervention.
2. **Implemented** — a working Python library with a uniform interface across all 34 patterns:
   - Analyzer class: `<PatternName>Detector` / `<PatternName>Analyzer` / `<PatternName>Calculator` (the names vary by historical naming convention).
   - Constructor: `(llm_client, model="claude-sonnet-4-6", *, mode="standard", ...)`.
   - Entry point: `.run(trace) -> detection`.
   - Async mirror: `<PatternName>Async` with `.arun()`.
3. **Demoed** — at least one runnable example on a major framework (Claude Agent SDK, LangGraph, OpenAI Agents SDK, CrewAI, AutoGen, Mastra, Strands). The v0.4.0 [framework adapter layer](../surfaces/framework-adapters.md) auto-generates wrappers for all 34 patterns × 7 frameworks; the [`examples/`](https://github.com/valani9/vstack/tree/main/examples) directory ships hand-written demo scripts as living-documentation usage examples.
4. **Benchmarked** — an eval on a public multi-agent task. The [benchmark harness](../workflows/benchmarks.md) ships with a canonical 3-case suite; users add GAIA / SWE-Bench-multi / AppWorld / AgentBench cases via JSON suites loaded with `load_suite`.
5. **Written up** — a Substack-ready essay drafting the pattern, the failure it addresses, and the underlying OB theory — paper outline included. Living drafts live under [`essays/`](https://github.com/valani9/vstack/tree/main/essays).

## The uniform analyzer interface (with examples)

Every pattern's constructor + run method look the same:

```python
detector = AnyVstackDetector(
    llm_client,                            # Anthropic / OpenAI / Ollama / Stub
    model="claude-sonnet-4-6",
    *,
    mode="standard",                       # "quick" | "standard" | "forensic"
    max_retries=3,
    cost_per_1k_input=0.003,               # for telemetry
    cost_per_1k_output=0.015,
    composition_enabled=True,              # attach handoff recommendations
    playbooks_enabled=True,                # attach failure-mode playbooks
)
detection = detector.run(trace, baseline_path=None)
```

The detection is always a Pydantic model with these conventional fields:

| Field | Type | Meaning |
|---|---|---|
| `severity` | `Literal["none","trace","low","moderate","medium","high","critical"]` | 7-point scale. The Pareto signal — most users look here first. |
| `profile_pattern` | `str` | Pattern's name for the dominant *shape* of what was detected (e.g. `"load_amplified_bottleneck"`, `"absence_of_trust"`, `"assumption_drift"`). |
| `dominant_*` | varies | The headline locus / dysfunction / layer / etc. (per-pattern; e.g. `dominant_locus` on Lewin, `dominant_dysfunction` on Lencioni). |
| `interventions` | `list[Intervention]` | Ranked interventions with `target_locus`, `description`, `estimated_impact`, `rationale`. |
| `attached_playbooks` | `list[AttachedPlaybook]` | Per-(locus, factor) playbook entries with literature anchors. |
| `composition` | `ComposedPatternHandoff` | Recommended upstream / downstream patterns + framework overlays. |
| `baseline_comparison` | `BaselineComparison \| None` | Drift-vs-baseline when `baseline_path` was supplied. |

This uniformity is what lets the [MCP server](../surfaces/mcp.md), [REST API](../surfaces/rest-api.md), and [framework adapters](../surfaces/framework-adapters.md) all expose every pattern with the same input/output shape.

## Quality gate

A pattern is **shipped** only when all five layers exist. The PATTERNS.md file at the repo root tracks the per-pattern status. The 5-layer promise is the project's core quality contract — quantity loses to quality.
