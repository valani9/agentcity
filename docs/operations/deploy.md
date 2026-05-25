# Production deploy guide

This page captures everything you need to run `vstack-api` and `vstack-mcp` in production for thousands of concurrent users. Each section corresponds to one concrete decision; the defaults are safe but conservative — read once before going live, then revisit when scale demands.

## TL;DR — minimum production checklist

- [ ] Bind `vstack-api` to a loopback or private interface, not 0.0.0.0 directly. Front it with a reverse proxy (nginx / Caddy / Cloud Load Balancer) that terminates TLS.
- [ ] Set `VSTACK_API_KEYS` (or `VSTACK_API_KEYS_FILE`) **and** `VSTACK_API_REQUIRE_AUTH=true` before exposing anything beyond localhost.
- [ ] Set `VSTACK_API_RATE_LIMIT=100/60` (or whatever per-key quota matches your usage).
- [ ] Set `VSTACK_API_MAX_BODY_BYTES=2097152` (2 MiB) unless your traces genuinely exceed this — defaults to 5 MiB which is fine but tighter is safer.
- [ ] Set `VSTACK_CACHE=memory` for the cost win when the same trace is replayed across patterns / modes.
- [ ] Configure `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY` / `OLLAMA_HOST`).
- [ ] Scrape `/metrics` into Prometheus; alert on `vstack_requests_total{status!="ok"}` and the `vstack_request_duration_seconds` p99.
- [ ] Mount a persistent volume for `~/.vstack/` if you want baselines / learnings / telemetry across restarts.
- [ ] Run `vstack-doctor --skip-network` in your container build to catch misconfiguration before deploy.

## Recommended deploy shapes

### Shape A — single container behind a reverse proxy

Best for low-volume, single-tenant production. The Docker image ships everything.

```bash
docker run -d --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -e VSTACK_API_REQUIRE_AUTH=true \
  -e VSTACK_API_KEYS="prod=$(openssl rand -hex 24)" \
  -e VSTACK_API_RATE_LIMIT=100/60 \
  -e VSTACK_CACHE=memory \
  -e VSTACK_HOME=/var/lib/vstack \
  -v vstack-data:/var/lib/vstack \
  ghcr.io/valani9/vstack:0.6.0 \
  vstack-api serve --host 0.0.0.0 --port 8000
```

Front with nginx terminating TLS:

```nginx
server {
    listen 443 ssl http2;
    server_name vstack.example.com;
    ssl_certificate     /etc/letsencrypt/live/vstack.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vstack.example.com/privkey.pem;

    client_max_body_size 5m;
    proxy_read_timeout 180s;
    proxy_send_timeout 180s;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The `X-Forwarded-For` header is what the rate limiter uses to per-IP-attribute requests that don't carry an API key (auth path covers the API-key case directly).

### Shape B — multi-replica behind Kubernetes

For real concurrency. The image is multi-arch (amd64 + arm64) and the API is stateless (in-memory cache, in-memory rate limiter, in-memory metrics). Scale horizontally by replica count; each replica has its own cache (small price for simplicity — switch to Redis if you outgrow it).

Sample Deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vstack-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: vstack-api
  template:
    metadata:
      labels:
        app: vstack-api
    spec:
      containers:
      - name: api
        image: ghcr.io/valani9/vstack:0.6.0
        command: ["vstack-api", "serve", "--host", "0.0.0.0", "--port", "8000"]
        ports: [{containerPort: 8000}]
        env:
        - {name: VSTACK_API_REQUIRE_AUTH, value: "true"}
        - {name: VSTACK_API_RATE_LIMIT, value: "200/60"}
        - {name: VSTACK_API_KEYS, valueFrom: {secretKeyRef: {name: vstack-api, key: keys}}}
        - {name: ANTHROPIC_API_KEY, valueFrom: {secretKeyRef: {name: anthropic, key: api-key}}}
        - {name: VSTACK_CACHE, value: "memory"}
        - {name: VSTACK_HOME, value: "/var/lib/vstack"}
        resources:
          requests: {cpu: "100m", memory: "256Mi"}
          limits:   {cpu: "1",    memory: "1Gi"}
        readinessProbe:
          httpGet: {path: /readyz, port: 8000}
          periodSeconds: 5
        livenessProbe:
          httpGet: {path: /livez,  port: 8000}
          periodSeconds: 15
        volumeMounts:
        - {name: home, mountPath: /var/lib/vstack}
      volumes:
      - name: home
        emptyDir: {}     # or PersistentVolumeClaim if baselines + learnings need to survive restarts
```

Service + Ingress are standard. `/healthz`, `/livez`, `/readyz` are wired to K8s probe semantics (liveness vs. readiness vs. startup).

## Authentication

The API is loopback-friendly by default — local dev needs zero auth config. The moment you expose anything past localhost, enable auth:

```bash
# Generate a fresh strong key:
python -c "import secrets; print(secrets.token_urlsafe(24))"

export VSTACK_API_KEYS="prod=<key>,staging=<other-key>"
export VSTACK_API_REQUIRE_AUTH=true
```

Or via a newline-delimited file:

```bash
export VSTACK_API_KEYS_FILE=/etc/vstack/api-keys
cat > /etc/vstack/api-keys <<EOF
prod=<key1>
staging=<key2>
EOF
chmod 600 /etc/vstack/api-keys
```

Clients send the key as:

- `Authorization: Bearer <key>` (preferred), or
- `X-API-Key: <key>`

Wrong / missing keys get `401 Unauthorized` with `WWW-Authenticate: Bearer realm="vstack"`.

## Rate limiting

The in-memory sliding-window limiter is the default. Configure with:

```bash
VSTACK_API_RATE_LIMIT="100/60"    # 100 requests per 60s per API key (or per IP if no key)
VSTACK_API_RATE_LIMIT="off"       # disable
```

When exceeded the API returns `429 Too Many Requests` with `Retry-After`, `X-RateLimit-Limit`, and `X-RateLimit-Remaining` headers. Successful requests also carry the latter two headers so clients can self-pace.

Health endpoints (`/healthz`, `/readyz`, `/livez`, `/metrics`, `/openapi.json`) are NOT rate-limited — K8s probes hammer them continuously.

For real multi-replica deploys with a global quota, swap the in-memory limiter for a Redis-backed one. The `RateLimiter` protocol in `vstack.security` is the swap point.

## Request size limits

Configure if the defaults don't match your use case:

| Env var | Default | Purpose |
|---|---|---|
| `VSTACK_API_MAX_BODY_BYTES` | 5 MiB | Total POST body. |
| `VSTACK_API_MAX_TRACE_STEPS` | 5,000 | Max length of `steps[]` / `messages[]`. |
| `VSTACK_API_MAX_MESSAGES` | 5,000 | Max multi-agent message log size. |
| `VSTACK_API_MAX_STRING_CHARS` | 200,000 | Per-string char cap. |
| `VSTACK_API_MAX_TOTAL_CHARS` | 1,000,000 | Total free-text char count. |
| `VSTACK_API_REQUEST_TIMEOUT` | 120s | Server-side per-request deadline. |

Tighten these aggressively if your traces are smaller than the defaults. Loose limits + a malicious client = OOM risk.

## Caching

Enable in-memory caching with:

```bash
VSTACK_CACHE=memory
VSTACK_CACHE_CAPACITY=2048
VSTACK_CACHE_TTL_SECONDS=3600       # optional; entries never expire by default
```

The cache key is SHA-256 of `(pattern, mode, model, trace)` canonical JSON. Two identical traces produce one analyzer run + N cache hits. Typical hit rates depend on workload — observability replays of the same trace through multiple patterns benefit; one-off analyses won't.

In a multi-replica deploy, each replica has its own cache. For shared caching, swap `vstack.cache.NullCache` / `InMemoryLRUCache` for a Redis-backed implementation — the `CacheBackend` protocol is the swap point.

## Observability

### Prometheus metrics

`GET /metrics` returns Prometheus text format. Scrape into Prometheus + chart in Grafana:

```yaml
- job_name: vstack-api
  static_configs: [{targets: ["vstack-api.svc.cluster.local:8000"]}]
  metrics_path: /metrics
```

Metrics shipped:

- `vstack_requests_total{surface,pattern,mode,status}` — counter
- `vstack_request_duration_seconds{surface,pattern,mode}` — histogram

Alert suggestions:

- p99 of `vstack_request_duration_seconds` > 30s for >5min (LLM provider degradation)
- `rate(vstack_requests_total{status="analyzer_error"}[5m]) > 0.01` (>1% error rate)
- `rate(vstack_requests_total{status="llm_resolution_error"}[5m]) > 0` (any LLM-key misconfiguration)

### Request IDs

Every response carries an `X-Request-ID`. Clients SHOULD propagate an inbound ID; the server generates a fresh one if absent. The ID is bound to a Python contextvar for the lifetime of the request so every log line during the request carries it.

### Sentry (optional)

Set `SENTRY_DSN` to enable error reporting. No-op if `sentry-sdk` isn't installed.

```bash
pip install sentry-sdk
export SENTRY_DSN="https://...@sentry.io/..."
export SENTRY_ENVIRONMENT=production
```

## Graceful shutdown

The FastAPI lifespan handler flips `/readyz` to `draining` on `SIGTERM`. K8s removes the pod from the Service's endpoints (readiness check fails), then waits for `terminationGracePeriodSeconds` (default 30s) before sending `SIGKILL`. Set it explicitly:

```yaml
spec:
  terminationGracePeriodSeconds: 30
```

Run uvicorn with a matching timeout:

```bash
vstack-api serve --workers 1   # set --workers > 1 only with a shared cache backend
```

## What still lives in-process

- **Cache**: in-memory LRU. Replace with Redis for cross-replica sharing.
- **Rate limiter**: in-memory. Replace with Redis for global quotas.
- **Metrics registry**: in-process. Scrape each replica separately.
- **`~/.vstack/`**: per-replica filesystem. Mount a shared volume for cross-replica baselines / learnings.

All four are pluggable via well-defined protocols (`CacheBackend`, `RateLimiter`, `TelemetrySink`, `LearningStore`). The in-memory defaults are the right choice for single-replica deploys; for true multi-tenancy with shared state, swap them at app-build time:

```python
from vstack.api import build_app
from my_redis_backed_cache import RedisCache

app = build_app(cache=RedisCache(url="redis://..."))
```

## Troubleshooting

Run `vstack-doctor --skip-network` first. It checks 30+ common misconfigurations and surfaces an exact next-step hint for each.

Common issues:

- **`502 llm_resolution_error`** — no `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OLLAMA_HOST` in the container's env.
- **`500 auth_misconfigured`** — `VSTACK_API_REQUIRE_AUTH=true` but no `VSTACK_API_KEYS`.
- **`413 request_too_large`** — bump `VSTACK_API_MAX_BODY_BYTES` or split the trace.
- **`504 timeout`** — forensic-mode analysis exceeded the 120s default. Try `mode=quick` or bump `VSTACK_API_REQUEST_TIMEOUT`.
- **Docker build fails on `valanistack==X.Y.Z` not found** — wait for PyPI propagation (~10 min) or pin to a known-good earlier release.
