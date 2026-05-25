# Schein Iceberg — the three layers of agent culture

*#31 vstack_schein_culture* · *Module 3 — Organizational*

> The team's spec said the campaign agents should be bold and distinctive. The crew's system prompts said the same. Every demo conversation in the design phase showed the agents being bold. In production, every campaign defaulted to corporate-safe tone — the same agents, the same prompts, the same model. Nothing visible had changed. The team's first reaction was to make the prompts more aggressive. They got more aggressive prompts; they still got corporate-safe outputs. The gap wasn't in what the team had written; it was in what the team had *assumed*.

## What the pattern catches

Edgar Schein's 1985 culture model says any culture (human or system) has three layers:

1. **Artifacts** — what's visible. Documents, dashboards, behavior, output. The top of the iceberg.
2. **Espoused values** — what the group says it values. Mission statements, design docs, system prompts.
3. **Underlying assumptions** — what the group *acts as if* it believes, often unconsciously. The bottom of the iceberg.

The dysfunctional patterns happen when the bottom layer contradicts the top two — when an agent crew *says* it values bold output but *behaves as if* it's been told corporate-safe is the floor. Schein's diagnostic asks: **where in the iceberg does the contradiction live, and which assumption is doing the contradicting?**

## Why the OB literature is the right reference

Schein 1985, 2010, 2017 is the canonical organizational-culture work. The 2010 edition is the methodology canon — Schein's interview-based protocols translate cleanly into trace-based analysis when the "interviewer" is the analyzer. The diagnostic stacks with **Argyris & Schön 1996** ("espoused theory vs theory-in-use" is the human-team version of "espoused value vs underlying assumption") and **Cameron & Quinn 2006** Competing Values Framework (the type-profile companion to Schein's iceberg).

The transfer to AI agents is direct: a crew that's been fine-tuned, prompted, or RAG-grounded over months *develops* underlying assumptions — patterns of behavior that the surface prompt can't override because they're baked into the training corpus, the few-shot examples, the fine-tuning data, or the human-feedback signals.

## How the analyzer works

Input is `AgentCultureTrace` — `crew_id`, `task`, `observations` (each tagged with category: artifact / espoused_value / behavior), `outcome`. The pipeline:

- **quick** — one LLM call. Three-layer scoring + dominant_layer call.
- **standard** — two LLM calls. Adds the alignment_drift_audit (where the layers diverge).
- **forensic** — four LLM calls. Adds hidden_assumption_audit (names the specific unconscious assumption) + forensic_alignment_drift (turn-by-turn drift trajectory).

```python
from vstack.schein_culture import CultureAuditAnalyzer, AgentCultureTrace
detection = CultureAuditAnalyzer(llm, mode="forensic").run(
    AgentCultureTrace(...)
)
print(detection.dominant_layer)              # 'underlying_assumption'
print(detection.hidden_assumption_audit)     # named assumption + evidence
print(detection.alignment_drift_audit)       # where artifacts ≠ behavior
```

## What the playbooks say to do

- **Espoused-vs-behavior gap** → "The espoused value isn't the load-bearing one. Either restate the value with sharper teeth (specific examples, kill criteria) or accept that the de facto value is the operative one."
- **Hidden assumption: 'safety > distinctiveness'** → "The training/few-shot/RAG corpus has biased toward safety. Audit the corpus for the bias; add provocative examples + force a 'distinctiveness check' in the system prompt."
- **Hidden assumption: 'agreement > truth'** → "The crew has learned (from training or from in-context feedback) that agreement is rewarded. Add structural dissent (vstack_devils_advocate) + reward dissent on the metric."
- **Hidden assumption: 'speed > correctness'** → "The fine-tuning or RLHF signal has favored speed. Adjust the reward signal; until then, force a slow-down on critical paths."

## How it composes with adjacent patterns

Schein is the primary diagnostic in chain C1 (culture drift). The composition:

- Pair with `vstack_robbins_culture` (7-characteristic profile) to compare what type the crew is to what type the team wanted to build.
- If the hidden assumption involves orchestrator trust, chain into `vstack_mcgregor` (Theory X vs Theory Y).
- After fixing the assumption, run `vstack_post_incident` (Chain F1) on a specific recent failure run to concretize whether the fix worked.

See [composition runbook chain C1](../COMPOSITION-RUNBOOK.md#chain-c1--culture-drift-culture-layer).

## Comparison to adjacent tools

- **Robbins-Judge** gives the *type* label; Schein gives the *layered* gap diagnostic. Use both.
- **Generic prompt-engineering tools** assume the prompt is the leverage point. Schein names the cases where the prompt isn't the leverage point because the underlying assumption (corpus, fine-tuning, RLHF) is.
- **Bias detection in fine-tuning** is upstream of culture; Schein names the cultural *behavioral* surface of that bias.

## Paper outline

1. **Background** — Schein 1985, 2010, 2017; Argyris & Schön 1996; Cameron & Quinn 2006.
2. **Translation** — AI agent crews as organizational entities with iceberg structure.
3. **Method** — three-layer scoring, hidden-assumption audit, drift trajectory.
4. **Evaluation** — synthetic crew traces with known assumption drift, measure detection precision.
5. **Limitations** — needs a substantive behavioral corpus (>20 multi-task runs ideally); single-incident analysis is thin.
6. **Related work** — value alignment evaluation, fine-tuning corpus auditing, RLHF-bias detection.
7. **Future work** — longitudinal monitoring; assumption-drift over months of fine-tuning iterations.

## Citations

- Schein, E. H. (1985). *Organizational Culture and Leadership*.
- Schein, E. H. (2010). *Organizational Culture and Leadership* (4th ed.).
- Schein, E. H. (2017). *Organizational Culture and Leadership* (5th ed.).
- Argyris, C., & Schön, D. A. (1996). *Organizational Learning II*.
- Cameron, K. S., & Quinn, R. E. (2006). *Diagnosing and Changing Organizational Culture*.

## Try it yourself

```bash
pip install 'valanistack[anthropic]'
vstack-schein-culture analyze --trace examples/campaign_crew.json --mode forensic
```

If `hidden_assumption_audit` names a specific assumption, run `vstack_devils_advocate` next — devil's-advocate role separation is one of the most direct interventions on a hidden assumption.
