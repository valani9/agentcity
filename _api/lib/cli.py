"""``vstack-api`` CLI -- serve the FastAPI app via uvicorn.

Defaults to ``127.0.0.1:8000`` (loopback only; no auth in v0).
Override host/port via flags or via ``vstack-config set api_host``
and ``vstack-config set api_port``.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable, Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vstack-api",
        description=(
            "vstack REST API. 34 analyze endpoints + catalogue + per-pattern "
            "citations/playbooks/composition. Runs uvicorn on localhost; "
            "do NOT expose to a public network without adding auth."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Start the API server (default).")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--workers", type=int, default=1)
    serve.add_argument(
        "--log-level",
        default="info",
        choices=("critical", "error", "warning", "info", "debug", "trace"),
    )
    serve.add_argument(
        "--reload",
        action="store_true",
        help="Reload on file changes (dev mode; uses uvicorn import string).",
    )

    sub.add_parser("routes", help="Print every registered route + method.")
    sub.add_parser(
        "openapi",
        help="Print the OpenAPI JSON spec to stdout (useful for SDK gen).",
    )

    args = parser.parse_args(argv)
    cmd = args.command or "serve"

    if cmd == "serve":
        return _run_serve(
            host=args.host,
            port=args.port,
            workers=args.workers,
            log_level=args.log_level,
            reload=args.reload,
        )
    if cmd == "routes":
        return _run_routes()
    if cmd == "openapi":
        return _run_openapi()
    parser.error(f"Unknown command: {cmd}")
    return 2


def _resolve_host_port(host: str | None, port: int | None) -> tuple[str, int]:
    get_key: Callable[..., Any] | None
    try:
        from vstack.memory import get_key as _get_key

        get_key = _get_key
    except ImportError:  # vstack.memory may not be installed in odd setups
        get_key = None

    if host is None and get_key is not None:
        host = get_key("api_host") or "127.0.0.1"
    elif host is None:
        host = "127.0.0.1"

    if port is None and get_key is not None:
        configured = get_key("api_port")
        if isinstance(configured, int):
            port = configured
        elif isinstance(configured, str) and configured.isdigit():
            port = int(configured)
        else:
            port = 8000
    elif port is None:
        port = 8000
    return host, port


def _run_serve(
    *,
    host: str | None,
    port: int | None,
    workers: int,
    log_level: str,
    reload: bool,
) -> int:
    try:
        import uvicorn
    except ImportError:
        print(
            "vstack-api: uvicorn is not installed. Run: pip install 'valanistack[api]'",
            file=sys.stderr,
        )
        return 2

    host, port = _resolve_host_port(host, port)
    if reload:
        # uvicorn requires an import string for --reload.
        uvicorn.run(
            "vstack.api:app",
            host=host,
            port=port,
            workers=workers,
            log_level=log_level,
            reload=True,
        )
    else:
        from ._app import build_app

        app = build_app()
        uvicorn.run(
            app,
            host=host,
            port=port,
            workers=workers,
            log_level=log_level,
        )
    return 0


def _run_routes() -> int:
    from ._app import build_app

    app = build_app()
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        if not path:
            continue
        ms = ",".join(sorted(methods))
        print(f"{ms:<20} {path}")
    return 0


def _run_openapi() -> int:
    import json as _json

    from ._app import build_app

    app = build_app()
    print(_json.dumps(app.openapi(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
