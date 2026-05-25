# <Pattern friendly name> — <one-line hook>

*<Pattern number + import name>* · *<Module: individual / team / organizational>*

> One-paragraph hook describing a real-world agent failure this pattern catches. Write it as a story — concrete agent, concrete moment, concrete consequence. Avoid jargon in the first paragraph; the rest of the essay earns the right to use the OB vocabulary.

## What the pattern catches

Two-to-three paragraphs naming the *agent failure mode* in plain English. Examples:

- "An agent that confidently makes up dates."
- "A multi-agent crew that ships fast but never disagrees."
- "An orchestrator that micromanages every subordinate's output."

End this section with a one-sentence statement of what the pattern's analyzer answers. ("Did the failure come from the model layer, the prompt layer, or both?")

## Why the OB literature is the right reference

One paragraph anchoring the pattern in a named OB framework + 1-3 canonical citations:

> The diagnostic is anchored in <Author, Year> + <Author, Year>. <Author>'s <Year> insight was that <one-sentence summary of the framework>. That insight transfers to AI agents because <one-sentence bridge>.

The bridge sentence is the hardest part of the essay. The reader has to feel that the OB framework wasn't grafted on — it was the right answer all along.

## How the analyzer works

Walk through the analyzer's pipeline at the right level of detail:

- What input it takes (one paragraph naming the trace shape).
- What it does in each of the three modes (quick / standard / forensic). One sentence each.
- What it returns (severity / profile_pattern / dominant_finding / interventions / playbooks / composition).

Include ~10-20 lines of pseudo-code or actual code. Don't reproduce the full analyzer — the reader can read the source. Show the *shape* of the run.

```python
from vstack.<pattern> import <Analyzer>, <Input>
detection = <Analyzer>(llm, mode="standard").run(<Input>(...))
print(detection.dominant_<field>, detection.severity)
```

## What the playbooks say to do

One paragraph per top playbook. Cite the specific (locus, factor) or (layer, dimension) key. Show the intervention text + its literature anchor.

This section is what separates a writeup from a marketing post. The reader leaves knowing *what to actually try* when the pattern fires.

## How it composes with adjacent patterns

The composition manifest names upstream + downstream patterns. Walk through one or two of the canonical chains:

- "If `<this pattern>` says `<finding>`, run `<downstream pattern>` next because <why>."
- "If `<upstream pattern>` already flagged this, `<this pattern>` is the deepening pass that <how>."

Cross-link to the [composition runbook](../COMPOSITION-RUNBOOK.md) chain (F1 / T1 / S1 / C1 / D1) where the pattern appears.

## Comparison to adjacent tools

One paragraph naming 1-3 *similar* tools (other vstack patterns, or external libraries) and explaining the difference in one sentence each. Examples:

- "vstack_lewin is the localization pass; vstack_aar is the lessons pass. AAR doesn't try to localize."
- "Lencioni is the layered diagnostic; Edmondson is the per-axis score. Use both."

## Paper outline

A 5-7 bullet outline of the academic paper this pattern would seed:

1. **Background** — the OB framework, its 2-3 most important citations.
2. **Translation** — why the framework transfers to AI agents (the bridge).
3. **Method** — the analyzer's pipeline + the (mode × output) matrix.
4. **Evaluation** — what benchmark suite would test it (e.g. GAIA, SWE-Bench-multi).
5. **Limitations** — where the pattern's heuristics break down.
6. **Related work** — adjacent diagnostic tools in the agent ecosystem.
7. **Future work** — what we'd build next (deeper modes, framework adapters, etc.).

This outline isn't an actual paper — it's the spec for one. When we go to publish, the essay + the spec + the existing CITATIONS.md become the paper draft.

## Citations

- <Citation 1>
- <Citation 2>
- <Citation 3>

(Mirror this list against the pattern's `lib/CITATIONS.md` to keep them in sync.)

## Try it yourself

Three-line snippet that the reader can paste:

```bash
pip install 'valanistack[anthropic]'
vstack-<pattern> analyze --trace <example>.json --mode standard
```

End with a one-sentence "if this surfaced something, run X next" hook back into the composition chain.
