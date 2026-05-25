"""Command-line entry point for the Yerkes-Dodson Workload Diagnostic."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import IO, Any

from ._composition import YERKES_DODSON_COMPOSITION
from ._playbooks import PLAYBOOKS
from .generator import YerkesDodsonAnalyzer
from .schema import AgentPerformanceTrace, WorkloadDetection


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


def _read_trace(path: str) -> AgentPerformanceTrace:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text()
    return AgentPerformanceTrace.model_validate_json(raw)


def _write_detection(detection: WorkloadDetection, out: IO[str], fmt: str) -> None:
    if fmt == "json":
        out.write(detection.model_dump_json(indent=2))
        out.write("\n")
    elif fmt == "markdown":
        out.write(detection.to_markdown())
    else:
        raise SystemExit(f"unknown --format {fmt!r}; choose markdown|json")


def _cmd_analyze(args: argparse.Namespace) -> int:
    trace = _read_trace(args.trace)
    client = _make_client(args.client, args.model, args.stub_responses)
    analyzer = YerkesDodsonAnalyzer(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
        mode=args.mode,
        max_retries=args.max_retries,
    )
    detection = analyzer.run(trace, baseline_path=args.baseline)
    out: IO[str]
    if args.out:
        out = open(args.out, "w")
    else:
        out = sys.stdout
    try:
        _write_detection(detection, out, args.format)
    finally:
        if args.out:
            out.close()
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    try:
        import yaml
    except ImportError:
        raise SystemExit("`batch` requires pyyaml. Install: pip install pyyaml")
    raw = yaml.safe_load(Path(args.corpus).read_text())
    if not isinstance(raw, list):
        raise SystemExit(f"corpus {args.corpus} must be a YAML list at top level")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    client = _make_client(args.client, args.model, args.stub_responses)
    analyzer = YerkesDodsonAnalyzer(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
        mode=args.mode,
        max_retries=args.max_retries,
    )
    n = 0
    for entry in raw:
        n += 1
        trace_data = entry.get("trace") if isinstance(entry, dict) else None
        if trace_data is None:
            continue
        trace = AgentPerformanceTrace.model_validate(trace_data)
        try:
            detection = analyzer.run(trace)
        except Exception as exc:
            print(
                f"[{entry.get('id', f'trace-{n}')}] error: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue
        scenario_id = entry.get("id", f"trace-{n}")
        out_path = out_dir / f"{scenario_id}.{args.format}"
        with open(out_path, "w") as out:
            _write_detection(detection, out, args.format)
        print(
            f"[{scenario_id}] zone={detection.observed_zone} "
            f"failure={detection.failure_mode} profile={detection.profile_pattern}",
            file=sys.stderr,
        )
    print(f"wrote {n} detections to {out_dir}/", file=sys.stderr)
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    raw = Path(args.detection).read_text()
    obj = json.loads(raw)
    if "detection" in obj and "schema_version" in obj:
        detection = WorkloadDetection.model_validate(obj["detection"])
    else:
        detection = WorkloadDetection.model_validate(obj)
    sys.stdout.write(detection.to_markdown())
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    _ = _read_trace(args.trace)
    print(f"OK -- {args.trace} parses as AgentPerformanceTrace")
    return 0


def _cmd_schema(args: argparse.Namespace) -> int:
    target = args.target
    if target == "trace":
        schema = AgentPerformanceTrace.model_json_schema()
    elif target == "detection":
        schema = WorkloadDetection.model_json_schema()
    else:
        raise SystemExit(f"unknown --target {target!r}; choose trace|detection")
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
        for (zone, failure_mode), pb in sorted(PLAYBOOKS.items()):
            payload.append(
                {
                    "zone": zone,
                    "failure_mode": failure_mode,
                    "title": pb.title,
                    "expected_effort": pb.expected_effort,
                    "anchor_citation": pb.anchor_citation,
                    "steps": pb.steps,
                }
            )
        sys.stdout.write(json.dumps(payload, indent=2))
        sys.stdout.write("\n")
        return 0
    print("# Yerkes-Dodson Failure-Mode Playbooks\n")
    for (zone, failure_mode), pb in sorted(PLAYBOOKS.items()):
        print(f"## ({zone}, {failure_mode}) -- {pb.title}")
        print(f"_Effort: {pb.expected_effort}_")
        if pb.anchor_citation:
            print(f"_Anchor: {pb.anchor_citation}_\n")
        for i, step in enumerate(pb.steps, 1):
            print(f"{i}. {step}")
        print()
    return 0


def _cmd_compose(args: argparse.Namespace) -> int:
    sys.stdout.write(json.dumps(YERKES_DODSON_COMPOSITION, indent=2, default=list))
    sys.stdout.write("\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vstack-yerkes",
        description="Yerkes-Dodson Optimal Workload diagnostic.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="Run on a single trace.")
    a.add_argument("--trace", required=True)
    a.add_argument("--mode", choices=("quick", "standard", "forensic"), default="standard")
    a.add_argument("--client", default="stub")
    a.add_argument("--model", default=None)
    a.add_argument("--stub-responses", default=None)
    a.add_argument("--format", choices=("markdown", "json"), default="markdown")
    a.add_argument("--baseline", default=None)
    a.add_argument("--out", default=None)
    a.add_argument("--max-retries", type=int, default=3)
    a.set_defaults(func=_cmd_analyze)

    b = sub.add_parser("batch", help="Run over a YAML corpus.")
    b.add_argument("--corpus", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--mode", choices=("quick", "standard", "forensic"), default="standard")
    b.add_argument("--client", default="stub")
    b.add_argument("--model", default=None)
    b.add_argument("--stub-responses", default=None)
    b.add_argument("--format", choices=("markdown", "json"), default="json")
    b.add_argument("--max-retries", type=int, default=3)
    b.set_defaults(func=_cmd_batch)

    r = sub.add_parser("replay", help="Render existing detection JSON.")
    r.add_argument("--detection", required=True)
    r.set_defaults(func=_cmd_replay)

    v = sub.add_parser("validate", help="Schema-validate a trace.")
    v.add_argument("--trace", required=True)
    v.set_defaults(func=_cmd_validate)

    s = sub.add_parser("schema", help="Dump JSON schema.")
    s.add_argument("--target", choices=("trace", "detection"), default="trace")
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
