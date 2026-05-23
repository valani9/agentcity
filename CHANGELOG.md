# Changelog

All notable changes to AgentCity are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/) from
`1.0.0` onward. During the `0.x` series, minor bumps may include
breaking changes (see API stability promise in `agentcity/__init__.py`).

## [0.1.0] — 2026-05-23

First production-ready release. All 34 patterns from the roadmap ship at
the 5-layer quality bar (README + library + demo + benchmark + essay).

### Added — top-level package

- `agentcity.__version__` is now defined at the namespace root.
- `py.typed` marker ships in the wheel — downstream consumers now pick
  up the library's type hints by default.
- API stability promise documented in the top-level package docstring.

### Added — shared production-grade infrastructure (`agentcity.aar.*`)

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
- `agentcity.aar.__version__` synced to `0.1.0`.
- Documentation updated to reflect the production-readiness layer.

### Compatibility

All existing public APIs from `0.0.14` continue to work unchanged.
The new infrastructure modules are purely additive — patterns that
do not adopt structured logging, telemetry, or input guards still
function exactly as they did in `0.0.14`.

## [0.0.14] — 2026-05-22

Closing batch. Patterns #04, #05, #07, #12 ship — completing the
34-pattern roadmap.

- `agentcity.danva_emotion` (#04) — DANVA-style emotion-recognition
  diagnostic. Per-emotion accuracy + intensity calibration + confusion
  patterns computed deterministically; LLM contributes only
  interventions.
- `agentcity.cognitive_reappraisal` (#05) — Gross's reappraisal vs
  suppression vs rumination vs avoidance vs expression classifier with
  two LLM passes (strategy detection + interventions).
- `agentcity.hexaco` (#07) — Lee & Ashton 6-factor personality fit
  diagnostic. H-factor (honesty-humility) risk reported separately
  from overall fit.
- `agentcity.vroom_expectancy` (#12) — Victor Vroom's
  Expectancy × Instrumentality × Valence motivation calculus. Product
  computed deterministically in Python; LLM cannot override the math.

## [0.0.13] — 2026-05-22

- `agentcity.goleman_ei` (#02) — Goleman's 2×2 emotional-intelligence
  diagnostic (self × other × recognition × regulation).
- `agentcity.sdt_reward` (#10) — Self-Determination Theory intrinsic
  reward diagnostic (autonomy, competence, relatedness).
- `agentcity.span_of_control` (#34) — six deterministic
  org-structure metrics computed in Python (max_span, mean_span,
  centralization_index, hierarchy_depth, span_gini,
  decision_bottleneck).

## [0.0.12] — 2026-05-22

- `agentcity.org_structure` (#33) — six-dimensional org structure
  matrix + archetype classifier.
- `agentcity.motivation_traps` (#09) — Saxberg's four motivation
  traps (values, self_efficacy, emotions, attribution).
- `agentcity.glaser_conversation` (#21) — conversational-intelligence
  steering across three states × three levels.

## [0.0.11 and earlier]

See git history for v0.0.11 and prior batches. Roadmap kickoff at
`v0.0.1` with pattern #30 (AAR generator); v0.0.2–v0.0.11 shipped
patterns #17, #18, #03, #13, #27, #20, #29, #22, #28, #01, #19, #15,
#26, #14, #24, #11, #25, #31, #08, #23, #32, #16, #06 incrementally.

[0.1.0]: https://github.com/valani9/AgentCity/releases/tag/v0.1.0
[0.0.14]: https://github.com/valani9/AgentCity/releases/tag/v0.0.14
[0.0.13]: https://github.com/valani9/AgentCity/releases/tag/v0.0.13
[0.0.12]: https://github.com/valani9/AgentCity/releases/tag/v0.0.12
