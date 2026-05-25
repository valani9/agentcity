# Modes — quick / standard / forensic

Every analyzer in vstack ships three pipeline modes. Same input model, same output detection shape; the modes trade LLM-call budget for depth of analysis.

| Mode | LLM calls | When to use |
|---|---|---|
| `quick` | 1 | CI / live ops / health-check sweeps. Returns severity + top intervention only. |
| `standard` | 2 | The default. Full scoring + ranked interventions. What most users want most of the time. |
| `forensic` | 4 | High-stakes incidents. Adds counterfactual reasoning, bias-mechanism diagnosis (Lewin), cascade audit (Lencioni), structural-anomaly + load-amplification audits (Span-of-Control), etc. |

## Picking the right mode

- Routine quarterly checks → **quick** (cheap; surfaces severity drift)
- Default day-to-day usage → **standard**
- A specific incident the team will brief on → **forensic**
- Recording a calibration baseline → **forensic** (highest-fidelity reference point)

## Cost / latency tradeoff

The [comparative-eval harness](../workflows/benchmarks.md) ships a CLI for measuring this empirically against your specific traces:

```bash
vstack-bench compare canonical --mode quick --mode standard --mode forensic
```

The output is a per-case row with elapsed-ms + severity + dominant-finding per mode, plus an agreement flag showing whether the modes returned the same headline finding.

## Mode overrides at runtime

The constructor's `mode=` argument is the default; each `.run()` call can override:

```python
detector = LewinAttributionDetector(llm, mode="standard")  # default
detection = detector.run(trace, mode="forensic")           # override per call
```

The MCP server, REST API, and framework adapters all pass `mode` through transparently.
