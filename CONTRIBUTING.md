# Contributing to AgentCity

AgentCity ships curated organizational-behavior patterns for AI agents. Each pattern is anchored in named OB literature and shipped with five layers: README + working library + runnable demo + benchmark + Substack-ready essay.

If you want to contribute, the highest-leverage things are:

## Real failure traces

If you ship production AI agents and have a failure trace that maps onto one of the patterns in [PATTERNS.md](PATTERNS.md), open an issue with the failure description and we'll work together on whether the pattern's library code handles it well. Real failures > synthetic.

## New pattern proposals

The pattern library is finite (34 planned) but extensible. If you find an OB framework not yet in the index that maps cleanly to a real agent failure mode, open an issue with:

1. The OB framework + primary academic citation.
2. The named agent failure mode it addresses.
3. A concrete example of the failure.
4. A proposed intervention.

If the proposal is accepted, you can either implement the pattern yourself (PR welcome) or it gets added to the planned roadmap.

## Framework integrations

Each pattern needs adapters for the major agent frameworks (Claude Agent SDK, LangGraph, OpenAI Agents SDK, CrewAI, AutoGen, Microsoft Agent Framework, Mastra). If you maintain or contribute to one of these frameworks and want to add the canonical adapter for AgentCity patterns, please do. Adapters live in `frameworks/<framework-name>/`.

## Benchmarks

Public benchmarks are the credibility loop. If you have a public agent-failure dataset or you'd like to run a pattern against your private corpus and report results, open an issue.

## Essays and citations

Every pattern ships with a Substack-ready essay (`essay.md`). If you write an essay that uses one of the patterns or extends one, please add a link to your essay in the pattern's README under a "Community essays" section. The goal is to compound the literature.

## What we will not accept

- Pattern proposals that don't anchor in named OB literature. AgentCity is specifically the OB-literature-anchored layer; pure design-pattern proposals belong in projects like [Architecting Agentic Communities Using Design Patterns](https://arxiv.org/abs/2601.03624).
- Implementations that don't ship all five layers (README + lib + demo + benchmark + essay). Half-shipped patterns dilute the library's quality bar. Better one well-shipped pattern than five half-shipped ones.
- Contributions of MO221 course-internal materials (slides, exercises, solutions). The library uses public OB-literature concepts only.

## Code style

Python:
- Python 3.11+
- `ruff` for formatting (line length 100, double quotes)
- `mypy` strict
- `pytest` for tests

TypeScript:
- ESM only
- `tsc --strict`
- `prettier` for formatting
- `vitest` for tests

## License

By contributing, you agree your contribution will be licensed under the MIT license used by the rest of the project.
