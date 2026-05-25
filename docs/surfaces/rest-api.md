# REST API (FastAPI)

```bash
pip install 'valanistack[anthropic,api]'
export ANTHROPIC_API_KEY="sk-ant-..."
vstack-api serve                  # 127.0.0.1:8000 by default
```

## Endpoints

- `GET  /healthz` — liveness probe
- `GET  /v1/patterns` — catalogue of all 34 patterns + tool names + analyze URLs
- `GET  /v1/patterns/{name}` — one pattern's record
- `GET  /v1/patterns/{name}/playbooks` — per-pattern failure-mode playbooks
- `GET  /v1/patterns/{name}/citations` — per-pattern CITATIONS.md
- `GET  /v1/patterns/{name}/composition` — composition manifest
- `POST /v1/analyze/{name}` — run the pattern; body is the pattern's input trace (with optional top-level `mode` / `model`)
- `GET  /openapi.json` — full OpenAPI 3.x spec; feed it into any client SDK generator
- `GET  /docs` — interactive Swagger UI

No auth in v0; bind to `127.0.0.1` only and put a real reverse proxy in front if you go remote.

## Request shape

The POST accepts either the trace fields at the top level **or** an envelope `{"trace": {...}, "mode": "standard", "model": "..."}`. Both shapes are equivalent.

```bash
curl -X POST http://127.0.0.1:8000/v1/analyze/lewin \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Answer Pluto question",
    "steps": [{"type":"output","content":"Pluto reclassified in 2003."}],
    "outcome": "Confidently wrong (correct: 2006).",
    "success": false,
    "mode": "standard"
  }'
```

## Error envelope

All errors come back as `{"detail": {"error": "<kind>", "message": "..."}}`:

- 400 `validation_error` — input doesn't match the pattern's Pydantic model.
- 400 `invalid_mode` — `mode` not in `["quick", "standard", "forensic"]`.
- 404 `unknown_pattern` — no such pattern name.
- 502 `llm_resolution_error` — no `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OLLAMA_HOST` configured.
- 502 `analyzer_error` — runtime failure inside the pattern.
