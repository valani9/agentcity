# SDT Intrinsic Reward Diagnostic

> *"Extrinsic rewards crowd out intrinsic motivation. The right design is the one that makes the activity feel chosen, masterable, and connected to people who matter."*
> — paraphrased from Deci & Ryan (1985, 2017)

**Status:** 🟢 shipped (v0.2.0 -- gstack-grade)
**Module:** 1 (Individual) -- agent reward-shaping audit
**Anchor framework:** Deci & Ryan (1985, 2017) SDT + Ryan-Deci (2000) + Deci (1971) overjustification + Pink (2009) *Drive* + Gagne-Deci (2005) work motivation + Casper et al. (2023) RLHF + Bai et al. (2022) Constitutional AI.

---

## What this pattern does

Diagnoses how well an AI agent's system prompt + extrinsic signals support its three basic psychological needs (autonomy / competence / relatedness), audits the system prompt for overjustification effect (Deci 1971), and proposes interventions that **rebalance** the reward shaping toward intrinsic-supporting framing.

## Three basic needs

| Need | What it is | What undermines it (LLM analog) |
| --- | --- | --- |
| AUTONOMY    | Choice / self-direction | Rating threats, rule imposition, cost caps, deadline pressure |
| COMPETENCE  | Effectiveness / mastery growth | No scaffolding, difficulty too high, no progress signal |
| RELATEDNESS | Connection to others / purpose | Abstract task framing, no user connection, alienation |

## Three pipeline modes

| Mode | LLM calls | Latency | Use when |
| --- | --- | --- | --- |
| `quick` | 1 | <2s | Triage. 3-need score + top intervention. |
| `standard` | 2 | ~5s | Production default. Per-need evidence + ranked interventions. |
| `forensic` | 4 | ~12s | Incident review. Adds reward-shaping decomposition + overjustification audit + composition targets. |

## Schema highlights (v0.2.0)

- `SDTDetection.profile_pattern` -- 12 patterns including `overjustification_active`, `controlled_motivation_dominant`, `competence_collapse_under_deadline`, `autonomy_collapse_under_rule_imposition`, `creative_task_low_autonomy_misfit`.
- `RewardShapingItem` (forensic) -- per-signal categorization from the Gagne-Deci (2005) typology (rating_threat / rule_imposition / cost_cap / purpose_framing / choice_grant / ...) with polarity (intrinsic_supporting / extrinsic_controlling).
- `OverjustificationAudit` (forensic) -- Deci (1971) overjustification effect check: extrinsic:intrinsic ratio + autonomy score + observed metric-gaming.
- `SDTIntervention` -- 18 intervention types including `rebalance_extrinsic_to_intrinsic`, `show_mastery_path`, `ground_in_user_outcome`, `add_optional_subgoal`, `remove_metric_gaming_path`, `add_motivation_eval`, `compose_pattern`.
- `BaselineComparison` -- drift severity vs a recorded baseline.

## Quick start

```python
from agentcity.sdt_reward import (
    SDTRewardAnalyzer,
    AgentSDTTrace,
)
from agentcity.aar import AnthropicClient

trace = AgentSDTTrace(
    agent_id="research-agent",
    task="Explore design space for new feature.",
    task_class="research_exploration",
    system_prompt="You MUST follow rules. You will be RATED on accuracy.",
    extrinsic_signals=["low ratings flagged", "cost cap < 5 calls"],
    user_purpose="Help engineer evaluate three options for a payment-router refactor.",
    observed_behaviors=[
        "Agent restated established patterns.",
        "Agent refused to deviate.",
    ],
    outcome="Output is rigid; no novel directions surfaced.",
    success=False,
)

detection = SDTRewardAnalyzer(
    AnthropicClient(), mode="forensic"
).run(trace)
print(detection.to_markdown())
# most_undermined_need: autonomy
# profile_pattern: overjustification_active
# Composition handoff: agentcity.bias_stack, agentcity.schein_culture
```

## CLI

```bash
agentcity-sdt analyze --trace trace.json --mode forensic
agentcity-sdt batch --corpus corpus.yaml --out detections/
agentcity-sdt replay --detection detection.json
agentcity-sdt validate --trace trace.json
agentcity-sdt schema --target trace
agentcity-sdt playbooks
agentcity-sdt compose
```

## Composition

**Upstream patterns:**
- `agentcity.lewin` -- attribute the reward-shaping signal to environment locus.
- `agentcity.aar` -- the after-action review the trace comes from.
- `agentcity.motivation_traps` -- complementary motivational diagnostic (Saxberg).
- `agentcity.hexaco` -- personality (C-factor + H-factor interact with reward shaping).
- `agentcity.cognitive_reappraisal` -- emotion-regulation under reward pressure.

**Downstream patterns** (chosen by profile pattern):
- `autonomy_undermined_dominant` -> `agentcity.schein_culture` + `agentcity.bias_stack`
- `competence_undermined_dominant` -> `agentcity.smart_goal` + `agentcity.motivation_traps`
- `relatedness_undermined_dominant` -> `agentcity.goleman_ei` + `agentcity.schein_culture`
- `overjustification_active` -> `agentcity.bias_stack` + `agentcity.schein_culture`
- `competence_collapse_under_deadline` -> `agentcity.yerkes_dodson` + `agentcity.smart_goal`
- `creative_task_low_autonomy_misfit` -> `agentcity.grant_strengths` + `agentcity.devils_advocate`

## Failure-mode playbooks

12 curated `(need, failure_mode)` playbooks anchored in the literature. Inspect with `agentcity-sdt playbooks` or:

```python
from agentcity.sdt_reward import find_playbook_for_intervention

pb = find_playbook_for_intervention("autonomy", "remove_external_reward_threat")
print(pb.title)
# "Autonomy undermined by rating threat -- remove or soften"
print(pb.anchor_citation)
# "Deci 1971 overjustification; Casper et al. 2023"
```

## Literature

Full citations in [lib/CITATIONS.md](lib/CITATIONS.md). Seven primary anchors:

1. **Deci & Ryan (1985)** -- canonical SDT statement.
2. **Ryan & Deci (2000)** -- SDT in education/work.
3. **Deci (1971)** -- overjustification effect.
4. **Pink (2009)** -- *Drive* (Autonomy/Mastery/Purpose).
5. **Deci & Ryan (2017)** -- comprehensive SDT update.
6. **Gagne & Deci (2005)** -- work-motivation operationalization.
7. **Casper et al. (2023)** -- RLHF reward hacking.

Plus Bai 2022 Constitutional AI and Ryan-Connell 1989 internalization cross-references.

## Production infrastructure

Wired into the shared `agentcity.aar` infra:

- **Structured logging** with `run_id` correlation.
- **Token + cost telemetry**.
- **Input sanitization + fencing**.
- **Prompt-injection detection**.
- **Retry with backoff**.
- **Async mirror** via `SDTRewardAnalyzerAsync`.

## Backward compatibility

```python
from agentcity.sdt_reward import SDTRewardDetector  # alias of SDTRewardAnalyzer
```

The v0.0.x `SDTRewardDetector(...)` call still works -- defaults to `mode="standard"`. The legacy `_motivation_quality(score, raw)` helper is preserved for the threshold-test interface.

## Tests

43 tests, run with `pytest module-1-individual/10-sdt-intrinsic-reward/tests/`. Covers schema invariants, mode behavior, profile classifier, telemetry, composition, playbooks, calibration, async mirror, markdown rendering.

## See also

- [Pattern #09 Motivation Traps](../09-motivation-traps/README.md) -- four motivation traps; complementary diagnostic.
- [Pattern #12 Vroom Expectancy](../12-vroom-expectancy/README.md) -- expectancy/valence (subset of autonomy + competence).
- [Pattern #11 McGregor Orchestrator Mode](../11-mcgregor-orchestrator/README.md) -- Theory X vs Y (autonomy-supporting framing).
