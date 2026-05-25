"""FastAPI application factory for the ``vstack-api`` server.

Production-hardened in v0.6.0:

* **Authentication** -- configurable via :class:`APIKeyStore`; off by
  default (loopback-friendly) so existing local flows keep working.
* **Rate limiting** -- per-key + per-IP sliding-window limiter.
* **Request size + trace-shape limits** -- enforced before Pydantic.
* **Async analyze path** -- uses the analyzer's ``arun()`` mirror
  via a thread offload so concurrent HTTP requests don't serialize
  on the synchronous LLM client.
* **CORS + security headers** -- standard middleware stack.
* **Request ID + structured logging** -- ``X-Request-ID`` round-trip,
  context-var-bound, returned on every response.
* **Prometheus metrics** -- ``/metrics`` endpoint + per-pattern
  latency histogram + per-status counters.
* **Health endpoints** -- ``/healthz`` (liveness), ``/readyz``
  (readiness), ``/livez`` (alias for liveness) with separate
  semantics so K8s probes can distinguish startup from runtime.
* **Graceful shutdown** -- in-flight requests drain on SIGTERM.
* **Optional Sentry** -- enabled when ``SENTRY_DSN`` is set.

Reuses ``vstack.mcp._registry`` so the HTTP surface and the MCP
surface speak about the same 34 patterns.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import Any, AsyncIterator, Callable, Optional

from fastapi import Body, FastAPI, HTTPException, Path, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from vstack.cache import (
    CacheBackend,
    CacheEntry,
    build_cache_key,
    resolve_cache_from_env,
)
from vstack.mcp._client import LLMResolutionError, default_model_for, resolve_llm_client
from vstack.mcp._registry import PATTERNS, PATTERNS_BY_NAME, PatternEntry, tool_name_for
from vstack.mcp._resources import read_resource
from vstack.observability import (
    DEFAULT_METRICS_REGISTRY,
    MetricsRegistry,
    REQUEST_ID_HEADER,
    get_or_create_request_id,
    install_sentry_if_configured,
    render_prometheus,
    reset_request_id,
    set_current_request_id,
    time_request,
)
from vstack.security import (
    APIKeyStore,
    InMemoryRateLimiter,
    RateLimiter,
    RequestLimits,
    RequestSizeExceeded,
    enforce_trace_limits,
    load_keys_from_env,
)
from vstack.security._limits import request_limits_from_env

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Response models (kept stable for backward compat with v0.3.0 clients)
# ----------------------------------------------------------------------


class APIError(BaseModel):
    error: str
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"
    server: str = "vstack-api"
    version: str
    patterns: int


class ReadyResponse(BaseModel):
    status: str
    """``"ready"`` once the server has loaded the registry + an LLM
    client can be resolved; ``"warming"`` during startup; ``"draining"``
    during graceful shutdown."""

    detail: str = ""


class PatternRecord(BaseModel):
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
    trace: dict[str, Any]
    mode: Optional[str] = None
    model: Optional[str] = None


class AnalyzeResponseEnvelope(BaseModel):
    pattern: str
    mode: str
    model: str
    detection: dict[str, Any]
    cached: bool = False
    """True when the detection was served from the configured cache."""


# ----------------------------------------------------------------------
# Application-state container
# ----------------------------------------------------------------------


class _AppState:
    """Per-app runtime config gathered into one object for testability."""

    def __init__(
        self,
        *,
        keystore: APIKeyStore | None,
        require_auth: bool,
        rate_limiter: RateLimiter | None,
        limits: RequestLimits,
        cache: CacheBackend,
        metrics: MetricsRegistry,
        llm_client_factory: Callable[[], Any] | None,
    ) -> None:
        self.keystore = keystore or APIKeyStore()
        self.require_auth = require_auth
        self.rate_limiter = rate_limiter
        self.limits = limits
        self.cache = cache
        self.metrics = metrics
        self.llm_client_factory = llm_client_factory or resolve_llm_client
        self.ready = True
        """Goes False during graceful shutdown so readyz reports
        draining."""


# ----------------------------------------------------------------------
# Middleware
# ----------------------------------------------------------------------


class _RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate/echo a request ID + bind it for the lifetime of the request."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        rid = get_or_create_request_id(incoming)
        token = set_current_request_id(rid)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers[REQUEST_ID_HEADER] = rid
        return response


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Standard production headers on every response."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # CSP for the JSON-only API surface (no inline scripts).
        response.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
        # HSTS only if we're served over HTTPS; the reverse proxy
        # is the right place to set this but we set it defensively.
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        return response


class _BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds ``state.limits.max_body_bytes``."""

    def __init__(self, app: ASGIApp, state: _AppState) -> None:
        super().__init__(app)
        self._state = state

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                size = 0
            if size > self._state.limits.max_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": {
                            "error": "request_body_too_large",
                            "message": (
                                f"Request body {size} bytes exceeds "
                                f"limit {self._state.limits.max_body_bytes}. "
                                f"Set VSTACK_API_MAX_BODY_BYTES to raise."
                            ),
                        }
                    },
                )
        return await call_next(request)


class _AuthMiddleware(BaseHTTPMiddleware):
    """API-key auth + rate limiting in one middleware.

    Skips public paths (health probes, metrics, OpenAPI) so a
    reverse proxy can do its own checks. Treats the empty keystore
    as "auth not enforced" unless ``require_auth`` is True (in which
    case requests are rejected immediately with a config error).
    """

    PUBLIC_PATHS = {
        "/healthz",
        "/livez",
        "/readyz",
        "/metrics",
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
    }

    def __init__(self, app: ASGIApp, state: _AppState) -> None:
        super().__init__(app)
        self._state = state

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        path = request.url.path
        if path in self.PUBLIC_PATHS or path.startswith("/docs/"):
            return await call_next(request)

        if self._state.require_auth and not self._state.keystore:
            return JSONResponse(
                status_code=500,
                content={
                    "detail": {
                        "error": "auth_misconfigured",
                        "message": (
                            "require_auth=True but no API keys are loaded. Set "
                            "VSTACK_API_KEYS or VSTACK_API_KEYS_FILE."
                        ),
                    }
                },
            )

        api_key_name: str | None = None
        if self._state.keystore:
            raw = _extract_api_key(request)
            matched = self._state.keystore.verify(raw)
            if matched is None and self._state.require_auth:
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": {
                            "error": "unauthorized",
                            "message": (
                                "Missing or invalid API key. Send "
                                "'Authorization: Bearer <key>' or "
                                "'X-API-Key: <key>'."
                            ),
                        }
                    },
                    headers={"WWW-Authenticate": 'Bearer realm="vstack"'},
                )
            api_key_name = matched.name if matched else None

        if self._state.rate_limiter is not None:
            rate_key = api_key_name or _client_ip(request)
            decision = self._state.rate_limiter.check(rate_key)
            if not decision.allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": {
                            "error": "rate_limited",
                            "message": (
                                f"Rate limit {decision.limit}/window exceeded. "
                                f"Retry after {decision.retry_after_seconds:.2f}s."
                            ),
                        }
                    },
                    headers={
                        "Retry-After": str(max(1, int(decision.retry_after_seconds))),
                        "X-RateLimit-Limit": str(decision.limit),
                        "X-RateLimit-Remaining": "0",
                    },
                )
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(decision.limit)
            response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
            return response

        return await call_next(request)


def _extract_api_key(request: Request) -> str | None:
    """Pull the API key from either the Authorization or X-API-Key header."""
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key.strip()
    return None


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return getattr(request.client, "host", None) or "unknown"


# ----------------------------------------------------------------------
# build_app
# ----------------------------------------------------------------------


def build_app(
    *,
    llm_client_factory: Optional[Callable[[], object]] = None,
    keystore: APIKeyStore | None = None,
    require_auth: bool = False,
    rate_limiter: RateLimiter | None = None,
    limits: RequestLimits | None = None,
    cache: CacheBackend | None = None,
    metrics: MetricsRegistry | None = None,
    cors_origins: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> FastAPI:
    """Construct the FastAPI app.

    All arguments are optional + production-friendly defaults are
    resolved from environment variables when not supplied:

    * ``VSTACK_API_KEYS`` / ``VSTACK_API_KEYS_FILE`` -- API keys
    * ``VSTACK_API_REQUIRE_AUTH`` -- ``"1"`` / ``"true"`` to enforce
    * ``VSTACK_API_RATE_LIMIT`` -- ``"100/60"`` (requests/window-seconds);
      ``"off"`` to disable.
    * ``VSTACK_API_MAX_*`` -- see :class:`RequestLimits`
    * ``VSTACK_CACHE=memory`` -- enable in-memory caching
    * ``VSTACK_API_CORS_ORIGINS`` -- comma-separated allowed origins
    * ``SENTRY_DSN`` -- optional error reporting
    """
    import os

    env = env if env is not None else dict(os.environ)
    keystore = keystore or load_keys_from_env(env)
    require_auth = require_auth or _bool_env(env, "VSTACK_API_REQUIRE_AUTH")
    rate_limiter = rate_limiter if rate_limiter is not None else _rate_limiter_from_env(env)
    limits = limits or request_limits_from_env(env)
    cache = cache or resolve_cache_from_env(env)
    metrics = metrics or DEFAULT_METRICS_REGISTRY
    cors_origins = cors_origins or _cors_origins_from_env(env)
    install_sentry_if_configured(env)

    state = _AppState(
        keystore=keystore,
        require_auth=require_auth,
        rate_limiter=rate_limiter,
        limits=limits,
        cache=cache,
        metrics=metrics,
        llm_client_factory=llm_client_factory,
    )

    @contextlib.asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Startup: nothing async to do; the state object is already
        # constructed and ready to accept requests.
        yield
        # Shutdown: flip the readyz flag so K8s probes know we're
        # draining, then yield briefly to let in-flight requests
        # finish before uvicorn force-closes their sockets.
        state.ready = False
        await asyncio.sleep(0)

    app = FastAPI(
        title="vstack API",
        description=(
            "HTTP surface for the 34 vstack organizational-behavior "
            "diagnostic patterns. Mirrors the MCP server's pattern "
            "registry; same inputs, same outputs, REST envelope."
        ),
        version="0.6.0",
        lifespan=_lifespan,
    )
    app.state.vstack = state

    # Middleware order is reversed for incoming requests: the LAST
    # one added is the FIRST to see the request. We want request-ID
    # binding to happen first so every log line during the request
    # carries the ID; then security headers; then body-size check
    # (so we reject huge bodies before doing CORS / auth work); then
    # auth + rate limit. CORS lives at the bottom-ish so its
    # response headers wrap everything.
    app.add_middleware(_AuthMiddleware, state=state)
    app.add_middleware(_BodySizeLimitMiddleware, state=state)
    app.add_middleware(_SecurityHeadersMiddleware)
    app.add_middleware(_RequestIDMiddleware)
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
            expose_headers=[
                REQUEST_ID_HEADER,
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
            ],
        )

    @app.get("/healthz", response_model=HealthResponse, include_in_schema=True)
    async def healthz() -> HealthResponse:
        return HealthResponse(version="0.6.0", patterns=len(PATTERNS))

    @app.get("/livez", response_model=HealthResponse, include_in_schema=False)
    async def livez() -> HealthResponse:
        return HealthResponse(version="0.6.0", patterns=len(PATTERNS))

    @app.get("/readyz", response_model=ReadyResponse)
    async def readyz() -> ReadyResponse:
        if not state.ready:
            return ReadyResponse(status="draining", detail="graceful shutdown in progress")
        return ReadyResponse(status="ready")

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics_endpoint() -> PlainTextResponse:
        return PlainTextResponse(
            render_prometheus(state.metrics), media_type="text/plain; version=0.0.4"
        )

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

    @app.get("/v1/patterns/{name}/playbooks", responses={404: {"model": APIError}})
    async def get_playbooks(name: str) -> Response:
        _resolve_pattern_or_404(name)
        mime, body = read_resource(f"vstack://patterns/{name}/playbooks")
        return Response(content=body, media_type=mime)

    @app.get("/v1/patterns/{name}/citations", responses={404: {"model": APIError}})
    async def get_citations(name: str) -> Response:
        _resolve_pattern_or_404(name)
        mime, body = read_resource(f"vstack://patterns/{name}/citations")
        return PlainTextResponse(content=body, media_type=mime)

    @app.get("/v1/patterns/{name}/composition", responses={404: {"model": APIError}})
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
            413: {"model": APIError},
            429: {"model": APIError},
            502: {"model": APIError},
        },
    )
    async def analyze(
        name: str,
        payload: dict[str, Any] = Body(...),
    ) -> AnalyzeResponseEnvelope:
        pattern = _resolve_pattern_or_404(name)
        trace_data, mode, model = _unwrap_payload(payload)

        try:
            enforce_trace_limits(trace_data, state.limits)
        except RequestSizeExceeded as e:
            raise HTTPException(
                status_code=413,
                detail={"error": "request_too_large", "message": str(e)},
            )

        resolved = pattern.load()
        chosen_mode = mode or "standard"
        if chosen_mode not in resolved.mode_values:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_mode",
                    "message": (
                        f"Mode {chosen_mode!r} not valid for {pattern.name}. "
                        f"Allowed: {list(resolved.mode_values)}"
                    ),
                },
            )

        try:
            trace = resolved.input_cls.model_validate(trace_data)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail={"error": "validation_error", "message": str(e)},
            )

        # Cache lookup BEFORE LLM resolution so a cache hit doesn't
        # waste an LLM-client construction (which can involve a network
        # round-trip for some providers).
        cache_model_key = model or "auto"
        cache_key = build_cache_key(
            pattern=pattern.name,
            mode=chosen_mode,
            model=cache_model_key,
            trace=trace_data,
        )
        cached_entry = state.cache.get(cache_key)
        if cached_entry is not None:
            with time_request(
                surface="rest",
                pattern=pattern.name,
                mode=chosen_mode,
                registry=state.metrics,
            ) as bucket:
                bucket["status"] = "cache_hit"
            return AnalyzeResponseEnvelope(
                pattern=pattern.name,
                mode=chosen_mode,
                model=cache_model_key,
                detection=dict(cached_entry.detection),
                cached=True,
            )

        try:
            llm = state.llm_client_factory()
        except LLMResolutionError as e:
            raise HTTPException(
                status_code=502,
                detail={"error": "llm_resolution_error", "message": str(e)},
            )
        chosen_model = model or default_model_for(llm)

        with time_request(
            surface="rest",
            pattern=pattern.name,
            mode=chosen_mode,
            registry=state.metrics,
        ) as bucket:
            try:
                detection = await _run_pattern_async(
                    resolved=resolved,
                    llm=llm,
                    chosen_model=chosen_model,
                    chosen_mode=chosen_mode,
                    trace=trace,
                    timeout_seconds=state.limits.request_timeout_seconds,
                )
                bucket["status"] = "ok"
            except asyncio.TimeoutError:
                bucket["status"] = "timeout"
                raise HTTPException(
                    status_code=504,
                    detail={
                        "error": "timeout",
                        "message": (
                            f"Analyzer for {pattern.name} exceeded the "
                            f"{state.limits.request_timeout_seconds:.0f}s "
                            "server-side deadline. Try mode=quick or split the trace."
                        ),
                    },
                )
            except Exception as e:  # noqa: BLE001 - runtime analyzer failure
                bucket["status"] = "analyzer_error"
                logger.exception("vstack-api: pattern %s failed", pattern.name)
                raise HTTPException(
                    status_code=502,
                    detail={"error": "analyzer_error", "message": str(e)},
                )

        if hasattr(detection, "model_dump"):
            payload_out = detection.model_dump(mode="json")
        else:
            payload_out = json.loads(json.dumps(detection, default=str))

        state.cache.set(
            cache_key,
            CacheEntry(detection=payload_out, created_at=time.time()),
        )

        return AnalyzeResponseEnvelope(
            pattern=pattern.name,
            mode=chosen_mode,
            model=chosen_model,
            detection=payload_out,
            cached=False,
        )

    return app


def create_default_app() -> FastAPI:
    return build_app()


# ----------------------------------------------------------------------
# internals
# ----------------------------------------------------------------------


async def _run_pattern_async(
    *,
    resolved: Any,
    llm: Any,
    chosen_model: str,
    chosen_mode: str,
    trace: Any,
    timeout_seconds: float,
) -> Any:
    """Run the analyzer either via its async mirror or in a thread.

    Patterns ship a ``*Async`` mirror under the same module
    (``LewinAttributionDetectorAsync``, etc.). When that mirror is
    importable + the LLM client has an async ``.acomplete``
    method, we await it directly. Otherwise we run the sync
    analyzer in a thread to avoid blocking the FastAPI event loop.
    """
    module = resolved.module
    async_cls_name = resolved.analyzer_cls.__name__ + "Async"
    async_cls = getattr(module, async_cls_name, None)
    if async_cls is not None and hasattr(llm, "acomplete"):
        analyzer = async_cls(llm, model=chosen_model, mode=chosen_mode)
        return await asyncio.wait_for(analyzer.arun(trace), timeout=timeout_seconds)
    # Sync analyzer offloaded to a thread.
    analyzer = resolved.analyzer_cls(llm, model=chosen_model, mode=chosen_mode)
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(None, analyzer.run, trace),
        timeout=timeout_seconds,
    )


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


def _bool_env(env: dict[str, str], key: str) -> bool:
    raw = (env.get(key) or "").strip().lower()
    return raw in ("1", "true", "yes", "on", "enabled")


def _rate_limiter_from_env(env: dict[str, str]) -> RateLimiter | None:
    raw = (env.get("VSTACK_API_RATE_LIMIT") or "").strip().lower()
    if not raw or raw in ("off", "none", "disabled"):
        return None
    try:
        if "/" in raw:
            count, window = raw.split("/", 1)
            return InMemoryRateLimiter(
                max_requests=max(1, int(count)),
                window_seconds=max(1.0, float(window)),
            )
        return InMemoryRateLimiter(max_requests=max(1, int(raw)))
    except ValueError:
        logger.warning(
            "VSTACK_API_RATE_LIMIT=%r is not a valid spec; rate limiting disabled.",
            raw,
        )
        return None


def _cors_origins_from_env(env: dict[str, str]) -> list[str]:
    raw = env.get("VSTACK_API_CORS_ORIGINS") or ""
    return [o.strip() for o in raw.split(",") if o.strip()]
