"""vstack.api -- FastAPI HTTP surface exposing every vstack pattern.

A thin REST adapter over the same registry that powers ``vstack-mcp``.
Endpoints:

* ``GET /healthz`` -- liveness probe
* ``GET /v1/patterns`` -- catalogue of all 34 patterns
* ``GET /v1/patterns/{name}`` -- one pattern's full record
* ``GET /v1/patterns/{name}/playbooks`` -- per-pattern playbooks
* ``GET /v1/patterns/{name}/citations`` -- per-pattern CITATIONS.md
* ``GET /v1/patterns/{name}/composition`` -- composition manifest
* ``POST /v1/analyze/{name}`` -- run the analyzer with a JSON body
  matching the pattern's input model; returns the detection model
  serialized to JSON.

Auth is OFF in v0; the server is intended for ``127.0.0.1`` use
(``vstack-api serve`` defaults to localhost). API-key auth lands when
we go remote.

The OpenAPI spec FastAPI auto-generates covers all 34 endpoints with
their typed schemas, so a client SDK can be generated from the
running server.
"""

from ._app import (
    APIError,
    AnalyzeRequestEnvelope,
    AnalyzeResponseEnvelope,
    HealthResponse,
    PatternListResponse,
    PatternRecord,
    ReadyResponse,
    build_app,
    create_default_app,
)

__all__ = [
    "APIError",
    "AnalyzeRequestEnvelope",
    "AnalyzeResponseEnvelope",
    "HealthResponse",
    "PatternListResponse",
    "PatternRecord",
    "ReadyResponse",
    "build_app",
    "create_default_app",
]

__version__ = "0.3.0"
