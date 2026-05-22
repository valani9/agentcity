"""
Command-line interface for the AAR Generator.

Examples:

    # Read a JSON trace from a file and write the AAR markdown to stdout
    agentcity aar --trace trace.json --client stub

    # Same, but pipe instead
    cat trace.json | agentcity aar --client anthropic > aar.md

    # Run the synthetic-failure benchmark
    agentcity bench --client anthropic

    # Show version
    agentcity --version

The CLI does not require any LLM API key in --client stub mode; useful
for trying the pipeline before deciding which provider to commit to.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from .clients import (
    AnthropicClient,
    OllamaClient,
    OpenAIClient,
    StubClient,
)
from .generator import AARGenerator
from .schema import AgentTrace


def _configure_logging(verbosity: int) -> None:
    """Translate -v / -vv flags into Python logging levels."""
    level = {0: logging.WARNING, 1: logging.INFO}.get(verbosity, logging.DEBUG)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )


def _make_client(name: str, model: str | None) -> Any:
    name = name.lower()
    if name == "anthropic":
        return AnthropicClient(model=model or "claude-sonnet-4-6")
    if name == "openai":
        return OpenAIClient(model=model or "gpt-5")
    if name == "ollama":
        return OllamaClient(model=model or "llama3.1:8b")
    if name == "stub":
        # Stub returns minimal canned output, useful for smoke-testing the
        # pipeline without an API key. Real output requires a real client.
        return StubClient(
            [
                "Restated goal placeholder.",
                "Results narrative placeholder.",
                json.dumps([]),
                json.dumps([]),
            ]
        )
    raise SystemExit(f"Unknown client: {name!r}. Use anthropic, openai, ollama, or stub.")


def _read_trace_input(path: str | None) -> AgentTrace:
    """Read a JSON trace either from a path or from stdin."""
    if path == "-" or path is None:
        raw = sys.stdin.read()
        source = "stdin"
    else:
        with open(path) as f:
            raw = f.read()
        source = path
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to parse JSON from {source}: {exc}")

    # Coerce step timestamps to datetime if they're ISO strings.
    for step in data.get("steps", []):
        ts = step.get("timestamp")
        if isinstance(ts, str):
            step["timestamp"] = datetime.fromisoformat(ts)
        elif ts is None:
            step["timestamp"] = datetime.now(timezone.utc)

    try:
        return AgentTrace(**data)
    except Exception as exc:
        raise SystemExit(f"Trace failed schema validation: {exc}")


def cmd_aar(args: argparse.Namespace) -> int:
    """`agentcity aar` — produce an AAR from a JSON trace."""
    trace = _read_trace_input(args.trace)
    client = _make_client(args.client, args.model)
    generator = AARGenerator(
        llm_client=client,
        model=args.model or getattr(client, "model", "unknown"),
        max_retries=args.max_retries,
    )
    aar = generator.generate(trace)

    if args.format == "markdown":
        sys.stdout.write(aar.to_markdown())
    elif args.format == "json":
        sys.stdout.write(aar.model_dump_json(indent=2))
    sys.stdout.write("\n")
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    """`agentcity bench` — run the synthetic-failure benchmark."""
    # The benchmark runner lives next to the YAML corpus, not in the
    # library. We re-implement the invocation here to keep the dependency
    # surface clean (no PyYAML in the library itself).
    sys.stderr.write(
        "Run the synthetic-failure benchmark by cloning the AgentCity "
        "repository and running\n"
        "  python module-2-team/30-aar-generator/eval/run_benchmark.py "
        "--client " + args.client + "\n"
    )
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    from . import __version__

    sys.stdout.write(f"agentcity {__version__}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentcity",
        description=(
            "AgentCity CLI — organizational behavior patterns for AI agents. "
            "Currently ships pattern #30 (AAR Generator)."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (-v INFO, -vv DEBUG).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    aar = sub.add_parser("aar", help="Generate an AAR from a JSON trace.")
    aar.add_argument(
        "--trace",
        "-t",
        default="-",
        help="Path to a JSON trace file, or - for stdin (default: stdin).",
    )
    aar.add_argument(
        "--client",
        "-c",
        default="stub",
        choices=["stub", "anthropic", "openai", "ollama"],
        help="LLM client to use (default: stub, no API key required).",
    )
    aar.add_argument(
        "--model",
        "-m",
        default=None,
        help="Model name override (e.g. claude-sonnet-4-6, gpt-5).",
    )
    aar.add_argument(
        "--format",
        "-f",
        default="markdown",
        choices=["markdown", "json"],
        help="Output format (default: markdown).",
    )
    aar.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum LLM call attempts on retryable errors (default: 3).",
    )
    aar.set_defaults(func=cmd_aar)

    bench = sub.add_parser(
        "bench",
        help="Run the synthetic-failure benchmark (delegates to the eval script).",
    )
    bench.add_argument(
        "--client",
        "-c",
        default="stub",
        choices=["stub", "anthropic", "openai", "ollama"],
        help="LLM client to use (default: stub).",
    )
    bench.set_defaults(func=cmd_bench)

    ver = sub.add_parser("version", help="Print the installed agentcity version.")
    ver.set_defaults(func=cmd_version)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
