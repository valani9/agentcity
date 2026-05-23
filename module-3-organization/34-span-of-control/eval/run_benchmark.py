"""Benchmark runner for the Span-of-Control / Centralization Calculator."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as e:
    raise SystemExit("PyYAML required. Install: pip install pyyaml") from e

try:
    from agentcity.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from agentcity.span_of_control import (
        AgentNode,
        CrewLoadTrace,
        SpanLoadAnalysis,
        SpanLoadCalculator,
    )
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc

_HERE = Path(__file__).resolve().parent


def load_corpus(path: Path) -> list[dict[str, Any]]:
    with open(path) as f:
        return yaml.safe_load(f)["scenarios"]


def scenario_to_trace(scenario: dict[str, Any]) -> CrewLoadTrace:
    t = scenario["trace"]
    return CrewLoadTrace(
        crew_id=scenario["id"],
        task=t["task"],
        agents=[AgentNode(**a) for a in t["agents"]],
        incoming_request_rate=t.get("incoming_request_rate", 1.0),
        observed_behaviors=t.get("observed_behaviors", []),
        outcome=t["outcome"],
        success=t.get("success", False),
    )


def score_analysis(analysis: SpanLoadAnalysis, scenario: dict[str, Any]) -> dict[str, Any]:
    expected_quality = scenario["expected_quality"]
    expected_bottleneck = scenario.get("expected_bottleneck_includes")

    quality_match = analysis.structural_load_quality == expected_quality
    if expected_bottleneck is None:
        bottleneck_match = len(analysis.bottleneck_agent_ids) == 0
    else:
        bottleneck_match = expected_bottleneck in analysis.bottleneck_agent_ids

    composite = (1.0 if quality_match else 0.0) * 0.5 + (1.0 if bottleneck_match else 0.0) * 0.5
    return {
        "quality_match": quality_match,
        "bottleneck_match": bottleneck_match,
        "composite": round(composite, 3),
        "actual_quality": analysis.structural_load_quality,
        "actual_bottleneck_ids": analysis.bottleneck_agent_ids,
        "structural_load_score": analysis.structural_load_score,
    }


def pick_client(name: str) -> object:
    name = name.lower()
    if name == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if name == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if name == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient(["[]"] * 100)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client", default="stub", choices=["stub", "anthropic", "openai", "ollama"]
    )
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_span_traces.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    calc = SpanLoadCalculator(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )

    results: list[dict[str, Any]] = []
    for scenario in corpus:
        trace = scenario_to_trace(scenario)
        try:
            analysis = calc.run(trace)
        except Exception as exc:
            results.append({"id": scenario["id"], "error": str(exc), "composite": 0.0})
            continue
        score = score_analysis(analysis, scenario)
        results.append({"id": scenario["id"], "score": score})
        (out_dir / f"{scenario['id']}.analysis.md").write_text(analysis.to_markdown())

    summary = {
        "run_id": run_id,
        "client": args.client,
        "corpus_size": len(results),
        "scores": results,
        "corpus_composite_mean": round(
            sum(r.get("score", {}).get("composite", 0.0) for r in results) / max(1, len(results)),
            3,
        ),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"Benchmark complete. Run id: {run_id}")
    print(f"Corpus composite (mean): {summary['corpus_composite_mean']}")
    print(f"Results: {out_dir}")


if __name__ == "__main__":
    main()
