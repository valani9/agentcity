# Contributing to vstack

vstack ships curated organizational-behavior patterns for AI agents. Each pattern is anchored in named OB literature and shipped with five layers: README + working library + runnable demo + benchmark + Substack-ready essay.

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

Each pattern needs adapters for the major agent frameworks (Claude Agent SDK, LangGraph, OpenAI Agents SDK, CrewAI, AutoGen, Microsoft Agent Framework, Mastra). If you maintain or contribute to one of these frameworks and want to add the canonical adapter for vstack patterns, please do. Adapters live in `frameworks/<framework-name>/`.

## Benchmarks

Public benchmarks are the credibility loop. If you have a public agent-failure dataset or you'd like to run a pattern against your private corpus and report results, open an issue.

## Essays and citations

Every pattern ships with a Substack-ready essay (`essay.md`). If you write an essay that uses one of the patterns or extends one, please add a link to your essay in the pattern's README under a "Community essays" section. The goal is to compound the literature.

## What we will not accept

- Pattern proposals that don't anchor in named OB literature. vstack is specifically the OB-literature-anchored layer; pure design-pattern proposals belong in projects like [Architecting Agentic Communities Using Design Patterns](https://arxiv.org/abs/2601.03624).
- Implementations that don't ship all five layers (README + lib + demo + benchmark + essay). Half-shipped patterns dilute the library's quality bar. Better one well-shipped pattern than five half-shipped ones.
- Contributions of any university course's internal materials (slides, exercises, solutions). The library uses public OB-literature concepts only.

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

## Development workflow

Set up a working environment from a clean clone:

```bash
git clone https://github.com/valani9/vstack.git
cd vstack
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,all]"
pre-commit install   # optional but recommended
```

Run the full validation suite before opening a PR:

```bash
pytest module-1-individual/ module-2-team/ module-3-organization/ -q
ruff check module-1-individual/ module-2-team/ module-3-organization/
ruff format --check module-1-individual/ module-2-team/ module-3-organization/
# mypy per-pattern (avoids "Duplicate module named lib" across patterns)
for p in module-1-individual/* module-2-team/* module-3-organization/*; do
  [ -d "$p/lib" ] && mypy "$p/lib" --strict --ignore-missing-imports || true
done
python -m build && pip install --force-reinstall --no-deps dist/vstack-*.whl
```

## API stability promise

Every published pattern exposes its public surface via `__all__` in its
package's `__init__.py`. Symbols listed there follow this stability
promise:

- **`0.x.y` releases** — breaking changes are permitted in `minor`
  bumps (`0.0.x` → `0.1.0`). Patch bumps (`0.x.y` → `0.x.(y+1)`)
  are non-breaking. Breaking changes are always documented in
  [CHANGELOG.md](CHANGELOG.md).
- **`1.x.y` and later** — strict SemVer. Breaking changes only on a
  `major` bump, and only after at least one `minor` release where
  the API was marked deprecated and emitted a `DeprecationWarning`.

Symbols not listed in `__all__` are private. Importing them from a
sub-package is supported only on a best-effort basis and may change
between any two releases — please open an issue if you need a private
symbol promoted to the public surface.

## Production-readiness checklist for new patterns

In addition to the existing 5-layer requirement (README + lib + demo +
benchmark + essay), patterns merged after `0.1.0` should:

1. Use `vstack.aar.get_logger(...)` rather than
   `logging.getLogger(...)` so log lines carry the run-id correlation
   field.
2. Wrap the body of `run(...)` (or equivalent entry point) in
   `with run_context(new_run_id(), pattern="<pkg_name>"):`.
3. Call `record_llm_call(...)` after each successful LLM completion
   with the model, token counts (from `client.last_usage`), and
   elapsed_ms (via `time_call()`).
4. Pass any free-text input from outside the application boundary
   through `sanitize_for_prompt` before string-formatting it into a
   prompt template.
5. Ship a stub-client micro-benchmark in
   `benchmarks/_perf/patterns/<pattern>.py` so the perf regression
   harness can detect performance regressions on the deterministic
   parts of the pipeline.

These are recommendations, not blockers. Existing patterns are being
migrated incrementally and contributors are welcome to migrate any
they touch.

## License

By contributing, you agree your contribution will be licensed under the MIT license used by the rest of the project.
