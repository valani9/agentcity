# vstack — Claude Code skills

Seven task-shaped skills for Claude Code that compose vstack's 34 organizational-behavior diagnostic patterns into real workflows. Each skill orchestrates multiple patterns; none of them is a thin wrapper over a single analyzer (the MCP server already exposes those directly).

## What ships

| Skill | What it does | Patterns composed |
|---|---|---|
| `/vstack` | Meta entry. Routes a free-form complaint to the right specialized skill. | _(meta only — no analyzers)_ |
| `/vstack-pick-pattern` | Conversation-driven pattern picker. Interviews the user, recommends 1-3 patterns, sketches the call. | _(meta only — surfaces all 34)_ |
| `/vstack-post-incident` | Full After-Action Review pipeline. AAR → Lewin attribution → 1-2 downstream patterns. | `aar`, `lewin`, dynamic downstream |
| `/vstack-audit-crew` | Multi-pattern crew health check (10-20 min). | `lencioni`, `psych_safety`, `trust_triangle`, `process_gain_loss`, `bias_stack` |
| `/vstack-bottleneck` | Load + structure diagnosis when a crew slows down under traffic. | `span_of_control`, `org_structure`, `social_loafing`, `superflocks` |
| `/vstack-culture-check` | Surface vs. assumption-layer culture audit. | `schein_culture`, `robbins_culture`, optional `mcgregor` |
| `/vstack-baseline` | Set + verify monitoring baselines per pattern (drift-detection setup). | All 34 (via the calibration API in each pattern) |

## Install (v0.3.0 — manual copy)

```bash
# After pip install valanistack, copy the skill set into your Claude Code skills directory.
git clone https://github.com/valani9/vstack.git /tmp/vstack
mkdir -p ~/.claude/skills/vstack
cp -r /tmp/vstack/_skills/* ~/.claude/skills/vstack/

# Or point vstack-config at a custom location:
vstack-config set skills_install_path ~/.claude/skills/vstack
```

In a future release `vstack-config install-skills` will do the copy in one command.

## Why task-shaped, not pattern-direct

Each pattern's MCP tool (`vstack_lewin`, `vstack_schein_culture`, ...) is already directly callable via the MCP server. Building 34 pattern-direct slash commands on top would duplicate that surface and force the user to know which pattern they need.

The skill shape is different: each `/vstack-*` skill encodes the **task** ("we had an incident", "the crew is slowing down", "the culture feels off") and the skill composes the right pattern bundle, runs them in the right order, and synthesizes a single executive readout. Users don't need to know the pattern catalogue at all — that's the skill's job.

## Skill conventions

Every SKILL.md follows the same structure:

1. **When to invoke** — short list of trigger phrases / situations
2. **Preflight** — what artifacts the skill needs the user to surface
3. **Workflow** — numbered steps, each calling one or more MCP tools
4. **Synthesis** — how to produce the single executive readout
5. **Failure modes** — what to do when the user can't produce a required artifact
6. **Composition** — which other vstack skills compose with this one

The skills assume `vstack-mcp` is available in the MCP client (Claude Desktop, Cursor, Cline, etc.). They invoke tools via `vstack_<pattern_name>` and read resources via `vstack://patterns/<name>/playbooks`.
