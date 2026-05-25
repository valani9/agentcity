# Claude Code skills

Seven task-shaped skills under [`_skills/`](https://github.com/valani9/vstack/tree/main/_skills) compose vstack's 34 patterns into real workflows.

| Skill | What it does | Patterns composed |
|---|---|---|
| `/vstack` | Meta entry — routes a free-form complaint to the right skill. | _(meta only)_ |
| `/vstack-pick-pattern` | Interview-based pattern picker. | _(meta only — surfaces all 34)_ |
| `/vstack-post-incident` | AAR → Lewin → 1-2 downstream patterns. | `aar`, `lewin`, dynamic downstream |
| `/vstack-audit-crew` | 5-pattern crew health check. | `lencioni`, `psych_safety`, `trust_triangle`, `process_gain_loss`, `bias_stack` |
| `/vstack-bottleneck` | Load + structure diagnosis. | `span_of_control`, `org_structure`, `social_loafing`, `superflocks` |
| `/vstack-culture-check` | Surface-vs-assumption-layer culture audit. | `schein_culture`, `robbins_culture`, optional `mcgregor` |
| `/vstack-baseline` | Record + verify monitoring baselines. | All 34 |

## Install

```bash
vstack-config install-skills              # copies to ~/.claude/skills/vstack/
vstack-config install-skills --dry-run    # preview first
vstack-config install-skills --force      # overwrite existing
```

Restart your Claude Code client after install to pick up the skills.

## Skill design — why task-shaped, not pattern-direct

Each pattern's MCP tool is already directly callable. Building 34 pattern-direct slash commands on top would duplicate that surface. The skill shape is different: each `/vstack-*` skill encodes the **task** ("we had an incident", "the crew is slowing down", "the culture feels off") and composes the right pattern bundle into one executive readout.

See the [composition runbook](../concepts/composition.md) for the canonical chains each skill orchestrates.
