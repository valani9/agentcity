"""Structured logging with run-id correlation for vstack patterns.

Every diagnostic run produces multiple log lines (validation, metric
computation, one or two LLM passes, intervention parsing). When you
have N parallel pattern runs in production, those lines interleave in
the log stream and become impossible to correlate without an explicit
run identifier.

This module provides:

  - ``new_run_id()`` — short stable identifier per diagnostic run.
  - ``run_context(run_id, pattern)`` — context manager that pushes
    ``run_id`` and ``pattern`` into a context variable so a logging
    Filter can inject them on every log record produced inside the
    block.
  - ``get_logger(name)`` — convenience wrapper that returns a logger
    with the run-context Filter attached.
  - ``configure_json_logging(level)`` — opt-in JSON formatter for
    production deployments that ship logs to a structured backend.

Patterns adopt this by replacing ``log = logging.getLogger(...)`` with
``log = get_logger(...)`` and wrapping the body of ``run(...)`` in
``with run_context(new_run_id(), pattern="<name>"):``. Adoption is
incremental — patterns that don't adopt still log fine, just without
the correlation fields.

This module has zero hard dependencies on external structured-logging
libraries. It uses ``contextvars`` (stdlib) and stdlib ``logging``
only. Callers wanting Datadog / Sentry / OTLP can wire their adapter
in front of the root logger without changing pattern code.
"""

from __future__ import annotations

import contextvars
import json
import logging
import secrets
from contextlib import contextmanager
from typing import Any, Iterator

_RUN_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "vstack_run_id", default=None
)
_PATTERN: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "vstack_pattern", default=None
)


def new_run_id() -> str:
    """Return a fresh 12-char URL-safe run identifier.

    Short enough to scan in logs by eye, long enough that collisions
    in a single deploy are astronomically unlikely (~72 bits of
    entropy).
    """
    return secrets.token_urlsafe(9)[:12]


@contextmanager
def run_context(run_id: str, pattern: str | None = None) -> Iterator[str]:
    """Context manager: push ``run_id`` and ``pattern`` so every log
    record inside the block carries them as structured attributes.

    Nesting is supported — inner context tokens are popped on exit
    so an outer run_id resumes correctly.
    """
    run_token = _RUN_ID.set(run_id)
    pattern_token = _PATTERN.set(pattern) if pattern else None
    try:
        yield run_id
    finally:
        _RUN_ID.reset(run_token)
        if pattern_token is not None:
            _PATTERN.reset(pattern_token)


def current_run_id() -> str | None:
    """Return the run id pushed by the innermost active ``run_context``."""
    return _RUN_ID.get()


def current_pattern() -> str | None:
    """Return the pattern label pushed by the innermost active ``run_context``."""
    return _PATTERN.get()


class _RunContextFilter(logging.Filter):
    """Inject ``run_id`` and ``pattern`` from the contextvars into every
    log record. If no context is active, fields are absent — formatters
    decide how to render that case.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        run_id = _RUN_ID.get()
        pattern = _PATTERN.get()
        if run_id is not None:
            record.run_id = run_id
        if pattern is not None:
            record.pattern = pattern
        return True


_filter_singleton = _RunContextFilter()


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the run-context filter attached.

    Idempotent: calling more than once for the same logger does not
    add the filter twice.
    """
    logger = logging.getLogger(name)
    if not any(isinstance(f, _RunContextFilter) for f in logger.filters):
        logger.addFilter(_filter_singleton)
    return logger


class JsonFormatter(logging.Formatter):
    """A minimal JSON formatter for structured-log backends.

    Emits one JSON object per log record with ``timestamp``, ``level``,
    ``logger``, ``message``, plus ``run_id`` / ``pattern`` when the
    record was produced inside an active :func:`run_context`. Extra
    fields attached via ``logger.info("msg", extra={...})`` are also
    included.
    """

    _RESERVED: frozenset[str] = frozenset(
        {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        run_id = getattr(record, "run_id", None)
        if run_id is not None:
            payload["run_id"] = run_id
        pattern = getattr(record, "pattern", None)
        if pattern is not None:
            payload["pattern"] = pattern
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key in payload:
                continue
            if key.startswith("_"):
                continue
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                payload[key] = repr(value)
            else:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_json_logging(level: int = logging.INFO) -> None:
    """Configure the root vstack logger for JSON output.

    Call once at process start in production deployments that ship
    logs to a structured backend (Datadog, Loki, CloudWatch, etc.).
    Tests and demos don't need this — stdlib formatting works fine.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(_filter_singleton)
    root = logging.getLogger("vstack")
    root.handlers = [handler]
    root.setLevel(level)
    root.propagate = False


__all__ = [
    "JsonFormatter",
    "configure_json_logging",
    "current_pattern",
    "current_run_id",
    "get_logger",
    "new_run_id",
    "run_context",
]
