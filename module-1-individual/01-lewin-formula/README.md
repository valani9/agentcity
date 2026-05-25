# Pattern #01 — Lewin Formula Diagnostic — B = f(P, E)

> *"Every psychological event depends upon the state of the person and at the same time on the environment, although their relative importance is different in different cases."*
> — Kurt Lewin, *Principles of Topological Psychology* (McGraw-Hill, 1936, p. 12)

**Status:** 🟢 shipped — v0.2.0 (gstack-grade upgrade).
**Module:** 1 (Individual) — applies anywhere an agent's behavior is being attributed.
**Anchor framework:** Kurt Lewin, *Principles of Topological Psychology* (1936). The `B = f(P, E)` formula is the foundation of modern field theory in social psychology. The diagnostic also draws on the full attribution-theory literature thread (Heider 1958, Kelley 1967, Ross 1977, Gilbert & Malone 1995), the person-situation debate's modern resolution (Mischel & Shoda 1995 CAPS; Funder & Ozer 1983 symmetry), Bandura's (1986) reciprocal determinism, and the MAST taxonomy (Cemri et al. 2025) of multi-agent LLM failure modes.

> For the full literature thread with page-citations, see [`lib/CITATIONS.md`](lib/CITATIONS.md) (11 academic sources).

---

## TL;DR — what this pattern does

When an AI agent fails, the team's reflexive attribution is usually
"the model is bad." This is **the fundamental attribution error**
(Ross 1977): observers systematically over-attribute behavior to
*disposition* (the model) and under-attribute to *situation* (the
scaffolding). The Lewin diagnostic redirects engineering effort to
the right locus.

It reads an agent failure trace and outputs:

  - **Per-locus scores** (`internal` / `environmental` / `interactional`)
    with confidence intervals.
  - **Evidence** — quotes from the trace + cited factors.
  - **Counterfactuals** (forensic mode) — "if you swap X to Y, the failure
    would / would-not persist." The operational test of the locus
    assignment.
  - **Ranked interventions** — what to change, in what order, with
    effort estimates, risk, reversibility (one-way vs two-way door),
    and success metrics.
  - **Composition handoffs** — names the next vstack pattern(s) to
    run based on dominant locus + framework + intervention shape.
  - **Failure-mode playbooks** — concrete 3–6 step recipes for the
    most common (locus, factor) combinations.
  - **Baseline comparison** (optional) — drift vs a stored historical
    detection. Catches silent regressions.

> The single thing the diagnostic earns its keep on: when the team
> attributed the failure to the model and the diagnostic finds the
> environment is at fault. The `OVERTURNS` verdict in the rendered
> output is the user-facing payoff.

---

## Install

```bash
pip install valanistack                # Stub-only — no API key needed for demos and CI.
pip install "vstack[anthropic]"   # Add the Anthropic client.
pip install "vstack[openai]"      # Add the OpenAI client.
pip install "vstack[ollama]"      # Add the local-Ollama client.
pip install "vstack[all]"         # All three.
```

The diagnostic itself has no LLM-provider dependencies beyond
`pydantic` and the standard library. Pick a client extra.

---

## Three pipeline modes

| Mode | LLM calls | Target latency | Target cost | When to use |
|---|---|---|---|---|
| `quick` | 1 | < 2s | < $0.005 | CI gates, live ops, dashboards |
| `standard` | 2 | < 10s | < $0.05 | Human-driven postmortems (the default) |
| `forensic` | 4 | < 60s | < $0.30 | Deep dives, contested attributions, regressions |

**Quick** issues one combined call: scoring + the single highest-impact
intervention. Returns `loci[]` and at most one `top_intervention`.

**Standard** issues two calls (the v0.0.x behavior, refined): full
locus scoring with Kelley covariance reasoning; then 2–4 ranked
interventions. The default.

**Forensic** issues four calls:

  1. **Locus scoring** with explicit Kelley (1967) covariation reasoning
     baked into the prompt (consensus + distinctiveness + consistency).
  2. **Counterfactual swap analysis** — for each locus, generate a
     "if we swapped X to Y, the failure would / would-not persist"
     statement. Populates `LocusEvidence.counterfactual`.
  3. **Gilbert-Malone bias-mechanism diagnosis** on the team's initial
     attribution. Names which of the four correspondence-bias mechanisms
     (Gilbert & Malone 1995) explains the misattribution.
  4. **Interventions** — 4–8 ranked, with composition targets.

Mode is set at the constructor or per-call:

```python
detector = LewinAttributionDetector(client, mode="forensic")
detector.run(trace)                  # forensic
detector.run(trace, mode="quick")    # override per-call
```

---

## Python quick start

```python
from vstack.lewin import (
    LewinAttributionDetector,
    AgentFailureTrace,
    FailureStep,
    IndividualFactor,
    EnvironmentalFactor,
    CovarianceSignal,
)
from vstack.aar import AnthropicClient

trace = AgentFailureTrace(
    agent_id="qa-bot-001",
    model_name="claude-opus-4-7",
    framework="langgraph",
    task="Answer 'When was Pluto reclassified?'",
    steps=[
        FailureStep(type="input", content="When was Pluto reclassified?"),
        FailureStep(type="tool_call", content="rag.search(query='Pluto reclassification')"),
        FailureStep(type="observation", content="returned a 2003 Wikipedia revision"),
        FailureStep(type="output", content="Pluto was reclassified in 2003."),
    ],
    outcome="Confidently wrong year. The correct year is 2006 (IAU resolution).",
    success=False,
    environmental_factors=[
        EnvironmentalFactor(
            factor="rag_context",
            description="Retrieval returned a 2003 Wikipedia revision.",
            factor_id="e-rag-stale",
        ),
    ],
    initial_attribution="the model is bad at facts",
    covariance_signal=CovarianceSignal(
        consensus="high",       # every model fails this question with this RAG
        distinctiveness="high", # this model nails other history questions
        consistency="high",     # the failure repeats reliably
    ),
)

detection = LewinAttributionDetector(AnthropicClient(), mode="forensic").run(trace)
print(detection.to_markdown())
# Dominant locus: ENVIRONMENTAL (score 0.85)
# Initial attribution: OVERTURNS
# Correspondence-bias mechanism: unaware
# Recommended downstream: vstack.smart_goal, vstack.schein_culture
# Playbook attached: "Stale / poisoned RAG — reindex, add freshness filter, source-date the prompt"
```

---

## CLI quick start

```bash
# Analyze a single trace, standard mode, markdown output.
vstack-lewin analyze --trace fixtures/stale_rag.json --client stub

# Forensic + JSON, piped into jq.
vstack-lewin analyze --trace fail.json --client anthropic \
    --mode forensic --format json | jq '.dominant_locus'

# Batch a corpus.
vstack-lewin batch --corpus eval/synthetic_lewin_failures.yaml \
    --out detections/ --mode standard

# Re-render an existing detection JSON to markdown.
vstack-lewin replay --detection detections/scenario-1.json

# List all available failure-mode playbooks.
vstack-lewin playbooks

# Show the cross-pattern composition graph.
vstack-lewin compose

# Dump the JSON schema for the input trace (for client SDKs).
vstack-lewin schema --target trace --out schemas/trace.json
```

CLI auth is via standard env vars (`ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`); the `stub` client needs nothing.

---

## The framework: a guided tour through the literature

The Lewin diagnostic doesn't rest on a single 1936 reference. It sits
inside a 90-year literature thread that resolves the
person-vs-situation debate and provides the cognitive mechanism for
why teams over-attribute to the model.

### 1. Lewin's field theory (1936, 1939, 1947, 1951)

  - **1936** — *Principles of Topological Psychology*. The behavior
    formula `B = f(P, E)` (originally `B = f(L)` with `L = P ∪ E`).
    Lewin's key empirical claim: the *psychological* environment ≠
    the physical environment (p. 23). For agents: the system prompt
    (a few hundred tokens) determines the agent's perceived
    environment, regardless of the application's full state.
  - **1939** — with Lippitt & White. Autocratic / democratic /
    laissez-faire experiment. *Behavior is set by the climate, not the
    person.* For agents: orchestration topology + system prompt = climate.
  - **1947** — Unfreeze-change-refreeze model. Model retraining /
    fine-tuning are forced refreezes; environmental-locus
    interventions are not. Anchors the model-version playbook.
  - **1951** — *Field Theory in Social Science* (posthumous).
    Force-field analysis. Behavior is the equilibrium of driving and
    restraining forces. The diagnostic's intervention recommendations
    are operationalized as "push on the right side of the field."

### 2. Attribution theory (Heider, Jones, Kelley, Ross)

  - **Heider 1958** — *The Psychology of Interpersonal Relations*.
    Original attribution theory. Personal vs impersonal causality.
  - **Jones & Davis 1965; Jones & Harris 1967** — Correspondent
    inference theory; the forced-essay paradigm. Empirical demonstration
    of dispositional over-attribution.
  - **Kelley 1967** — Covariation principle. Causes are inferred from
    **consensus** (do others behave this way too?), **distinctiveness**
    (does the actor behave this way only here?), and **consistency**
    (does the behavior recur over time?). **Direct mapping to the
    diagnostic's `CovarianceSignal` schema input.** Forensic mode's
    locus-scoring prompt walks through all three explicitly.
  - **Ross 1977** — Names the **fundamental attribution error**.
    Argued FAE is the "conceptual bedrock" of social psychology. This
    is the bias the diagnostic exists to correct.
  - **Gilbert & Malone 1995** — Names four mechanisms by which
    observers over-attribute: (a) **unaware** of situational
    constraints, (b) **unrealistic expectations** for typical situational
    behavior, (c) **over-categorization** of the actor's traits,
    (d) **incomplete correction** after learning of the constraint.
    **Direct mapping to the diagnostic's `GilbertMaloneMechanism`
    schema field.** Forensic mode names which mechanism applies to
    the team's misattribution.

### 3. The person-situation debate (Mischel, Funder, CAPS)

  - **Mischel 1968** — Cross-situational consistency r ≈ .30. Read
    by some as "person doesn't matter." Triggered the debate.
  - **Funder & Ozer 1983** — Situations also produce r ≈ .30–.40.
    The empirical symmetry. Both sides of `B = f(P, E)` are roughly
    equally predictive.
  - **Mischel & Shoda 1995 — CAPS.** Personality as a stable network
    of cognitive-affective units producing "if-situation-A-then-
    behavior-X" signatures. **Direct map to LLM agents:** the model's
    prompt-conditioned behavior policy.
  - **Funder 2006** — Finalizes the interactionist position. The
    "personality triad" — persons, situations, behaviors — as the
    joint unit. Frames the *interactional* locus.

### 4. Reciprocal determinism (Bandura)

  - **Bandura 1986** — Triadic reciprocal causation: P ↔ B ↔ E,
    each leg influencing the other two over time. The Lewin diagnostic
    gives the *instantaneous* reading; reciprocity is the *temporal*
    extension over multi-turn agent loops.

### 5. Modern AI agent failure taxonomies (MAST)

  - **Cemri et al. 2025 — MAST** (arXiv:2503.13657 / NeurIPS).
    14 multi-agent failure modes in 3 categories: specification &
    system design; inter-agent misalignment; task verification &
    termination. **Empirical finding: most multi-agent LLM failures
    arise from inter-agent / system design (environmental locus),
    not model capability (internal locus).** The diagnostic's
    environmental tie-break is empirically supported, not just
    aesthetically chosen.

---

## What "P" and "E" mean for an LLM agent

**Internal (P) — the model's "person" components:**

| factor | description |
|---|---|
| `base_model` | Pretraining distribution, architecture, parameters. |
| `fine_tuning` | Domain adaptation, instruction tuning. |
| `rlhf` | Behavioral priors imposed by RLHF / DPO / Constitutional alignment. |
| `training_cutoff` | Knowledge bound. |
| `reasoning_capability` | Depth of in-context reasoning. |
| `tool_use_skill` | Tool-call competence. |
| `language_support` | Per-language fluency. |
| `context_window_size` | Tokens the model can see. |
| `sampling_config` | Temperature, top-p, top-k, seed, repetition penalty. |
| `model_version` | Identical model id but a quiet update changes behavior. |
| `inference_settings` | Max output tokens, reasoning effort, tool-choice mode. |
| `safety_filter_strictness` | How aggressively the model refuses. |
| `decoding_strategy` | Greedy vs sampling vs constrained decoding. |
| `other` | Catch-all. |

**Environmental (E) — everything outside the model in this turn:**

| factor | description |
|---|---|
| `system_prompt` | The agent's role / rules / constraints. |
| `tools_available` | Tools registered with the agent. |
| `rag_context` | Retrieved chunks the agent saw. |
| `task_framing` | How the user's request was framed. |
| `user_inputs` | What the user actually said. |
| `downstream_consumers` | Shape and contract the output must satisfy. |
| `rate_limits` | Constraints from the provider. |
| `tool_responses` | What tools actually returned. |
| `feedback_loops` | Self-critique, refinement loops. |
| `orchestration` | The agent graph / control flow. |
| `conversation_history` | Prior turns in context. |
| `memory_store` | Persistent memory the agent reads / writes. |
| `output_parser` | Validator / JSON-parser at the boundary. |
| `safety_filter` | External safety / moderation layer. |
| `caching_layer` | Response or context cache. |
| `multi_agent_topology` | Single-agent vs planner/executor/critic. |
| `verification_step` | Explicit verification before "task complete." |
| `other` | Catch-all. |

---

## The AI-agent failure mode this diagnostic addresses

> *Most multi-agent LLM system failures we observed arise from
> inter-agent interactions and system design choices, not from
> model capability limitations.*
> — Cemri et al. 2025, MAST analysis

The diagnostic's environmental tie-break (`environmental` wins on a
tie within 0.05) is empirically grounded — when in doubt, the
literature says the cause is the scaffolding, not the model.

Concretely, the diagnostic helps teams:

  1. Detect when an attribution to the model is wrong. (`OVERTURNS` verdict.)
  2. Name *which* mechanism caused the misattribution. (forensic mode →
     `bias_mechanism` field, one of `unaware`, `unrealistic_expectation`,
     `over_categorization`, `incomplete_correction`, `none`.)
  3. Stop sending engineering effort to model swaps when the prompt is
     under-specified. (intervention `effort_estimate` makes the cost
     of model swaps explicit relative to prompt patches.)
  4. Carry a paper-trail of attribution decisions. (`run_id` plus
     stored detection JSON enables reproducibility.)
  5. Detect drift over time. (`compare_to_baseline` flags moves in the
     dominant locus or large score deltas.)

---

## Composition with other patterns

The diagnostic auto-attaches a `ComposedPatternHandoff` to every
detection. Recommendations are conservative; only patterns that are
operationally relevant for `(dominant_locus, framework, intervention
shape)` are surfaced.

**Per-locus downstream recommendations:**

  - `internal` → `vstack.bias_stack`, `vstack.hexaco`,
    `vstack.goleman_ei`
  - `environmental` → `vstack.smart_goal`, `vstack.grpi`,
    `vstack.lencioni`, `vstack.schein_culture`,
    `vstack.psych_safety`
  - `interactional` → `vstack.aar`, `vstack.trust_triangle`,
    `vstack.vroom_expectancy`
  - `indeterminate` → `vstack.aar` (human-led postmortem)

**Framework overlays** (additive):

  - `langgraph` → `+ devils_advocate`, `+ group_decision`
  - `crewai` → `+ grpi`, `+ social_loafing`, `+ devils_advocate`
  - `autogen` → `+ group_decision`, `+ devils_advocate`, `+ social_loafing`
  - `openai-agents-sdk` → `+ process_gain_loss`
  - `claude-agent-sdk` → `+ process_gain_loss`
  - `mastra`, `strands` → `+ grpi`

**Intervention overlays** — when an intervention's `intervention_type`
points so directly at another pattern that we surface it regardless of
locus:

  - `change_prompt` → `vstack.schein_culture`
  - `add_verification_step` → `vstack.devils_advocate`
  - `change_topology` → `vstack.grpi`
  - `change_memory` → `vstack.johari`
  - `new_eval` → `vstack.smart_goal`
  - `human_review` → `vstack.plus_delta`

### Composition recipes

  1. **AAR → Lewin → next pattern.** AAR (#30) produces lessons; each
     lesson can be turned into an `AgentFailureTrace` and fed into
     Lewin for locus attribution. Lewin's `composition_handoff` then
     names the next downstream pattern.
  2. **Lewin → Bias-Stack (when `internal` dominant).** Bias-Stack
     diagnoses the specific reasoning bias driving the internal
     failure.
  3. **Lewin → GRPI / Lencioni (when `environmental` dominant + multi-agent).**
     Audit the working agreement and team-level dysfunction.

See [`examples/cookbook/01_aar_then_lewin.py`](../../examples/cookbook/01_aar_then_lewin.py)
in the repo root for a runnable composition demo.

---

## Failure-mode playbooks

Every `(locus, factor)` combination with a curated playbook is
auto-attached to detections when an intervention targets that key.
Run `vstack-lewin playbooks` to see the full list.

**Internal:**

  - `(internal, context_window_size)` → Context-window overflow —
    chunk + map-reduce, do **not** fine-tune.
  - `(internal, sampling_config)` → Stochastic failure — pin temperature
    + seed before swapping the model.
  - `(internal, model_version)` → Silent model update broke production —
    pin version + add a smoke gate.
  - `(internal, rlhf)` → RLHF refusal — system-prompt reframe before
    re-fine-tune.
  - `(internal, reasoning_capability)` → Reasoning ceiling — chain-of-
    thought, then escalate to a reasoning model.

**Environmental:**

  - `(environmental, rag_context)` → Stale / poisoned RAG — reindex,
    add freshness filter, source-date the prompt.
  - `(environmental, system_prompt)` → Under-specified system prompt —
    add explicit acceptance criteria.
  - `(environmental, orchestration)` → Orchestration loop —
    termination condition + max-iter cap.
  - `(environmental, tools_available)` → Tool shape mismatch — match
    the tool surface to the task.
  - `(environmental, task_framing)` → Ambiguous framing — rewrite via
    SMART.
  - `(environmental, downstream_consumers)` → Output shape mismatch —
    schema validator at the boundary.
  - `(environmental, verification_step)` → No verification step — add
    a critique pass.
  - `(environmental, user_inputs)` → Hostile / under-specified user
    input — sanitize, fence, clarify.

**Interactional:**

  - `(interactional, system_prompt)` → System-prompt × model-bias —
    fix env first, re-evaluate.
  - `(interactional, rag_context)` → RAG × model-capacity interaction —
    chunk + summarize first.

Each playbook is 3–6 ordered steps with an OB or MAST citation. View
the full text via `vstack-lewin playbooks --format markdown`.

---

## When to use vs not-use

**Use this diagnostic when:**

  - You have an agent failure trace (`task`, `steps`, `outcome`,
    `success`) and want to know where to spend engineering effort.
  - A team disagreement exists on what to fix ("rewrite the prompt!"
    vs "swap the model!") and you want an evidence-grounded vote.
  - You're tracking drift over time and want to know when the dominant
    locus has shifted.
  - You're auditing an attribution your team made and want a second
    opinion (forensic mode is designed for this).

**Do NOT use this diagnostic when:**

  - You need to evaluate output *quality* (use HaluEval, TruthfulQA,
    or a task-specific eval).
  - You need to detect jailbreaks or unsafe outputs (use a moderation
    classifier and the OWASP LLM Top 10).
  - You need to root-cause infrastructure failures (use OpenTelemetry
    traces and APM tools).
  - You don't have a failure trace yet (Lewin diagnoses observed
    failures; it doesn't speculate about hypothetical ones).

---

## Comparison with adjacent tools

| Tool | What it does | How Lewin differs |
|---|---|---|
| **TruthfulQA / HaluEval** | Evaluate output quality on factual / hallucination dimensions. | Lewin diagnoses *attribution* (where to fix), not *quality* (what's right). They compose. |
| **MAST + Who&When (Cemri 2025)** | Taxonomy + benchmark of multi-agent failure modes. | Lewin uses MAST's findings to ground its env-locus tie-break; consumes a single trace, not a corpus. |
| **AgenTracer / AgentRx** | Automated multi-agent trajectory diagnosis. | Adjacent. They identify the failure step; Lewin attributes locus across `P × E` and proposes interventions. Often used together. |
| **LangSmith / Phoenix / Langfuse** | Agent trace observability. | They give you the trace; Lewin reads it. |
| **vstack AAR (#30)** | Wharton 4-step postmortem. | AAR finds the *lesson*; Lewin attributes the *cause*. The cookbook recipe chains them. |
| **vstack Bias-Stack (#27)** | Detect specific reasoning biases. | When Lewin says `internal`, route to Bias-Stack to name the bias. |
| **OWASP LLM Top 10** | Vulnerability checklist for LLM apps. | Lewin's playbooks reference LLM07 + LLM08 directly. Different scope; complementary. |

---

## Calibration & baselines

Production deployments often want to detect when a regression has
shifted the dominant locus. Two operations:

```python
from vstack.lewin import record_baseline, load_baseline, compare_to_baseline

# After running the diagnostic, record the detection as a baseline.
record_baseline(detection, "baselines/qa-bot.json")

# Some weeks later, compare a fresh detection.
fresh = LewinAttributionDetector(client).run(trace)
baseline = load_baseline("baselines/qa-bot.json")
comparison = compare_to_baseline(fresh, baseline)
print(comparison.drift_severity)  # none | minor | moderate | severe
```

Drift severity buckets:

  - **none** — every locus delta ≤ 0.10 *and* dominant locus unchanged.
  - **minor** — some locus delta in (0.10, 0.20], dominant unchanged.
  - **moderate** — some delta in (0.20, 0.40], or dominant changed
    within the same family (internal ↔ interactional, environmental
    ↔ interactional).
  - **severe** — some delta > 0.40, or dominant flipped internal ↔
    environmental directly.

The CLI's `analyze --baseline path.json` does this in one step and
includes the comparison in the rendered output.

---

## Telemetry

Every LLM call in every mode is reported to the
`vstack.aar.set_default_sink(...)` sink with:

  - `pattern="lewin"`, `run_id=<stable id>` (from `run_context`),
  - `pass=<quick|standard_loci|standard_interventions|forensic_loci|forensic_counterfactuals|forensic_bias_mechanism|forensic_interventions>`,
  - `mode=<active mode>`,
  - `model`, `input_tokens`, `output_tokens`, `total_tokens`, `elapsed_ms`.

The default sink is `NullTelemetrySink` (off). For production, install
the `InMemoryTelemetrySink` for tests or wire your own sink in front of
Datadog / Honeycomb / OTLP / Prometheus.

Per-mode rough cost budgets (claude-sonnet @ $3/M input, $15/M output):

  - `quick` — ~500 tokens × 2 (input + output) ≈ $0.005.
  - `standard` — ~1500 tokens total ≈ $0.025.
  - `forensic` — ~4000 tokens total ≈ $0.10.

Real cost is recorded in `detection.cost_usd` after every run.

---

## Files in this directory

| Path | Lines | Purpose |
|---|---|---|
| `README.md` | this file | The pattern's overview + lit thread + composition + playbooks. |
| `essay.md` | ~100 | Substack-ready essay. |
| `lib/schema.py` | ~840 | Pydantic schema (input + output + auxiliary). |
| `lib/generator.py` | ~1050 | Multi-mode pipeline + async mirror + telemetry. |
| `lib/prompts.py` | ~390 | LLM prompt templates per mode + assemble_prompt helper. |
| `lib/_composition.py` | ~140 | Composition manifest + recommended_downstream. |
| `lib/_calibration.py` | ~115 | Baseline record / load / compare + drift bucket. |
| `lib/_playbooks.py` | ~280 | `(locus, factor)` → playbook table. |
| `lib/cli.py` | ~360 | `vstack-lewin` CLI entry point. |
| `lib/__init__.py` | ~190 | Public API surface (`__all__`). |
| `lib/CITATIONS.md` | ~200 | Full bibliography (11 academic sources). |
| `tests/test_lewin.py` | ~270 | v0.0.x test suite (kept for backward compatibility). |
| `tests/test_lewin_v2.py` | ~870 | v0.2.0 comprehensive tests: schema, modes, guards, telemetry, run-context, composition, calibration, playbooks, async. |
| `tests/test_lewin_cli.py` | ~260 | CLI smoke tests for all subcommands. |
| `demo/01_self_contained_demo.py` | ~250 | Stale-RAG self-contained demo (kept). |
| `eval/synthetic_lewin_failures.yaml` | ~140 | Hand-crafted failure-mode corpus. |
| `eval/run_benchmark.py` | ~160 | Corpus runner. |

Total: ~5,500 LOC across the pattern (up from ~1,680 in v0.1.0).

---

## Versioning

  - `0.0.5` (Module 1 kickoff) — initial implementation.
  - `0.1.0` — production-readiness infrastructure shipped at the
    library level (telemetry, structured logging, prompt-injection
    guards). Pattern interfaces unchanged.
  - **`0.2.0` (this release)** — comprehensive upgrade. Multi-mode
    pipeline (quick / standard / forensic). Richer schema with new
    Literals, `CovarianceSignal`, `BaselineComparison`,
    `ComposedPatternHandoff`, `AttachedPlaybook`. Cross-pattern
    composition. Failure-mode playbooks. CLI. Async mirror. Full
    literature thread anchored in 11 academic sources.

Backward compatibility: all v0.0.x and v0.1.0 schemas continue to
deserialize. New fields have safe defaults. Old severity values
(`none`, `low`, `medium`, `high`) remain valid alongside the 7-point
extended scale (`none`, `trace`, `low`, `moderate`, `medium`, `high`,
`critical`).

---

## License

MIT — see [LICENSE](../../LICENSE).
