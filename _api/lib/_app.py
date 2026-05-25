"""FastAPI application factory for the ``vstack-api`` server.

Reuses ``vstack.mcp._registry`` so the HTTP surface and the MCP
surface speak about the same 34 patterns. The MCP layer is the
canonical pattern registry; this module imports from it. Keeping a
single registry guarantees the two surfaces never drift on names,
input shapes, or mode enums.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

from fastapi import Body, FastAPI, HTTPException, Path
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from vstack.mcp._client import LLMResolutionError, default_model_for, resolve_llm_client
from vstack.mcp._registry import PATTERNS, PATTERNS_BY_NAME, PatternEntry, tool_name_for
from vstack.mcp._resources import read_resource

logger = logging.getLogger(__name__)


class APIError(BaseModel):
    """Standard error response envelope."""

    error: str
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"
    server: str = "vstack-api"
    version: str
    patterns: int


class PatternRecord(BaseModel):
    """One pattern as exposed over the HTTP catalogue."""

    name: str
    friendly: str
    group: str
    tool: str = Field(..., description="The matching MCP tool name (vstack_<name>).")
    summary: str
    input_class: str
    output_class: str
    modes: list[str]
    analyze_url: str
    resources: dict[str, str | None]


class PatternListResponse(BaseModel):
    count: int
    patterns: list[PatternRecord]


class AnalyzeRequestEnvelope(BaseModel):
    """Optional wrapping shape; clients can also POST the raw input model directly.

    The server accepts either shape. When this envelope is used, the
    pattern's input trace lives at ``trace`` and the optional ``mode``
    / ``model`` overrides live alongside it.
    """

    trace: dict[str, Any]
    mode: Optional[str] = None
    model: Optional[str] = None


class AnalyzeResponseEnvelope(BaseModel):
    """Wrapping for the detection plus diagnostic metadata."""

    pattern: str
    mode: str
    model: str
    detection: dict[str, Any]


def build_app(
    *,
    llm_client_factory: Optional[Callable[[], object]] = None,
) -> FastAPI:
    """Construct and return the FastAPI app.

    Parameters
    ----------
    llm_client_factory:
        Optional zero-arg callable returning an LLM client (anything
        exposing ``.complete(prompt, system=None)``). Defaults to
        :func:`vstack.mcp.resolve_llm_client`. Tests inject a stub
        client to avoid live LLM calls.
    """
    app = FastAPI(
        title="vstack API",
        description=(
            "HTTP surface for the 34 vstack organizational-behavior "
            "diagnostic patterns. Mirrors the MCP server's pattern "
            "registry; same inputs, same outputs, REST envelope."
        ),
        version="0.3.0",
    )
    factory = llm_client_factory or resolve_llm_client

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(version="0.3.0", patterns=len(PATTERNS))

    @app.get("/v1/patterns", response_model=PatternListResponse)
    async def list_patterns_endpoint() -> PatternListResponse:
        return PatternListResponse(
            count=len(PATTERNS),
            patterns=[_record_for(p) for p in PATTERNS],
        )

    @app.get(
        "/v1/patterns/{name}",
        response_model=PatternRecord,
        responses={404: {"model": APIError}},
    )
    async def get_pattern_endpoint(
        name: str = Path(..., description="Pattern import name, e.g. 'lewin'"),
    ) -> PatternRecord:
        pattern = _resolve_pattern_or_404(name)
        return _record_for(pattern)

    @app.get(
        "/v1/patterns/{name}/playbooks",
        responses={404: {"model": APIError}},
    )
    async def get_playbooks(name: str) -> Response:
        _resolve_pattern_or_404(name)
        mime, body = read_resource(f"vstack://patterns/{name}/playbooks")
        return Response(content=body, media_type=mime)

    @app.get(
        "/v1/patterns/{name}/citations",
        responses={404: {"model": APIError}},
    )
    async def get_citations(name: str) -> Response:
        _resolve_pattern_or_404(name)
        mime, body = read_resource(f"vstack://patterns/{name}/citations")
        return PlainTextResponse(content=body, media_type=mime)

    @app.get(
        "/v1/patterns/{name}/composition",
        responses={404: {"model": APIError}},
    )
    async def get_composition(name: str) -> Response:
        _resolve_pattern_or_404(name)
        mime, body = read_resource(f"vstack://patterns/{name}/composition")
        return Response(content=body, media_type=mime)

    @app.post(
        "/v1/analyze/{name}",
        response_model=AnalyzeResponseEnvelope,
        responses={
            400: {"model": APIError},
            404: {"model": APIError},
            502: {"model": APIError},
        },
    )
    async def analyze(
        name: str,
        payload: dict[str, Any] = Body(
            ...,
            description=(
                "Either the pattern's input trace directly, or an "
                "envelope {'trace': <input>, 'mode': 'standard', "
                "'model': '...'} when you need to override the mode "
                "or model. Optional 'mode' and 'model' may also "
                "appear at the top level of the trace shape."
            ),
        ),
    ) -> AnalyzeResponseEnvelope:
        pattern = _resolve_pattern_or_404(name)
        trace_data, mode, model = _unwrap_payload(payload)

        resolved = pattern.load()
        if mode and mode not in resolved.mode_values:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_mode",
                    "message": (
                        f"Mode {mode!r} not valid for {pattern.name}. "
                        f"Allowed: {list(resolved.mode_values)}"
                    ),
                },
            )
        try:
            trace = resolved.input_cls.model_validate(trace_data)
        except Exception as e:  # pydantic.ValidationError
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_error",
                    "message": str(e),
                },
            )

        try:
            llm = factory()
        except LLMResolutionError as e:
            raise HTTPException(
                status_code=502,
                detail={"error": "llm_resolution_error", "message": str(e)},
            )

        chosen_mode = mode or "standard"
        chosen_model = model or default_model_for(llm)  # type: ignore[arg-type]

        try:
            analyzer = resolved.analyzer_cls(llm, model=chosen_model, mode=chosen_mode)
            detection = analyzer.run(trace)
        except Exception as e:  # noqa: BLE001 - runtime analyzer failure
            logger.exception("vstack-api: pattern %s failed", pattern.name)
            raise HTTPException(
                status_code=502,
                detail={"error": "analyzer_error", "message": str(e)},
            )

        if hasattr(detection, "model_dump"):
            payload_out = detection.model_dump(mode="json")
        else:
            payload_out = json.loads(json.dumps(detection, default=str))

        return AnalyzeResponseEnvelope(
            pattern=pattern.name,
            mode=chosen_mode,
            model=chosen_model,
            detection=payload_out,
        )

    return app


def create_default_app() -> FastAPI:
    """Module-level app used by uvicorn one-shot invocations like ``vstack.api:app``."""
    return build_app()


def _resolve_pattern_or_404(name: str) -> PatternEntry:
    pattern = PATTERNS_BY_NAME.get(name)
    if pattern is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "unknown_pattern", "message": f"No vstack pattern named {name!r}."},
        )
    return pattern


def _unwrap_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str | None, str | None]:
    """Pull ``trace`` / ``mode`` / ``model`` from either envelope shape."""
    if "trace" in payload and isinstance(payload["trace"], dict):
        mode = payload.get("mode")
        model = payload.get("model")
        return payload["trace"], _str_or_none(mode), _str_or_none(model)
    body = dict(payload)
    mode = body.pop("mode", None)
    model = body.pop("model", None)
    return body, _str_or_none(mode), _str_or_none(model)


def _str_or_none(v: object) -> str | None:
    if v is None:
        return None
    return str(v)


def _record_for(pattern: PatternEntry) -> PatternRecord:
    resolved = pattern.load()
    return PatternRecord(
        name=pattern.name,
        friendly=pattern.friendly,
        group=pattern.group,
        tool=tool_name_for(pattern),
        summary=pattern.summary,
        input_class=pattern.input_cls,
        output_class=pattern.output_cls,
        modes=list(resolved.mode_values),
        analyze_url=f"/v1/analyze/{pattern.name}",
        resources={
            "playbooks": f"/v1/patterns/{pattern.name}/playbooks",
            "composition": f"/v1/patterns/{pattern.name}/composition",
            "citations": (
                f"/v1/patterns/{pattern.name}/citations" if pattern.citations_present else None
            ),
        },
    )
