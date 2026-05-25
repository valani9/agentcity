# Security model

vstack's security model has three concentric rings.

## Ring 1 — Library code (always-on)

These guards are unconditional. Every consumer (Python library, CLI, MCP, REST, framework adapters) goes through them.

- **Prompt-injection detection.** Free-text fields (`task`, `goal`, `outcome`, etc.) are passed through `vstack.aar.detect_injection` before they reach an LLM prompt. Suspicious inputs are logged + heuristically flagged but not rejected — the detector is best-effort and the more important defense is the pattern's own prompt-fencing.
- **Prompt fencing.** Every analyzer wraps user-supplied trace content in `<user-input>...</user-input>` fences via `vstack.aar.fence` so injected instructions can't escape into the system-prompt context.
- **Pattern-name validation.** Any path that takes a user-supplied pattern name (baselines, learnings, MCP tool dispatch) runs it through `vstack.security.safe_pattern_name` which rejects anything outside `[A-Za-z0-9_-]+`. Prevents path-traversal via attacker-controlled tool / pattern names.
- **Path containment.** User-supplied paths (baseline JSON, suite JSON, install destinations) are checked with `vstack.security.safe_path(must_be_under=...)` against the configured root.
- **No `shell=True`.** Every subprocess call (gbrain, chrome-devtools-mcp) uses explicit argv lists. `vstack.security.safe_subprocess_argv` validates the argv before execution.

## Ring 2 — REST API (configurable)

These guards are opt-in but production-recommended. The REST API ships them off by default to preserve local-dev ergonomics; enable them when binding past loopback.

- **API-key auth.** Set `VSTACK_API_KEYS=...` + `VSTACK_API_REQUIRE_AUTH=true`. Keys are SHA-256-hashed in memory; comparisons are constant-time (`hmac.compare_digest`).
- **Rate limiting.** Set `VSTACK_API_RATE_LIMIT="100/60"` for 100 req per 60s per API-key (or per X-Forwarded-For IP if no key). Returns `429` with `Retry-After`.
- **Request size limits.** `VSTACK_API_MAX_BODY_BYTES` / `MAX_TRACE_STEPS` / `MAX_STRING_CHARS` / `MAX_TOTAL_CHARS` enforced before the trace reaches Pydantic, so a malicious client can't OOM the server with one POST.
- **Request timeout.** `VSTACK_API_REQUEST_TIMEOUT=120` (seconds). Forensic mode of some patterns can exceed this; the server surfaces a `504 timeout` and the client can retry in quick mode.
- **Security headers.** Every response carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `Referrer-Policy: strict-origin-when-cross-origin`. HSTS is added when served over HTTPS.
- **CORS.** Off by default. Configure with `VSTACK_API_CORS_ORIGINS=https://app.example.com,https://staging.example.com`. Credentials never sent.

## Ring 3 — Deployment (your responsibility)

vstack can't enforce these — they're the network + infrastructure layer above the application.

- **TLS termination.** Use a reverse proxy (nginx / Caddy / a managed Load Balancer). Don't expose the FastAPI app directly to the public internet on cleartext HTTP.
- **Secrets management.** Never bake `ANTHROPIC_API_KEY` / `VSTACK_API_KEYS` into a Docker image. Use the deployment platform's secret store (K8s Secrets, AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault).
- **Network isolation.** The MCP server (stdio) is process-local; the REST API benefits from a private subnet + a security-group allowlist.
- **Audit logging.** Pipe stdout / stderr to your logging backend. Every request carries an `X-Request-ID` for correlation.
- **Dependency hygiene.** vstack's CI runs `bandit` on every commit + `pip-audit` on every install. Run these in your own CI too.

## Threat model

We design for these adversaries:

1. **Untrusted trace content.** An attacker controls the trace fields (e.g. a bug-reporter pasted malicious content into a UI that calls vstack). Defended by Ring 1 (prompt fencing + injection detection + length caps).
2. **Untrusted API caller (no key).** Someone hits the public IP of your `vstack-api`. Defended by Ring 2 (auth, rate limit, request size caps) + Ring 3 (TLS, network ACLs).
3. **Untrusted API caller (valid key, abusive volume).** A legitimate API-key holder runs traffic high enough to deny service to others. Defended by per-key rate limiting + per-request timeout.
4. **Compromised dependency.** A transitive `pip` dep gets a malicious update. Defended by `pip-audit` in CI + `bandit` on first-party code; PyPI Trusted Publisher OIDC means our releases are tied to a specific GitHub workflow run.

We do NOT design for:

- **Attacks against the LLM provider itself.** That's the provider's job; we surface their errors and pass through their auth.
- **Side-channel attacks on the cache layer.** Cache keys are hashes of full canonical traces; there's no useful timing oracle for an attacker without a valid API key + matching trace.
- **Adversarial machine-learning attacks against the diagnostic analyzers.** The analyzers are LLM-driven; if a sophisticated attacker is able to manipulate the LLM's output by carefully crafting the input trace, that's a property of the LLM, not vstack's code.

## Security audit posture

- Every commit gates on `bandit` over the first-party `lib/` dirs.
- `pip-audit` runs in CI as an informational warn-only step (transitive vulns in framework adapter dep trees can't be unilaterally patched by vstack; report-only is correct).
- The `vstack-doctor` CLI surfaces real-time misconfiguration (auth-on-without-keys is an ERROR-level finding).
- No CVEs in first-party vstack code as of v0.6.0.

## Reporting a vulnerability

See [SECURITY.md](https://github.com/valani9/vstack/blob/main/SECURITY.md) at the repo root. Short version: email `valani@bu.edu` with the subject "VSTACK-SECURITY"; don't open a public issue.
