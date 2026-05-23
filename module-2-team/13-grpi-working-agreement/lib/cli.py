"""Command-line entry point for the GRPI Working Agreement Generator."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import IO, Any

from ._composition import GRPI_COMPOSITION
from ._playbooks import PLAYBOOKS
from .generator import GRPIWorkingAgreementAnalyzer
from .schema import TeamSetupRequest, WorkingAgreement


def _make_stub_client(stub_path: str | None) -> object:
    from agentcity.aar import StubClient

    responses: list[str] = []
    if stub_path:
        p = Path(stub_path)
        raw = json.loads(p.read_text())
        if not isinstance(raw, list):
            raise SystemExit(f"stub responses file {stub_path} must be a JSON array of strings")
        responses = [r if isinstance(r, str) else json.dumps(r) for r in raw]
    return StubClient(responses)


def _make_client(name: str, model: str | None, stub_path: str | None) -> object:
    name = (name or "stub").lower()
    if name == "stub":
        return _make_stub_client(stub_path)
    if name == "anthropic":
        from agentcity.aar import AnthropicClient

        return AnthropicClient(
            model=model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        )
    if name == "openai":
        from agentcity.aar import OpenAIClient

        return OpenAIClient(model=model or os.environ.get("OPENAI_MODEL", "gpt-5"))
    if name == "ollama":
        from agentcity.aar import OllamaClient

        return OllamaClient(model=model or os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    raise SystemExit(f"unknown client: {name!r}. Choose stub|anthropic|openai|ollama.")


def _read_request(path: str) -> TeamSetupRequest:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text()
    return TeamSetupRequest.model_validate_json(raw)


def _write_agreement(agreement: WorkingAgreement, out: IO[str], fmt: str) -> None:
    if fmt == "json":
        out.write(agreement.model_dump_json(indent=2))
        out.write("\n")
    elif fmt == "markdown":
        out.write(agreement.to_markdown())
    elif fmt == "preamble":
        out.write(agreement.to_orchestrator_preamble())
    else:
        raise SystemExit(f"unknown --format {fmt!r}; choose markdown|json|preamble")


def _cmd_generate(args: argparse.Namespace) -> int:
    request = _read_request(args.request)
    client = _make_client(args.client, args.model, args.stub_responses)
    analyzer = GRPIWorkingAgreementAnalyzer(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
        mode=args.mode,
        max_retries=args.max_retries,
    )
    agreement = analyzer.run(request, baseline_path=args.baseline)
    out: IO[str] = open(args.out, "w") if args.out else sys.stdout
    try:
        _write_agreement(agreement, out, args.format)
    finally:
        if args.out:
            out.close()
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    _ = _read_request(args.request)
    print(f"OK -- {args.request} parses as TeamSetupRequest")
    return 0


def _cmd_schema(args: argparse.Namespace) -> int:
    target = args.target
    if target == "request":
        schema = TeamSetupRequest.model_json_schema()
    elif target == "agreement":
        schema = WorkingAgreement.model_json_schema()
    else:
        raise SystemExit(f"unknown --target {target!r}; choose request|agreement")
    out_text = json.dumps(schema, indent=2)
    if args.out:
        Path(args.out).write_text(out_text + "\n")
        print(f"wrote schema to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(out_text)
        sys.stdout.write("\n")
    return 0


def _cmd_playbooks(args: argparse.Namespace) -> int:
    if args.format == "json":
        payload: list[dict[str, Any]] = []
        for (dim, fm), pb in sorted(PLAYBOOKS.items()):
            payload.append(
                {
                    "dimension": dim,
                    "failure_mode": fm,
                    "title": pb.title,
                    "expected_effort": pb.expected_effort,
                    "anchor_citation": pb.anchor_citation,
                    "steps": pb.steps,
                }
            )
        sys.stdout.write(json.dumps(payload, indent=2))
        sys.stdout.write("\n")
        return 0
    print("# GRPI Working Agreement Playbooks\n")
    for (dim, fm), pb in sorted(PLAYBOOKS.items()):
        print(f"## ({dim}, {fm}) -- {pb.title}")
        print(f"_Effort: {pb.expected_effort}_")
        if pb.anchor_citation:
            print(f"_Anchor: {pb.anchor_citation}_\n")
        for i, step in enumerate(pb.steps, 1):
            print(f"{i}. {step}")
        print()
    return 0


def _cmd_compose(args: argparse.Namespace) -> int:
    sys.stdout.write(json.dumps(GRPI_COMPOSITION, indent=2, default=list))
    sys.stdout.write("\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agentcity-grpi",
        description="GRPI Working Agreement generator.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Generate a working agreement.")
    g.add_argument("--request", required=True)
    g.add_argument("--mode", choices=("quick", "standard", "forensic"), default="standard")
    g.add_argument("--client", default="stub")
    g.add_argument("--model", default=None)
    g.add_argument("--stub-responses", default=None)
    g.add_argument(
        "--format",
        choices=("markdown", "json", "preamble"),
        default="markdown",
    )
    g.add_argument("--baseline", default=None)
    g.add_argument("--out", default=None)
    g.add_argument("--max-retries", type=int, default=3)
    g.set_defaults(func=_cmd_generate)

    v = sub.add_parser("validate", help="Schema-validate a request.")
    v.add_argument("--request", required=True)
    v.set_defaults(func=_cmd_validate)

    s = sub.add_parser("schema", help="Dump JSON schema.")
    s.add_argument("--target", choices=("request", "agreement"), default="request")
    s.add_argument("--out", default=None)
    s.set_defaults(func=_cmd_schema)

    pb = sub.add_parser("playbooks", help="List available playbooks.")
    pb.add_argument("--format", choices=("markdown", "json"), default="markdown")
    pb.set_defaults(func=_cmd_playbooks)

    c = sub.add_parser("compose", help="Show composition graph.")
    c.set_defaults(func=_cmd_compose)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
