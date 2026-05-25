"""Per-request correlation IDs.

The REST API middleware reads the inbound ``X-Request-ID`` header
(or generates one if absent), stashes it in a contextvar, attaches
it to every log line emitted during the request, and echoes it on
the response so the client can correlate.
"""

from __future__ import annotations

import contextvars
import secrets

REQUEST_ID_HEADER = "X-Request-ID"

_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "vstack_request_id", default=None
)


def get_or_create_request_id(incoming: str | None = None) -> str:
    """Return the inbound ID if valid, otherwise generate a fresh one.

    A valid ID is 1-200 chars long, ASCII alphanumeric plus a small
    set of punctuation we accept (``- _ : .``). Anything else gets
    replaced with a fresh server-generated ID — we never echo back
    untrusted text in headers.
    """
    if incoming:
        if 1 <= len(incoming) <= 200 and all(c.isalnum() or c in "-_:." for c in incoming):
            return incoming
    return "req_" + secrets.token_hex(8)


def set_current_request_id(request_id: str | None) -> contextvars.Token[str | None]:
    """Bind ``request_id`` to the current task/thread context.

    Returns a token the caller passes to :func:`reset_request_id`
    when the request is done. Middleware uses a ``try / finally``
    around the request handler.
    """
    return _request_id_var.set(request_id)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    _request_id_var.reset(token)


def current_request_id() -> str | None:
    """Return the request ID bound to the current context, if any.

    Use this in log filter functions / Sentry breadcrumbs / etc.
    """
    return _request_id_var.get()
