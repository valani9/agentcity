# REST API endpoints

Full reference; see [REST API surface](../surfaces/rest-api.md) for prose intro.

## Health + catalogue

| Method | Path | Returns |
|---|---|---|
| `GET` | `/healthz` | `{"status": "ok", "server": "vstack-api", "version": "0.5.0", "patterns": 34}` |
| `GET` | `/v1/patterns` | `{"count": 34, "patterns": [PatternRecord, ...]}` |
| `GET` | `/v1/patterns/{name}` | `PatternRecord` (404 if unknown) |

## Per-pattern resources

| Method | Path | Returns |
|---|---|---|
| `GET` | `/v1/patterns/{name}/playbooks` | The pattern's playbooks dict, JSON-serialized. |
| `GET` | `/v1/patterns/{name}/citations` | The pattern's CITATIONS.md as `text/markdown`. |
| `GET` | `/v1/patterns/{name}/composition` | The composition manifest, JSON-serialized. |

## Analyze

| Method | Path | Body | Returns |
|---|---|---|---|
| `POST` | `/v1/analyze/{name}` | Pattern input trace (flat) **or** `{"trace": {...}, "mode": "standard", "model": "..."}` envelope. | `AnalyzeResponseEnvelope` = `{pattern, mode, model, detection}`. |

Error envelope: `{"detail": {"error": "<kind>", "message": "..."}}` with status 400 (`validation_error` / `invalid_mode`), 404 (`unknown_pattern`), or 502 (`llm_resolution_error` / `analyzer_error`).

## OpenAPI + interactive docs

| Method | Path | Returns |
|---|---|---|
| `GET` | `/openapi.json` | Full OpenAPI 3.x spec. |
| `GET` | `/docs` | Swagger UI. |
| `GET` | `/redoc` | ReDoc UI. |
