# vstack — narrative essays

The 5th layer of vstack's pattern shape: a Substack-ready essay per pattern. Each essay drafts the pattern, the failure mode it addresses, and the underlying organizational-behavior theory, with a paper outline at the end.

## What ships now

- `_TEMPLATE.md` — the canonical essay structure. All 34 essays follow it.
- `01-lewin.md`, `17-lencioni.md`, `20-edmondson-psych-safety.md`, `30-aar.md`, `31-schein.md`, `34-span-of-control.md` — six anchor essays covering the most-trafficked patterns. They establish the voice + level of depth for the rest.

The remaining 28 essays are the next quality bar to ship — see `PATTERNS.md` for which patterns are missing essays. The pattern is documented + implemented + demoed + benchmarked; the essay is the cherry on top.

## Voice + length target

- 1500-3000 words.
- One pattern per essay.
- Lead with the *agent failure* the pattern catches, not the OB literature. The literature is the deepening pass, not the hook.
- Always include: opening anecdote, what the pattern detects, how the analyzer works (1-2 paragraphs of pseudo-code), citations, comparison to adjacent patterns, paper outline.

## How essays connect to the rest of vstack

Each essay's filename matches the pattern's number + import_name. The MCP `vstack://patterns/<name>/citations` resource gives the academic anchors; the essay is the *narrative* on top of those anchors, written for an engineering audience.

Once an essay is publication-ready, the workflow is:

1. Post on Substack (or whichever venue we're targeting that week).
2. Add the published URL to the pattern's `CITATIONS.md` under a "Vstack essay" heading.
3. Cross-link from the docs site at `docs/patterns/<module>.md`.

The full 10-venue paper-publication plan lives in the private City Valani repo under `vstack/SPINOFF-01-TMLR.md` through `vstack/SPINOFF-10-ICLR-BLOG-TRACK.md`.
