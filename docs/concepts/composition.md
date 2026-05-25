# Composition runbook

This page is the **human-readable** version of the composition chains. The machine-readable per-pattern composition manifests are at `vstack://patterns/<name>/composition` via the MCP server, or `GET /v1/patterns/<name>/composition` via the REST API.

For the full curated runbook covering all five canonical chains (failure / team / structural / culture / calibration), see [`COMPOSITION-RUNBOOK.md`](https://github.com/valani9/vstack/blob/main/COMPOSITION-RUNBOOK.md) at the repo root.

## The five canonical chains

| Chain | Trigger | Patterns | Skill |
|---|---|---|---|
| **F1 — Confidently wrong** | Agent returned wrong answer with high confidence | AAR → Lewin → branch on locus (Bias Stack / Yerkes-Dodson / Glaser) | `/vstack-post-incident` |
| **T1 — Crew is "off"** | Multi-agent crew produces output that doesn't feel right | Lencioni + Edmondson + Trust Triangle + Process Gain/Loss + Bias Stack (parallel) | `/vstack-audit-crew` |
| **S1 — Bottleneck under load** | Crew slows down or backs up under traffic | Span-of-Control (deterministic) → Org-Structure (qualitative) → Social Loafing / Superflocks (behavioral) | `/vstack-bottleneck` |
| **C1 — Culture drift** | Crew's behavior doesn't match the team's intent | Schein iceberg → Robbins-Judge 7-characteristic → (optional) McGregor | `/vstack-culture-check` |
| **D1 — Calibration** | Set + verify monitoring baselines for drift detection | Any 1-N patterns in forensic mode, baseline JSON written to `~/.vstack/baselines/` | `/vstack-baseline` |

## Cross-chain transitions

The most common multi-chain transitions (from the runbook):

| If this chain... | ...surfaced this | ...the natural next chain is |
|---|---|---|
| F1 (failure) | Lewin says `interactional` | T1 (full crew audit) |
| F1 | Lewin says `environmental` + crew is multi-agent | S1 (bottleneck) |
| T1 (team) | Lencioni "absence of trust" | C1 (culture) |
| T1 | Lencioni "lack of commitment" | S1 (bottleneck) |
| S1 (structural) | Math fine + structure wrong | C1 (culture root often masquerades as structure) |
| C1 (culture) | Schein layer-drift severity high | F1 against a specific failed run (concretize the drift) |
| Any | Drift suspected over time | D1 (baselines) — then re-run quarterly |

## The output shape for the executive readout

Every chain ends with one structured readout. The shared template:

```
## <Chain name> — <one-line scope>

**Headline:** <one sentence — deepest finding with severity>

**Layered view:**
- <pattern 1>: <severity> + <one-line top finding>
- <pattern 2>: <severity> + <one-line top finding>
- ...

**The chain:** <one sentence connecting the patterns at different resolutions>

**Three highest-leverage interventions:** (deduped, ranked by estimated_impact)
1. <intervention> (from <pattern>)
2. ...
3. ...

**Where to look next:** <recommend the next /vstack-* skill>
```

Cap at ~500 words. Detection JSONs go in a collapsible appendix.

See [COMPOSITION-RUNBOOK.md](https://github.com/valani9/vstack/blob/main/COMPOSITION-RUNBOOK.md) for code + per-chain detailed walkthroughs.
