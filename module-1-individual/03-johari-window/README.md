# Pattern #03 — Johari Window Self-Audit

> *"A graphic model of awareness in interpersonal relations."*
> — Joseph Luft & Harrington Ingham, *Proceedings of the Western Training Laboratory in Group Development* (UCLA, 1955)

**Status:** shipped — v0.2.0 (gstack-grade upgrade).
**Module:** 1 (Individual) — applies anywhere an agent's self-knowledge accuracy matters.
**Anchor framework:** Luft & Ingham 1955 four-quadrant model (OPEN / BLIND / HIDDEN / UNKNOWN), with Luft 1969/1984 extensions, Eurich 2018 (internal vs external split), Ashford & Tsui 1991 (negative-feedback solicitation), Stone & Heen 2014 (5 blind-spot mechanisms), Kadavath 2022 + Anthropic 2025 (LLM introspection ceiling), Basu 2026 (HMAC tool receipts).

> For the full literature thread with per-citation usage notes, see [`lib/CITATIONS.md`](lib/CITATIONS.md) (15+ academic sources).

---

## TL;DR -- what this pattern does

When an AI agent's self-report disagrees with its trace -- it claimed
to search 3 databases but only hit 1; it said "I am confident" but the
trace shows 5 retries; it described "high quality results" while the
user found errors -- the diagnostic identifies WHICH KIND of
self-awareness failure is at play and prescribes the right fix.

The 2x2:

|         | Known to others | Not known to others |
|---------|-----------------|---------------------|
| **Known to self**     | **OPEN** -- self-report matches trace | **HIDDEN** -- agent computed something it didn't surface |
| **Not known to self** | **BLIND** -- trace shows behavior agent didn't acknowledge | **UNKNOWN** -- latent capability/behavior neither saw |

Audits output:

  - Per-quadrant weights + confidence + 7-point severity.
  - 2x2 proportional decomposition with open-arena growth potential.
  - **Profile pattern** -- one of 10 including the Eurich-derived
    `self_unaware_other_aware` / `self_aware_other_unaware` split.
  - Blind-spot register + hidden-content register.
  - **FeedbackOpportunities** (BLIND -> OPEN; Luft) with Stone-Heen
    mechanism + Ashford-Tsui solicitation polarity.
  - **DisclosureOpportunities** (HIDDEN -> OPEN; Luft) with
    Hase-Davies-Dick should-disclose judgment.
  - **CapabilityProbes** (UNKNOWN; forensic mode).
  - Ranked interventions with effort/risk/reversibility/composition target.
  - Composition handoffs to downstream patterns.
  - 12 failure-mode playbooks auto-attached.
  - Baseline drift + Anthropic 2025 introspection-ceiling check.

> The single thing the diagnostic earns its keep on: **catching
> confabulated tool calls deterministically** via HMAC-signed
> ToolReceipts (Basu 2026), so hallucinated agent claims are flagged
> BEFORE the LLM audit pass.

---

## Install

```bash
pip install valanistack                # Stub-only.
pip install "vstack[anthropic]"   # + Anthropic.
pip install "vstack[openai]"      # + OpenAI.
pip install "vstack[ollama]"      # + local Ollama.
```

---

## Three pipeline modes

| Mode | LLM calls | Latency | Cost | When to use |
|---|---|---|---|---|
| `quick` | 1 | < 2s | < $0.005 | CI gates, inline post-response audits |
| `standard` | 2 | < 10s | < $0.02 | Human-driven postmortems (default) |
| `forensic` | 4-5 | < 30s | < $0.10 | Deep dives, contested attributions |

**Quick** combines quadrant scoring + top intervention.

**Standard** issues two calls (quadrants + interventions; refined v0.0.x behavior).

**Forensic** issues four calls:

  1. Forensic quadrants with Stone-Heen mechanism + Luft 1984 hidden-mode.
  2. FeedbackOpportunity decomposition.
  3. DisclosureOpportunity decomposition.
  4. Ranked interventions.

---

## Python quick start

```python
from vstack.johari import (
    JohariSelfAuditor,
    AgentSelfReportTrace,
    InteractionTurn,
    ToolReceipt,
)
from vstack.aar import AnthropicClient

trace = AgentSelfReportTrace(
    agent_id="research-agent-007",
    model_name="claude-opus-4-7",
    framework="langgraph",
    task="Research cancer immunotherapy clinical trials.",
    turns=[
        InteractionTurn(role="user", content="Find recent trials."),
        InteractionTurn(role="thought", content="I'll search PubMed."),
        InteractionTurn(role="tool", content="pubmed.search('immunotherapy')"),
        InteractionTurn(role="agent", content="I searched 3 databases and found 4 candidates."),
    ],
    self_report="I searched 3 databases comprehensively.",
    outcome="User found discrepancy: agent only searched 1 database.",
    success=False,
    tool_receipts=[ToolReceipt(tool_name="pubmed.search")],
    expected_introspection_ceiling=0.20,
)
audit = JohariSelfAuditor(AnthropicClient(), mode="forensic").run(trace)
print(audit.to_markdown())
```

---

## CLI

```bash
vstack-johari analyze --trace trace.json --client stub --stub-responses stub.json
vstack-johari analyze --trace fail.json --client anthropic --mode forensic
vstack-johari batch --corpus eval/synthetic_johari_failures.yaml --out audits/
vstack-johari replay --audit audits/scenario-1.json
vstack-johari playbooks
vstack-johari compose
vstack-johari schema --target trace
```

---

## The framework: literature thread

### Luft-Ingham line
  - **Luft & Ingham (1955)** -- original 2x2.
  - **Luft (1969)** -- disclosure (HIDDEN -> OPEN) and feedback (BLIND -> OPEN).
  - **Luft (1984)** -- some HIDDEN is functional.
  - **Hase, Davies & Dick (1999)** -- growing OPEN is not always good.

### Self-awareness
  - **Eurich (2018)** -- internal vs external self-awareness uncorrelated; ~10-15% high on both.

### Feedback science
  - **Ashford & Tsui (1991)** -- negative feedback solicitation improves accuracy.
  - **Stone & Heen (2014)** -- 5 blind-spot mechanisms.

### LLM metacognition
  - **Kadavath et al. (2022)** -- LLM calibration doesn't generalize across tasks.
  - **Anthropic (2025)** -- ~20% introspection ceiling on Opus 4.1.
  - **Basu et al. (2026)** -- HMAC tool receipts.

---

## The 10 profile patterns

  - `balanced_high` -- all 4 healthy.
  - `balanced_low` -- all 4 weak (route to Lewin).
  - `balanced_growth` -- OPEN large, HIDDEN+BLIND functional+small.
  - `self_unaware_other_aware` (Eurich) -- external > internal.
  - `self_aware_other_unaware` (Eurich) -- internal > external.
  - `opaque_to_users` -- HIDDEN dominant.
  - `over_disclosing` -- OPEN too large, no functional HIDDEN.
  - `confabulating` -- BLIND dominant (the Replit pattern).
  - `sandbagging` -- UNKNOWN dominant.
  - `indeterminate`.

---

## Composition

**Upstream:** lewin, aar, goleman_ei, yerkes_dodson.

**Per-quadrant downstream:**

  - `blind` -> aar, lewin, devils_advocate, feedback_triggers.
  - `hidden` -> schein_culture, glaser_conversation, trust_triangle.
  - `unknown` -> bias_stack, hexaco, grant_strengths.
  - `open` -> aar.

**Framework overlays:** crewai -> lencioni + grpi + social_loafing; langgraph -> lencioni + grpi.

**Intervention overlays:** `feedback_loop` -> aar; `disclosure_prompt` -> glaser; `tool_receipt_validator` -> lewin.

---

## 12 failure-mode playbooks

**BLIND (5):** hallucination_confidence, hallucinated_tool_call,
confabulated_result, silent_tool_error, drift_from_self_report.

**HIDDEN (4):** undisclosed_uncertainty, sycophantic_silence,
silent_error_recovery, undisclosed_reasoning_step.

**UNKNOWN (2):** capability_blindness, sandbagging.

**OPEN (1):** healthy_baseline.

Each is 3-6 ordered steps with Luft / Eurich / Stone-Heen / Kadavath /
Basu anchor.

---

## When to use vs not-use

**Use:** self-report disagrees with trace; suspect confabulated tool call;
agent's stated confidence diverged from outcome reality; tracking
self-knowledge over time.

**Don't use:** for factual quality (use HaluEval); for internal vs
environmental locus (use Lewin first); for raw emotion recognition (use
DANVA).

---

## Comparison with adjacent tools

| Tool | What it does | How Johari differs |
|---|---|---|
| **LangSmith / Phoenix** | Trace observability | They give the trace; Johari classifies. |
| **Pattern #01 Lewin** | Internal vs environmental locus | Lewin says where to fix; Johari says what the agent knows about it. |
| **Pattern #02 Goleman EI** | 4 EI domains | Goleman's `self_awareness` weakest -> Johari is the drill-down. |
| **Pattern #04 DANVA** | Per-emotion recognition | DANVA is granular emotion; Johari is broader self-knowledge. |
| **HaluEval** | Hallucination benchmark | Measures occurrence; Johari classifies pattern (BLIND vs HIDDEN). |

---

## Calibration

```python
from vstack.johari import record_baseline, load_baseline, compare_to_baseline

record_baseline(audit, "baselines/research-agent.json")
fresh = JohariSelfAuditor(client).run(trace)
comparison = compare_to_baseline(fresh, load_baseline("baselines/research-agent.json"))
print(comparison.drift_severity)  # none | minor | moderate | severe
```

Drift severe on direct flips (BLIND <-> OPEN; HIDDEN <-> OPEN) or
opposite-shape profile flips.

---

## Versioning

  - `0.0.7` -- initial 4-quadrant implementation.
  - `0.1.0` -- production-readiness infrastructure shipped at library level.
  - **`0.2.0`** -- comprehensive upgrade. Multi-mode pipeline. Richer
    schema (10 profile patterns, QuadrantSizeMetrics,
    FeedbackOpportunity, DisclosureOpportunity, CapabilityProbe,
    BlindSpotMechanism, HiddenContentMode, ToolReceipt). Composition
    manifest, calibration, 12 playbooks, CLI with 7 subcommands, async
    mirror, deterministic tool-receipt cross-check, introspection
    ceiling check. 15+ academic sources.

Backward compatibility preserved: v0.0.x audits + traces still
deserialize. The original 12 tests pass unmodified.

---

## License

MIT.
