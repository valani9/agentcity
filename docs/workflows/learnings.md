# Learning store

Cross-session memory: "last time you ran Lencioni on this crew, you applied intervention X. Did it improve next time?"

Stored at `~/.vstack/learnings.jsonl` (one record per pattern run). Append-only by default; the latest open record for a `(pattern, agent_id|crew_id)` tuple can be updated with a follow-up outcome.

## CLI

```bash
vstack-learn record lewin --agent-id qa-bot \
    --severity high --intervention change_rag_index \
    --dominant-finding "environmental: stale RAG"

vstack-learn recall --pattern lewin --limit 25
vstack-learn outcome lewin improved --notes "next run got 2006 right"
vstack-learn outcomes --pattern lewin   # aggregated improvement rate per intervention
```

## Schema

Each record carries: timestamp, pattern, mode, agent_id, crew_id, severity, profile_pattern, dominant_finding, interventions_applied, follow_up_outcome (`improved`/`no_change`/`worse`/`unknown`), notes, extra.

The `outcomes` view aggregates by `(pattern, intervention)` so you can answer "which interventions actually worked?" empirically:

```
lewin::change_rag_index    runs=7   improved=5   no_change=1   worse=1   rate=71%
lewin::add_prompt_guard    runs=3   improved=1   no_change=2   worse=0   rate=33%
```
