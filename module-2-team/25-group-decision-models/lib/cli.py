"""Command-line entry point for the Group Decision Models generator."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import IO, Any

from ._composition import GROUP_DECISION_COMPOSITION
from ._playbooks import PLAYBOOKS
from .generator import DecisionProtocolAnalyzer
from .schema import AgentVote, DecisionProtocol, DecisionRequest


def _make_stub_client(stub_path: str | None) -> object:
    from vstack.aar import StubClient

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
        from vstack.aar import AnthropicClient

        return AnthropicClient(
            model=model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        )
    if name == "openai":
        from vstack.aar import OpenAIClient

        return OpenAIClient(model=model or os.environ.get("OPENAI_MODEL", "gpt-5"))
    if name == "ollama":
        from vstack.aar import OllamaClient

        return OllamaClient(model=model or os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    raise SystemExit(f"unknown client: {name!r}. Choose stub|anthropic|openai|ollama.")


def _read_request(path: str) -> DecisionRequest:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text()
    return DecisionRequest.model_validate_json(raw)


def _read_votes(path: str | None) -> list[AgentVote] | None:
    if not path:
        return None
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, list):
        raise SystemExit(f"votes file {path} must be a JSON array")
    return [AgentVote.model_validate(v) for v in raw]


def _write_protocol(protocol: DecisionProtocol, out: IO[str], fmt: str) -> None:
    if fmt == "json":
        out.write(protocol.model_dump_json(indent=2))
        out.write("\n")
    elif fmt == "markdown":
        out.write(protocol.to_markdown())
    elif fmt == "preamble":
        out.write(protocol.to_orchestrator_preamble())
        out.write("\n")
    else:
        raise SystemExit(f"unknown --format {fmt!r}")


def _cmd_analyze(args: argparse.Namespace) -> int:
    request = _read_request(args.request)
    votes = _read_votes(args.votes)
    client = _make_client(args.client, args.model, args.stub_responses)
    analyzer = DecisionProtocolAnalyzer(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
        mode=args.mode,
        max_retries=args.max_retries,
    )
    protocol = analyzer.run(request, votes, baseline_path=args.baseline)
    out: IO[str] = open(args.out, "w") if args.out else sys.stdout
    try:
        _write_protocol(protocol, out, args.format)
    finally:
        if args.out:
            out.close()
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    try:
        import yaml
    except ImportError:
        raise SystemExit("`batch` requires pyyaml.")
    raw = yaml.safe_load(Path(args.corpus).read_text())
    if not isinstance(raw, list):
        raise SystemExit(f"corpus {args.corpus} must be a YAML list")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = _make_client(args.client, args.model, args.stub_responses)
    analyzer = DecisionProtocolAnalyzer(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
        mode=args.mode,
        max_retries=args.max_retries,
    )
    n = 0
    for entry in raw:
        n += 1
        request_data = entry.get("request") if isinstance(entry, dict) else None
        if request_data is None:
            continue
        request = DecisionRequest.model_validate(request_data)
        try:
            protocol = analyzer.run(request)
        except Exception as exc:
            print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        scenario_id = entry.get("id", f"decision-{n}")
        with open(out_dir / f"{scenario_id}.{args.format}", "w") as out:
            _write_protocol(protocol, out, args.format)
    print(f"wrote {n} decision protocols to {out_dir}/", file=sys.stderr)
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    raw = Path(args.protocol).read_text()
    obj = json.loads(raw)
    if "protocol" in obj and "schema_version" in obj:
        protocol = DecisionProtocol.model_validate(obj["protocol"])
    else:
        protocol = DecisionProtocol.model_validate(obj)
    sys.stdout.write(protocol.to_markdown())
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    _ = _read_request(args.request)
    print(f"OK -- {args.request} parses as DecisionRequest")
    return 0


def _cmd_schema(args: argparse.Namespace) -> int:
    target = args.target
    if target == "request":
        schema = DecisionRequest.model_json_schema()
    elif target == "protocol":
        schema = DecisionProtocol.model_json_schema()
    elif target == "vote":
        schema = AgentVote.model_json_schema()
    else:
        raise SystemExit(f"unknown --target {target!r}")
    out_text = json.dumps(schema, indent=2)
    if args.out:
        Path(args.out).write_text(out_text + "\n")
    else:
        sys.stdout.write(out_text)
        sys.stdout.write("\n")
    return 0


def _cmd_playbooks(args: argparse.Namespace) -> int:
    if args.format == "json":
        payload: list[dict[str, Any]] = []
        for (m, fm), pb in sorted(PLAYBOOKS.items()):
            payload.append(
                {
                    "model": m,
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
    print("# Group Decision Playbooks\n")
    for (m, fm), pb in sorted(PLAYBOOKS.items()):
        print(f"## ({m}, {fm}) -- {pb.title}")
        print(f"_Effort: {pb.expected_effort}_")
        for i, step in enumerate(pb.steps, 1):
            print(f"{i}. {step}")
        print()
    return 0


def _cmd_compose(args: argparse.Namespace) -> int:
    sys.stdout.write(json.dumps(GROUP_DECISION_COMPOSITION, indent=2, default=list))
    sys.stdout.write("\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vstack-group-decision",
        description="Group Decision Models generator (Kaner 2014 facilitator canon).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("--request", required=True)
    a.add_argument("--votes", default=None, help="Optional JSON file with AgentVote list")
    a.add_argument("--mode", choices=("quick", "standard", "forensic"), default="standard")
    a.add_argument("--client", default="stub")
    a.add_argument("--model", default=None)
    a.add_argument("--stub-responses", default=None)
    a.add_argument("--format", choices=("markdown", "json", "preamble"), default="markdown")
    a.add_argument("--baseline", default=None)
    a.add_argument("--out", default=None)
    a.add_argument("--max-retries", type=int, default=3)
    a.set_defaults(func=_cmd_analyze)
    b = sub.add_parser("batch")
    b.add_argument("--corpus", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--mode", choices=("quick", "standard", "forensic"), default="standard")
    b.add_argument("--client", default="stub")
    b.add_argument("--model", default=None)
    b.add_argument("--stub-responses", default=None)
    b.add_argument("--format", choices=("markdown", "json", "preamble"), default="json")
    b.add_argument("--max-retries", type=int, default=3)
    b.set_defaults(func=_cmd_batch)
    r = sub.add_parser("replay")
    r.add_argument("--protocol", required=True)
    r.set_defaults(func=_cmd_replay)
    v = sub.add_parser("validate")
    v.add_argument("--request", required=True)
    v.set_defaults(func=_cmd_validate)
    s = sub.add_parser("schema")
    s.add_argument("--target", choices=("request", "protocol", "vote"), default="request")
    s.add_argument("--out", default=None)
    s.set_defaults(func=_cmd_schema)
    pb = sub.add_parser("playbooks")
    pb.add_argument("--format", choices=("markdown", "json"), default="markdown")
    pb.set_defaults(func=_cmd_playbooks)
    c = sub.add_parser("compose")
    c.set_defaults(func=_cmd_compose)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
