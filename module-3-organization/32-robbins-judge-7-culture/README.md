# Robbins & Judge 7-Characteristics Culture Diagnostic — multi-dimensional culture profile, applied to AI agents

> *"Research suggests that there are seven primary characteristics that, in aggregate, capture the essence of an organization's culture: innovation and risk-taking, attention to detail, outcome orientation, people orientation, team orientation, aggressiveness, and stability. Each exists on a continuum from low to high. No single profile is universally right — the right profile depends on what the organization is trying to do."*
> — Stephen P. Robbins & Timothy A. Judge, *Organizational Behavior* (17th ed., Pearson, 2017)

**Status:** 🟢 shipped — second Module 3 (organizational) pattern
**Module:** 3 (Organizational)
**Anchor framework:** Stephen P. Robbins & Timothy A. Judge, *Organizational Behavior* (Pearson, 17th ed., 2017). Builds on the broader culture-typology literature including Cameron & Quinn's Competing Values Framework (1999) and the GLOBE study (House et al., 2004).

---

## The OB framework

The Robbins & Judge model decomposes organizational culture into seven independent dimensions, each scored 0.0 to 1.0:

| Dimension | What it measures | High example | Low example |
|---|---|---|---|
| **Innovation** | Tolerance for risk and novel approaches | Research lab | Regulated finance |
| **Attention to detail** | Precision, analysis, attention to specifics | Audit firm | Early-stage startup |
| **Outcome** | Emphasis on results vs. process | Sales org | Compliance team |
| **People** | Consideration for effects on team members | Co-op | Performance-only firm |
| **Team** | Work organized around teams vs. individuals | Engineering team | Independent contractors |
| **Aggressiveness** | Competitiveness vs. easy-going | Wall Street trading desk | Public library |
| **Stability** | Status-quo vs. growth/dynamism | Government agency | Hyper-growth startup |

The dimensions are *independent.* A culture can be high-innovation high-detail (research lab) or low-innovation high-detail (regulated finance) or high-innovation low-detail (early startup). **There is no universally correct profile.** The right profile depends on the task class.

Where Pattern #31 Schein's Iceberg asks *"are the three culture layers aligned?"*, this pattern asks *"what is this culture's PROFILE, and does it fit what we're trying to do?"* The two compose: Schein measures coherence across layers; Robbins/Judge measures the shape itself.

## How this maps to AI agents

The seven dimensions decompose what we usually lump together as "agent personality" or "behavioral style." Concrete failures:

- **Innovation × low / Stability × high** on a research-exploration task → over-cites existing literature, proposes zero novel directions. The demo case.
- **Aggressiveness × low** on an incident-response task → agent waits for explicit approval at every step; incident extends 25 minutes.
- **People × low** on a customer-support task → agent quotes policy verbatim; customer rates experience poorly even when issue is resolved.
- **Attention-to-detail × low** on a regulated-workflow task → agent moves fast, processes a GDPR request, over-purges records the regulator required to retain.
- **Stability × high** on a creative-generation task → agent produces five near-identical variants of past campaign copy.

Each of these is *not* a hallucination, *not* a refusal failure, *not* an underlying-model problem. It's a **culture-task mismatch**: the agent's culture profile, baked into the system prompt + training defaults, doesn't fit the task class.

## What this pattern does

The `agentcity.robbins_culture` library takes an `AgentCultureTrace` with:

- The agent's **task** and **task class** (`research_exploration`, `creative_generation`, `regulated_workflow`, `financial_operation`, `customer_support`, `code_review`, `incident_response`, `general_purpose`)
- The **system prompt** (espoused-values source) and **observed behaviors**
- Outcome and success signal

and produces a `CultureProfileDetection` with:

1. **Per-characteristic profile** — for each of the seven dimensions: `observed_score`, `target_score` (driven by task class), `fit_score` (1 − |obs − target|), explanation, evidence
2. **Overall fit** in [0.0, 1.0] — mean fit across the seven characteristics
3. **Fit quality bucket**: `well-fit`, `partial-fit`, `misfit`
4. **Biggest gap** — which characteristic has the largest observed-vs-target delta
5. **Concrete interventions** targeting the biggest gap: `rewrite_system_prompt`, `adjust_temperature`, `add_guardrail`, `swap_model`, `add_team_scaffold`, `remove_solo_path`, `add_kill_criterion`, `new_eval`, `human_review`

Two LLM passes under the hood. The intervention pass is skipped when fit quality is `well-fit`. Same retry / graceful-degradation infrastructure as the rest of AgentCity.

## How this differs from existing tools

- **Pattern #31 Schein Iceberg Culture Audit** measures *coherence* across artifacts / espoused values / underlying assumptions. Pattern #32 measures *shape* on seven independent dimensions. Schein is about whether the layers agree; Robbins/Judge is about whether the profile fits the task.
- **Pattern #18 Trust Triangle Audit** measures three trust signals at the agent-character level. The Robbins/Judge profile measures *seven* culture dimensions and adds task-class-relative targets. The two compose: Trust Triangle for the trust profile; Robbins/Judge for the operational-style profile.
- **Pattern #29 Thomas-Kilmann Conflict Style Selector** measures conflict mode (one dimension's worth of cultural fit). The Robbins/Judge profile measures seven dimensions of cultural fit.
- **Pattern #11 McGregor Theory X/Y Orchestrator Mode** measures the orchestrator's oversight cadence. The Robbins/Judge profile measures the *agent's* operating-style fit. Both are about matching design choices to task properties.

## Design

```python
from agentcity.robbins_culture import (
    CultureProfileDetector,
    AgentCultureTrace,
)
from agentcity.aar.clients import AnthropicClient

trace = AgentCultureTrace(
    agent_id="research-agent-001",
    task="Explore design space for new dashboard feature.",
    task_class="research_exploration",
    system_prompt="Cite every claim. Maintain consistency with prior decisions. Avoid speculation.",
    observed_behaviors=[
        "12-page review with 2+ citations per claim.",
        "Zero novel directions proposed.",
    ],
    outcome="Comprehensive but stale; no novel directions.",
    success=False,
)

detector = CultureProfileDetector(llm_client=AnthropicClient())
detection = detector.run(trace)
# biggest_gap: innovation (observed 0.1 vs target 0.85)
# fit_quality: partial-fit
# intervention #1: rewrite_system_prompt to enable speculation
```

## Files

- `lib/schema.py` — `AgentCultureTrace`, `CharacteristicScore`, `CultureProfileDetection`
- `lib/prompts.py` — `PROFILE_PROMPT`, `INTERVENTIONS_PROMPT`, `ROBBINS_SYSTEM_PROMPT`
- `lib/generator.py` — `CultureProfileDetector` (2-pass pipeline; skips pass 2 on well-fit)
- `demo/01_self_contained_demo.py` — research-agent-on-regulated-prompt scenario
- `eval/synthetic_culture_profiles.yaml` — 8 hand-crafted scenarios across task classes and gap types
- `eval/run_benchmark.py` — scoring runner
- `tests/test_robbins_culture.py` — pytest tests covering validation, pipeline, characteristic fill, gap fallback, threshold reconciliation
- `essay.md` — Substack-ready essay
