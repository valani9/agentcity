# Changelog

All notable changes to vstack are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/) from
`1.0.0` onward. During the `0.x` series, minor bumps may include
breaking changes (see API stability promise in `vstack/__init__.py`).

## [0.3.0] — 2026-05-25

Phase 1 of the expansion roadmap is complete. v0.3.0 lands four additional
invocation surfaces alongside the v0.2.0 MCP server, plus the persistent
local state store everything else can build on.

### Added — `vstack.memory` + `vstack-config` CLI

- New ``~/.vstack/`` home directory with subdirs for ``baselines/``,
  ``sessions/``, ``analytics/``. Override via the ``VSTACK_HOME`` env var.
- ``vstack-config`` CLI: ``get`` / ``set`` / ``list`` / ``unset`` / ``path``
  / ``keys`` / ``install-skills`` subcommands.
- 8 documented preference keys (default_mode, default_model, telemetry,
  log_level, preferred_llm, api_host, api_port, skills_install_path).
- Helpers exposed for downstream callers:
  ``baseline_path_for(name)``, ``get_baselines_dir()``,
  ``load_config()`` / ``save_config()``.

### Added — `vstack.upgrade` + `vstack-upgrade` CLI

- Hits the PyPI JSON index for ``valanistack``, picks the highest stable
  version (or pre-release if ``--allow-prereleases``), compares against
  the runtime ``vstack.__version__``, and prints the matching
  CHANGELOG.md section as migration notes. Never execs pip; the user
  runs the printed install command.
- ``--json`` for machine-readable output, ``--quiet`` for CI.
- 19 new tests; HTTP is mocked at the ``urllib.request`` boundary so
  CI never touches PyPI.

### Added — `vstack.api` + `vstack-api` CLI (FastAPI)

- HTTP surface for every pattern. Endpoints: ``/healthz``,
  ``/v1/patterns``, ``/v1/patterns/{name}`` (+ playbooks / citations /
  composition subpaths), ``/v1/analyze/{name}`` (POST). Accepts the
  trace either flat or wrapped in ``{trace, mode, model}``.
- FastAPI auto-generates the OpenAPI spec under ``/openapi.json`` and
  serves Swagger UI at ``/docs``.
- ``vstack-api`` CLI: ``serve`` (default), ``routes``, ``openapi``.
- New optional extra ``valanistack[api]`` (pulls FastAPI + uvicorn).
- 13 new tests via FastAPI's TestClient.

### Added — Docker (`ghcr.io/valani9/vstack`)

- ``Dockerfile`` at the repo root installs ``valanistack[all]``,
  sets ``VSTACK_HOME=/var/lib/vstack``, drops to a non-root user, and
  defaults ``CMD`` to ``vstack-mcp serve``. tini as PID 1 for clean
  signal handling.
- New ``.github/workflows/docker.yml`` builds multi-arch
  (linux/amd64 + linux/arm64) on every ``v*`` tag, publishes to GHCR
  with semver tags + ``latest``, generates SBOM + provenance
  attestations.

### Added — Claude Code skills (`_skills/`)

- 7 task-shaped SKILL.md essays: ``/vstack`` (meta router),
  ``/vstack-pick-pattern`` (interview), ``/vstack-post-incident``
  (AAR + Lewin + downstream chain), ``/vstack-audit-crew`` (5-pattern
  crew health), ``/vstack-bottleneck`` (Span + Structure + behavioral),
  ``/vstack-culture-check`` (Schein + Robbins + optional McGregor),
  ``/vstack-baseline`` (calibration roundtrip).
- Skills are *task-shaped*, not pattern-direct — each one composes
  multiple patterns into a real workflow.
- One-command install via ``vstack-config install-skills``.

### Added — CLIs

- ``vstack-mcp``, ``vstack-api``, ``vstack-config``, ``vstack-upgrade``
  all registered in ``[project.scripts]``. Together with the 34
  per-pattern CLIs from v0.1.0, every pattern + every surface is one
  command away.

### Tests

- ``_memory/tests/`` (16), ``_upgrade/tests/`` (19), ``_api/tests/`` (13)
  bring the suite to **1,811 passing** (up from 1,756 in v0.2.0).
- CI mypy loop extended with ``_memory``, ``_upgrade``, ``_api``;
  CI lint + test job paths extended to include the new surface dirs.
- Release smoke test now also imports ``vstack.mcp``, ``vstack.memory``,
  ``vstack.upgrade``, ``vstack.api`` to guard against force-include
  drift.

## [0.2.0] — 2026-05-25

First non-CLI invocation surface. vstack can now be driven from any
MCP-compatible client (Claude Desktop, Cursor, Cline, Continue,
ChatGPT, OpenAI Assistants, and the rest of the MCP ecosystem) in
addition to direct Python imports and per-pattern CLIs.

### Added — `vstack.mcp` (MCP server)

- **`vstack-mcp` CLI** — `vstack-mcp serve` runs a local stdio MCP
  server. Zero hosting cost: the user's MCP client spawns the server
  as a subprocess, exchanges JSON-RPC over stdin/stdout, and never
  reaches a network socket.
- **34 tools, one per pattern** — `vstack_lewin`, `vstack_aar`,
  `vstack_schein_culture`, `vstack_span_of_control`, etc. Each tool's
  input schema is the pattern's Pydantic input model merged with two
  optional top-level params (`mode`, `model`); each tool's output is
  the pattern's detection model serialized to JSON.
- **Resources** — `vstack://patterns/index` lists every registered
  pattern; `vstack://patterns/<name>/citations` exposes the per-
  pattern `CITATIONS.md`; `vstack://patterns/<name>/playbooks`
  exposes the failure-mode playbooks dict;
  `vstack://patterns/<name>/composition` exposes the cross-pattern
  handoff manifest.
- **Prompts** — `vstack_pick_pattern` is a meta routing prompt that
  takes a free-form problem description and recommends the right
  pattern + tool call. Each pattern also gets a
  `vstack_<name>_invoke` template (35 prompts total).
- **LLM client resolution** — env-var-driven: prefer Anthropic if
  `ANTHROPIC_API_KEY` is set, else OpenAI, else Ollama. Override
  via `VSTACK_MCP_LLM=anthropic|openai|ollama|stub`. A structured
  error response is returned when no API key is configured; the
  server never crashes silently.
- **Utility subcommands** — `vstack-mcp list-tools`,
  `vstack-mcp list-resources`, `vstack-mcp config-snippet
  {claude-desktop|cursor|cline|continue|generic}` for paste-ready
  client config.

### Added — packaging

- New `[mcp]` optional dependency: `pip install valanistack[mcp]`
  pulls in `mcp>=1.20.0`.
- `valanistack[all]` now also includes the MCP server alongside the
  three LLM-client extras.
- `vstack-mcp` registered as a new `[project.scripts]` entry point.

### Added — tests

- 222 new tests under `_mcp/tests/` exercising registry resolution
  (all 34 patterns introspect cleanly), tool / resource / prompt
  enumeration, full server-handler round-trips, and a stub-LLM
  end-to-end call through the Lewin pattern. Brings the suite total
  to 1,756 passing.

### Repo layout

- New `_mcp/` source folder mirroring the per-pattern `module-*/`
  shape: source in `_mcp/lib/` (force-included as `vstack/mcp/` at
  wheel build time), tests in `_mcp/tests/`. CI's mypy loop now
  includes `_mcp` alongside the 34 patterns.

## [0.1.0] — 2026-05-23

First production-ready release. All 34 patterns from the roadmap ship at
the 5-layer quality bar (README + library + demo + benchmark + essay).

### Added — top-level package

- `vstack.__version__` is now defined at the namespace root.
- `py.typed` marker ships in the wheel — downstream consumers now pick
  up the library's type hints by default.
- API stability promise documented in the top-level package docstring.

### Added — shared production-grade infrastructure (`vstack.aar.*`)

- **Structured logging** with run-id correlation: `new_run_id`,
  `run_context`, `get_logger`, `JsonFormatter`,
  `configure_json_logging`. Patterns can correlate every log line
  from a single diagnostic run via a stable identifier, and ship JSON
  logs to structured backends without per-pattern changes.
- **Token / cost telemetry**: `TelemetrySink` protocol,
  `InMemoryTelemetrySink`, `NullTelemetrySink`, `record_llm_call`,
  `time_call`, `set_default_sink`. Default is off (Null sink); when
  enabled, every LLM call emits an event with model + token counts +
  elapsed_ms + run_id + pattern.
- **Prompt-injection input guards**: `sanitize_for_prompt`,
  `detect_injection`, `fence`. Strip control characters, cap absurd
  field sizes, detect known impersonation phrases, and provide
  unambiguous delimiters for fencing user content inside prompt
  templates.
- **Async LLM client adapters**: `AnthropicAsyncClient`,
  `OpenAIAsyncClient`, `OllamaAsyncClient` — same constructor surface
  as the sync clients, with `async def complete(...)`. Enables
  parallel pattern fan-out in server traffic.
- **Token-usage tracking** on every sync + async client: `last_usage`
  attribute returns an `LLMUsage` dataclass (input/output/total
  tokens + model). Cost layers can read this after each call without
  changing the `complete(...) -> str` return signature.
- **Configurable timeouts** on all real clients
  (`DEFAULT_TIMEOUT_SECONDS = 120.0`). LLM calls can no longer hang
  indefinitely on a stalled provider.

### Added — security, release engineering, and docs

- `SECURITY.md` with vulnerability reporting policy.
- `CHANGELOG.md` (this file).
- Pre-commit hooks config (`.pre-commit-config.yaml`): ruff, ruff
  format, mypy, bandit, pip-audit.
- PyPI release workflow (`.github/workflows/release.yml`) — publishes
  to PyPI on git tag push via trusted publisher.
- CI extended with: bandit security scan, pip-audit dependency scan,
  coverage gate, all-34-namespaces import verification in the build
  job.
- README badges (CI status, PyPI version, Python versions, license).
- `examples/cookbook/` directory with cross-pattern composition
  examples (orchestrator + diagnostic, parallel fan-out, telemetry
  wiring).
- Per-pattern micro-benchmark harness
  (`benchmarks/_perf/run_perf_suite.py`) measuring stub-client
  latency p50/p95 across all 34 patterns for regression detection.

### Changed

- `Development Status` classifier promoted from `2 - Pre-Alpha` to
  `4 - Beta`.
- `Python :: 3.13` classifier added (already covered by CI matrix).
- `vstack.aar.__version__` synced to `0.1.0`.
- Documentation updated to reflect the production-readiness layer.

### Compatibility

All existing public APIs from `0.0.14` continue to work unchanged.
The new infrastructure modules are purely additive — patterns that
do not adopt structured logging, telemetry, or input guards still
function exactly as they did in `0.0.14`.

## [0.0.14] — 2026-05-22

Closing batch. Patterns #04, #05, #07, #12 ship — completing the
34-pattern roadmap.

- `vstack.danva_emotion` (#04) — DANVA-style emotion-recognition
  diagnostic. Per-emotion accuracy + intensity calibration + confusion
  patterns computed deterministically; LLM contributes only
  interventions.
- `vstack.cognitive_reappraisal` (#05) — Gross's reappraisal vs
  suppression vs rumination vs avoidance vs expression classifier with
  two LLM passes (strategy detection + interventions).
- `vstack.hexaco` (#07) — Lee & Ashton 6-factor personality fit
  diagnostic. H-factor (honesty-humility) risk reported separately
  from overall fit.
- `vstack.vroom_expectancy` (#12) — Victor Vroom's
  Expectancy × Instrumentality × Valence motivation calculus. Product
  computed deterministically in Python; LLM cannot override the math.

## [0.0.13] — 2026-05-22

- `vstack.goleman_ei` (#02) — Goleman's 2×2 emotional-intelligence
  diagnostic (self × other × recognition × regulation).
- `vstack.sdt_reward` (#10) — Self-Determination Theory intrinsic
  reward diagnostic (autonomy, competence, relatedness).
- `vstack.span_of_control` (#34) — six deterministic
  org-structure metrics computed in Python (max_span, mean_span,
  centralization_index, hierarchy_depth, span_gini,
  decision_bottleneck).

## [0.0.12] — 2026-05-22

- `vstack.org_structure` (#33) — six-dimensional org structure
  matrix + archetype classifier.
- `vstack.motivation_traps` (#09) — Saxberg's four motivation
  traps (values, self_efficacy, emotions, attribution).
- `vstack.glaser_conversation` (#21) — conversational-intelligence
  steering across three states × three levels.

## [0.0.11 and earlier]

See git history for v0.0.11 and prior batches. Roadmap kickoff at
`v0.0.1` with pattern #30 (AAR generator); v0.0.2–v0.0.11 shipped
patterns #17, #18, #03, #13, #27, #20, #29, #22, #28, #01, #19, #15,
#26, #14, #24, #11, #25, #31, #08, #23, #32, #16, #06 incrementally.

[0.1.0]: https://github.com/valani9/vstack/releases/tag/v0.1.0
[0.0.14]: https://github.com/valani9/vstack/releases/tag/v0.0.14
[0.0.13]: https://github.com/valani9/vstack/releases/tag/v0.0.13
[0.0.12]: https://github.com/valani9/vstack/releases/tag/v0.0.12
