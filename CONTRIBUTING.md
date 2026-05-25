# Contributing to vstack

Thanks for wanting to make vstack better.

This guide is short because contributing should be easy. If something here is unclear, that's a bug in this guide — please open an issue.

## The 60-second on-ramp

```bash
git clone https://github.com/valani9/vstack.git
cd vstack
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,all]"
vstack-doctor                       # confirms your dev install works
pytest -q                           # 2,097 tests should pass in ~4 seconds
```

That's it. You're ready to edit code, write a pattern, or fix a bug.

## What's most useful

Ranked by impact, lowest barrier first:

| Contribution | Why it matters | Effort |
|---|---|---|
| **Bug reports with `vstack-doctor` output** | Catches real install issues we can fix in one PR | 5 min |
| **Real failure traces** that map onto a pattern | Synthetic traces miss things; real ones don't | 10 min |
| **Docs improvements + typo fixes** | Every doc page that gets clearer pays compounding interest | varies |
| **A new framework adapter** (Mastra, Strands, Smolagents) | New users of that framework get vstack for free | 1–2 hours |
| **A public-benchmark eval** for an existing pattern | Patterns without public evals have no public credibility loop | 2–4 hours |
| **A new OB-anchored pattern** (rare — most are shipped) | Extends the literature mapping; must cite a named source | 1–2 days |
| **An essay** that uses or extends a pattern | The essays compound the library's reach | varies |

## How to add a new pattern

Each pattern ships **five layers**:

1. **README** — what the framework is, the citation, the failure mode it addresses, the proposed intervention
2. **Python library** — the runnable code, under `module-N-<scope>/<NN>-<pattern>/lib/`
3. **Runnable demo** — a working example on at least one major agent framework
4. **Public-benchmark eval** — a comparison on GAIA, SWE-Bench-multi, AppWorld, AgentBench, or equivalent
5. **Essay** — a Substack-ready write-up of the pattern + its OB anchor

If any of those five is missing, the pattern is half-shipped. Half-shipped patterns dilute the bar.

Open an issue with the [feature-request template](.github/ISSUE_TEMPLATE/feature_request.yml) before writing code — we'll align on whether the framework anchor fits.

## Code style

**Python** — 3.11+ · `ruff format` · `ruff check` · `mypy --strict` · `pytest`

```bash
ruff format .
ruff check .
mypy <touched-lib-dir> --strict --ignore-missing-imports
pytest <touched-dir> -q
```

The mypy command runs **per-pattern** because each pattern's `lib/` is its own logical package (via the force-include build map). Running mypy across all patterns at once hits a "Duplicate module named `lib`" error.

**Comments** — default to none. Comment only when *why* is non-obvious (a workaround, an invariant, a constraint a future reader would miss).

## API stability promise

Every published pattern exposes its public surface via `__all__` in its package's `__init__.py`. The promise:

- **`0.x.y` releases** — breaking changes allowed in `minor` bumps (`0.x` → `0.(x+1)`). Patch bumps (`0.x.y` → `0.x.(y+1)`) are non-breaking.
- **`1.x.y` and later** — strict SemVer. Breaking changes only on `major` bumps, and only after at least one `minor` release where the API was marked deprecated and emitted `DeprecationWarning`.

Symbols not listed in `__all__` are private. Importing them from a sub-package is supported on a best-effort basis and may change between any two releases.

## Production-readiness checklist for new patterns

Patterns merged after `0.1.0` should:

1. Use `vstack.aar.get_logger(...)` (not `logging.getLogger(...)`) so log lines carry the run-id correlation field.
2. Wrap the body of `run(...)` in `with run_context(new_run_id(), pattern="<pkg_name>"):`.
3. Call `record_llm_call(...)` after each successful LLM completion with model, token counts (from `client.last_usage`), and `elapsed_ms` (via `time_call()`).
4. Pass any free-text input from outside the application boundary through `sanitize_for_prompt` before string-formatting it into a prompt template.
5. Ship a stub-client micro-benchmark in `benchmarks/_perf/patterns/<pattern>.py` so the perf regression harness can detect performance regressions.

These are recommendations, not blockers. Existing patterns are being migrated incrementally — contributors welcome to migrate any.

## How to add a framework adapter

Adapters live in `_adapters/lib/<framework>.py`. Each adapter exposes the same shape:

```python
from vstack.registry import all_patterns

def as_<framework>_tools(*, mode: str = "standard") -> list:
    """Return every vstack pattern wrapped as a native <framework> tool."""
    ...
```

Look at `_adapters/lib/langchain.py` as the canonical example — every other adapter mirrors its shape.

Then:

```bash
# Add the framework's lib to the optional-deps in pyproject.toml
# Add a test in _adapters/tests/test_<framework>.py
pytest _adapters/ -q
mypy _adapters/lib --strict --ignore-missing-imports
```

Open a PR. The CI matrix already covers Python 3.11–3.13 on Linux + macOS.

## What we won't accept

- **Patterns without a named OB-literature anchor.** vstack is specifically the OB-literature-anchored layer. Pure design-pattern proposals belong in projects like [Architecting Agentic Communities Using Design Patterns](https://arxiv.org/abs/2601.03624).
- **Half-shipped patterns** (missing any of the five layers). Better one well-shipped pattern than five half-shipped ones.
- **University course internals** (slides, exercises, solutions). The library uses public OB-literature concepts only.
- **Mocked tests where integration tests are needed.** Patterns that touch the LLM client or the file store get real integration tests against the stub LLM + a temp dir.

## Releasing

vstack uses tag-based releases. Process:

1. Bump `pyproject.toml` `version` **and** `_packaging/vstack/__init__.py` `__version__` together. The release-workflow smoke test verifies they match.
2. Update `CHANGELOG.md` with a new `## [X.Y.Z] — YYYY-MM-DD` section.
3. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. The Release workflow builds the wheel, publishes to PyPI via Trusted Publisher (OIDC), and creates a GitHub Release with the changelog section rendered into the body.
5. The Docker workflow (`workflow_run` on Release) builds + pushes multi-arch images to GHCR.

If anything in the release flow surprises you, see [`.github/workflows/release.yml`](.github/workflows/release.yml) — it's the source of truth.

## Where to ask

- **Bugs** → [open an issue](https://github.com/valani9/vstack/issues/new/choose) with the bug-report template.
- **Feature requests** → the feature-request template.
- **Usage questions** → the question template (often gets a faster answer than email).
- **Security disclosures** → please use [GitHub Security Advisories](https://github.com/valani9/vstack/security/policy) — not public issues.

## Code of conduct

Be kind. Disagree with code, not people. Cite your sources. If you're not sure whether something is appropriate, ask.

---

vstack is MIT-licensed and will stay that way. By contributing, you agree your changes ship under the same license.
