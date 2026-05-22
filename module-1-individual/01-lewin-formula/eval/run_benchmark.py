"""Benchmark runner for the Lewin Formula Diagnostic."""

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
    from agentcity.lewin import (
        AgentFailureTrace,
        EnvironmentalFactor,
        FailureStep,
        IndividualFactor,
        LewinAttributionDetector,
        LewinDetection,
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


def scenario_to_trace(scenario: dict[str, Any]) -> AgentFailureTrace:
    t = scenario["trace"]
    steps = [FailureStep(type=s["type"], content=s["content"]) for s in t["steps"]]
    individual = [
        IndividualFactor(factor=f["factor"], description=f["description"])
        for f in t.get("individual_factors", [])
    ]
    environmental = [
        EnvironmentalFactor(factor=f["factor"], description=f["description"])
        for f in t.get("environmental_factors", [])
    ]
    return AgentFailureTrace(
        agent_id=scenario["id"],
        model_name=t.get("model_name", "benchmark-synthetic"),
        task=t["task"],
        steps=steps,
        outcome=t["outcome"],
        success=t.get("success", False),
        individual_factors=individual,
        environmental_factors=environmental,
        initial_attribution=t.get("initial_attribution"),
    )


def score_detection(detection: LewinDetection, scenario: dict[str, Any]) -> dict[str, Any]:
    expected_dominant = scenario["expected_dominant"]
    expected_quality = scenario["expected_quality"]

    dominant_match = detection.dominant_locus == expected_dominant
    quality_match = detection.attribution_quality == expected_quality

    if expected_dominant == "indeterminate":
        score_reasonable = max(detection.locus_scores.values()) < 0.4
    else:
        expected_score = detection.locus_scores.get(expected_dominant, 0.0)
        score_reasonable = expected_score >= 0.5

    composite = (
        (1.0 if dominant_match else 0.0) * 0.5
        + (1.0 if quality_match else 0.0) * 0.25
        + (1.0 if score_reasonable else 0.0) * 0.25
    )
    return {
        "dominant_match": dominant_match,
        "quality_match": quality_match,
        "score_reasonable": score_reasonable,
        "composite": round(composite, 3),
        "actual_dominant": detection.dominant_locus,
        "actual_quality": detection.attribution_quality,
        "locus_scores": detection.locus_scores,
    }


def pick_client(name: str) -> object:
    name = name.lower()
    if name == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if name == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if name == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient(["[]", "[]"] * 100)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client", default="stub", choices=["stub", "anthropic", "openai", "ollama"]
    )
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_lewin_failures.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    detector = LewinAttributionDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )

    results: list[dict[str, Any]] = []
    for scenario in corpus:
        trace = scenario_to_trace(scenario)
        try:
            detection = detector.run(trace)
        except Exception as exc:
            results.append({"id": scenario["id"], "error": str(exc), "composite": 0.0})
            continue
        score = score_detection(detection, scenario)
        results.append({"id": scenario["id"], "score": score})
        (out_dir / f"{scenario['id']}.detection.md").write_text(detection.to_markdown())

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
