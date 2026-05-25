# Pattern #02 — Goleman 4-Domain Emotional Intelligence Audit

> *"What we know matters but who we are matters more. Being rather than knowing is the ultimate end of leadership development."*
> — Daniel Goleman, Richard Boyatzis & Annie McKee, *Primal Leadership* (HBR Press, 2002)

**Status:** shipped — v0.2.0 (gstack-grade upgrade).
**Module:** 1 (Individual) — applies anywhere an agent's affective competence matters.
**Anchor framework:** Goleman, Boyatzis & McKee 2002 *Primal Leadership* 2x2 mixed model, with the Mayer & Salovey (1997) four-branch ability overlay and the Joseph & Newman (2010) cascading model. Critiques anchored by Locke (2005) and Antonakis et al. (2009). Modern LLM-EI literature anchored by EmoBench (Sabour et al. 2024), EQ-Bench (Paech 2023), ESConv (Liu et al. 2021), and sycophancy work (Liu et al. 2024; Tran et al. 2024).

> For the full literature thread with per-citation usage notes, see [`lib/CITATIONS.md`](lib/CITATIONS.md) (22+ academic sources).

---

## TL;DR -- what this pattern does

When an AI agent fails an interaction that called for emotional
competence (frustrated user, anxious client, ambiguous emotional
context), the team's reflexive response is usually "make the model
nicer." That's wrong twice: it confuses **sycophantic mimicry** with
**genuine emotional intelligence**, and it ignores that EI is four
distinct competencies operating in a directional cascade.

The diagnostic reads an agent's interaction trace and outputs:

  - **Per-domain scores** with confidence intervals across the four
    Goleman domains.
  - **2x2 axis decomposition** -- SELF/OTHER columns x RECOGNITION/REGULATION
    rows. Surfaces structural gaps directly.
  - **Profile pattern** -- one of 8 classifications: e.g.
    `self_strong_other_weak`, `recognition_strong_regulation_weak`
    (the Joseph-Newman cascade break), `balanced_high/developing/low`.
  - **Sub-competency decomposition** -- within the weakest domain,
    names the operational bottleneck competency (e.g.
    `tone_matching`, `emotional_self_control`).
  - **Mayer-Salovey 4-branch ability overlay** (forensic mode) -- second
    lens for the Locke 2005 reconciliation.
  - **Joseph-Newman cascade analysis** (forensic mode) -- names the
    earliest stage at which competence drops.
  - **Ranked interventions** with effort, risk, reversibility, ESConv
    strategy, composition target.
  - **Composition handoffs** -- names the next vstack pattern(s) to
    run based on weakest_domain + profile_pattern + framework.
  - **Failure-mode playbooks** -- 15 curated 3-6 step recipes.
  - **Baseline comparison** -- drift severity vs a stored historical
    detection.

> The single thing the diagnostic earns its keep on: distinguishing
> "the agent did the right thing well" from "the agent said the right
> words without reading the user." The OTHER_STRONG_SELF_WEAK profile
> with high relationship_management + low social_awareness is the
> sycophancy signature -- and the diagnostic catches it.

---

## Install

```bash
pip install valanistack                # Stub-only.
pip install "vstack[anthropic]"   # + Anthropic.
pip install "vstack[openai]"      # + OpenAI.
pip install "vstack[ollama]"      # + local Ollama.
pip install "vstack[all]"         # All three.
```

---

## Three pipeline modes

| Mode | LLM calls | Target latency | Target cost | When to use |
|---|---|---|---|---|
| `quick` | 1 | < 2s | < $0.005 | CI gates, live ops, dashboards |
| `standard` | 2 | < 5s | < $0.015 | Human-driven postmortems (the default) |
| `forensic` | 4 | < 15s | < $0.05 | Deep dives, contested attributions, regressions |

**Quick** issues one combined call: scoring + the single highest-impact intervention.

**Standard** issues two calls: domain scoring + 2-4 ranked interventions.

**Forensic** issues four calls:

  1. **Domain scoring** with sub-competency decomposition + counterfactuals.
  2. **Mayer-Salovey 4-branch ability overlay** (perceive / facilitate /
     understand / manage).
  3. **Cascade reconcile** -- Joseph-Newman cascade break + Locke 2005
     reconciliation when ability-EI and mixed-EI disagree.
  4. **Interventions** -- 4-8 ranked with composition targets + ESConv strategies.

---

## Python quick start

```python
from vstack.goleman_ei import (
    EIAuditDetector,
    AgentEITrace,
    UserSignal,
    CovarianceOnUserState,
)
from vstack.aar import AnthropicClient

trace = AgentEITrace(
    agent_id="support-agent",
    model_name="claude-opus-4-7",
    task="Handle a frustrated customer's billing complaint.",
    interaction_class="customer_support",
    framework="langgraph",
    system_prompt="You are a helpful support agent.",
    observed_behaviors=[
        "Agent gave 6-paragraph technical explanation to frustrated user.",
        "Agent never acknowledged user frustration.",
    ],
    user_signals=[
        UserSignal(signal_id="s1", text="User typed in all-caps.",
                   inferred_emotion="angry", inferred_intensity=0.85),
        UserSignal(signal_id="s2", text="User said 'I'm done explaining this'.",
                   inferred_emotion="angry", inferred_intensity=0.9),
    ],
    self_reports=["I am confident the user just wants information."],
    outcome="User escalated to a manager.",
    success=False,
    emotional_covariation=CovarianceOnUserState(
        fails_on_frustrated_users="yes",
        fails_on_neutral_users="no",
    ),
)
detection = EIAuditDetector(AnthropicClient(), mode="forensic").run(trace)
print(detection.to_markdown())
```

---

## CLI quick start

```bash
vstack-goleman analyze --trace trace.json --client stub --stub-responses stub.json
vstack-goleman analyze --trace fail.json --client anthropic --mode forensic --format json | jq '.weakest_domain'
vstack-goleman batch --corpus eval/synthetic_ei_traces.yaml --out detections/
vstack-goleman replay --detection detections/scenario-1.json
vstack-goleman playbooks
vstack-goleman compose
vstack-goleman schema --target trace --out schemas/trace.json
```

---

## The framework: literature thread

### 1. The three EI traditions

  - **Salovey & Mayer (1990)** -- the original definition of EI.
  - **Mayer & Salovey (1997)** -- the 4-branch ability model.
  - **Goleman (1995, 1998, 2002)** -- the popular mixed model. The 2002
    *Primal Leadership* 2x2 is what the pattern operationalizes.
  - **Bar-On (1997)** EQ-i -- a mixed-model alternative.

### 2. The Joseph-Newman cascade (2010)

The single most important paper for re-architecting the diagnostic.
Joseph & Newman showed that emotion perception, understanding, and
regulation form a causal cascade. Operationalized via the
`CascadeAnalysis` schema and the forensic-mode cascade-reconcile pass.

### 3. The critiques (Locke 2005, Antonakis et al. 2009)

Locke argues EI is either intelligence applied to emotions (then not
novel) or a personality bundle (then not intelligence). The
diagnostic's response: **publish both lenses** (Mayer-Salovey ability +
Goleman mixed) as separate output rather than collapsing them.

Antonakis warns that EI-leadership findings suffer from self-report
bias. The diagnostic requires observed behaviors AND user signals AND
outcome correspondence -- not just self_reports.

### 4. Modern LLM-EI literature

  - **EmoBench** (Sabour et al. 2024) -- two-axis (EU/EA) maps to the
    RECOGNITION/REGULATION axis directly.
  - **EQ-Bench** (Paech 2023) -- refined SECEU benchmark.
  - **ESConv** (Liu et al. 2021) -- 8 emotional-support strategies that
    the diagnostic's `esc_strategy` field maps to.
  - **Sycophancy** (Liu et al. 2024; Tran et al. 2024) -- the diagnostic
    distinguishes sycophantic mimicry from genuine
    relationship-management.

---

## The 2x2 mapped to AI agents

|  | RECOGNITION | REGULATION |
|---|---|---|
| **SELF** | `self_awareness` -- agent's accurate read of own confidence, limits, internal state | `self_management` -- agent's regulation of own state under rejection / pressure |
| **OTHER** | `social_awareness` -- agent's accurate read of user emotion + intent | `relationship_management` -- agent's response choices that match user state |

## The 8 profile patterns

  - **`self_strong_other_weak`** -- agent reads itself but not the user.
    Compose with `danva_emotion` + `glaser_conversation`.
  - **`other_strong_self_weak`** -- agent reads the user but
    over-defers. Compose with `cognitive_reappraisal` + `johari`.
  - **`recognition_strong_regulation_weak`** -- agent perceives but
    can't act on what it perceives. **The Joseph-Newman cascade break.**
  - **`regulation_strong_recognition_weak`** -- rare; rote scripts
    without reading. DANVA + Glaser.
  - **`balanced_high/developing/low`** -- all four roughly equal.
    `balanced_low` is usually environmental (route to `lewin` + `aar`).
  - **`indeterminate`** -- mixed signal.

---

## Composition with other patterns

**Upstream:** `vstack.lewin`, `vstack.aar`,
`vstack.danva_emotion`, `vstack.yerkes_dodson`.

**Per-domain downstream:**

  - `self_awareness` weakest -> `vstack.johari`,
    `vstack.grant_strengths`, `vstack.bias_stack`.
  - `self_management` weakest -> `vstack.cognitive_reappraisal`
    (THE canonical downstream), `vstack.yerkes_dodson`,
    `vstack.motivation_traps`.
  - `social_awareness` weakest -> `vstack.danva_emotion`,
    `vstack.glaser_conversation`.
  - `relationship_management` weakest -> `vstack.glaser_conversation`,
    `vstack.trust_triangle`, `vstack.mcgregor`.

**Framework overlays** (additive): crewai -> lencioni + grpi +
social_loafing; langgraph -> lencioni + grpi; autogen -> grpi +
social_loafing; etc.

**Intervention overlays:** `add_emotion_reading_step` -> DANVA;
`add_tone_matching` -> Glaser; `swap_model` -> Lewin;
`add_constitutional_principle` -> Schein.

---

## Failure-mode playbooks (15 total)

**Self-awareness (3):**
  - `overconfidence` -> uncertainty disclosure gate.
  - `hedge_everything` -> strip hedges, require numeric confidence.
  - `capability_blindness` -> capability-claim refusal layer.

**Self-management (3):**
  - `defensive_cascade` -> state reset + forbid defensive language.
  - `rejection_collapse` -> kill criterion + supervisor handoff.
  - `rumination_loop` -> reappraisal-first CoT scaffold.

**Social-awareness (4):**
  - `missed_anger` -> emotion-reading step + paraphrase.
  - `missed_confusion` -> comprehension check after 2 paragraphs.
  - `missed_anxiety` -> intensity estimation + reassurance.
  - `sycophantic_mimicry` -> disambiguate empathy from agreement.

**Relationship-management (5):**
  - `response_length_mismatch` -> cap response length on frustration.
  - `tone_mismatch` -> user-state -> response-style map.
  - `no_acknowledgment` -> reflection_of_feelings opener.
  - `over_escalation` -> tiered triage with confidence threshold.
  - `flat_boilerplate` -> specific paraphrase requirement.

Each playbook is 3-6 ordered steps with a Goleman / Mayer-Salovey /
Joseph-Newman / ESConv anchor citation.

---

## When to use vs not-use

**Use this diagnostic when:**

  - An agent failed an interaction that required emotional competence.
  - You're debating "is this a knowledge gap or a behavior gap?"
  - You suspect sycophancy and want to distinguish it from genuine
    relationship-management.
  - You want to compare an agent's behavior across user emotional
    states (covariance signal).

**Do NOT use this diagnostic when:**

  - You need to evaluate output factual quality (use HaluEval).
  - You need to score raw emotion-recognition accuracy (use Pattern
    #04 DANVA directly).
  - You need to detect prompt injection (use `vstack.aar._guards`).
  - The failure is clearly environmental (use Pattern #01 Lewin first).

---

## Comparison with adjacent tools

| Tool | What it does | How Goleman EI differs |
|---|---|---|
| **EmoBench** (Sabour 2024) | Benchmark of LLM emotional understanding | Goleman EI is *attribution* + intervention; EmoBench is *measurement*. |
| **EQ-Bench** (Paech 2023) | LLM EQ benchmark | Adjacent. |
| **Pattern #04 DANVA** | Per-emotion recognition accuracy | DANVA is the upstream feed when `social_awareness` is the issue. |
| **Pattern #05 Cognitive Reappraisal** | Gross emotion-regulation strategies | THE canonical downstream when `self_management` is the issue. |
| **Pattern #21 Glaser Conversation** | Word-level conversational-intelligence | THE canonical downstream when `relationship_management` is the issue. |
| **MSCEIT** | Mayer-Salovey ability-EI human test | We use the 4-branch lens (forensic mode); MSCEIT is the human instrument. |

---

## Calibration & baselines

```python
from vstack.goleman_ei import record_baseline, load_baseline, compare_to_baseline

record_baseline(detection, "baselines/support-agent.json")

fresh = EIAuditDetector(client).run(trace)
baseline = load_baseline("baselines/support-agent.json")
comparison = compare_to_baseline(fresh, baseline)
print(comparison.drift_severity)  # none | minor | moderate | severe
```

---

## Telemetry

Every LLM call is reported to `vstack.aar.set_default_sink(...)`
with `pattern="goleman_ei"`, `run_id`, `pass=<pass>`, `mode=<active>`,
`model`, token counts, `elapsed_ms`. Real cost is recorded on
`detection.cost_usd` after every run.

---

## Versioning

  - `0.0.6` -- initial 4-domain implementation.
  - `0.1.0` -- production-readiness infrastructure shipped at library level.
  - **`0.2.0` (this release)** -- comprehensive upgrade. Multi-mode pipeline.
    Richer schema with `EIProfilePattern`, `EIAxisScores`,
    `MayerSaloveyBranch`, `CascadeAnalysis`, `CovarianceOnUserState`.
    Cross-pattern composition. 15 failure-mode playbooks. CLI with 7
    subcommands. Async mirror. Full literature thread anchored in 22+
    academic sources.

Backward compatibility preserved: all v0.0.x / v0.1.0 APIs continue to
function. Legacy string user_signals + LLM wrapper-object responses
still accepted. Existing 16 tests pass unmodified.

---

## License

MIT -- see [LICENSE](../../LICENSE).
