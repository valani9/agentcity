"""Benchmark runner for the Process Gain/Loss Detector."""

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
    from agentcity.process_gain_loss import (
        IndividualBaseline,
        ProcessGainLossDetection,
        ProcessGainLossDetector,
        ProcessTrace,
        TeamResult,
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


def scenario_to_trace(scenario: dict[str, Any]) -> ProcessTrace:
    t = scenario["trace"]
    baselines = [
        IndividualBaseline(
            agent_name=b["agent_name"],
            output_summary=b["output_summary"],
            quality_score=b["quality_score"],
            cost_units=b.get("cost_units"),
        )
        for b in t["individual_baselines"]
    ]
    team = TeamResult(
        agents=t["team_result"]["agents"],
        output_summary=t["team_result"]["output_summary"],
        quality_score=t["team_result"]["quality_score"],
        cost_units=t["team_result"].get("cost_units"),
    )
    return ProcessTrace(
        trace_id=t.get("trace_id", scenario["id"]),
        task=t["task"],
        individual_baselines=baselines,
        team_result=team,
        interaction_log=t.get("interaction_log", ""),
        outcome=t["outcome"],
        success=t.get("success", False),
    )


def score_detection(
    detection: ProcessGainLossDetection, scenario: dict[str, Any]
) -> dict[str, Any]:
    expected_quality = scenario["expected_quality"]
    expected_factor = scenario.get("expected_dominant_factor")

    quality_match = detection.process_quality == expected_quality
    if expected_factor is None:
        factor_match = True
    else:
        # Top-scoring factor must match the expected dominant factor
        if detection.contributing_factors:
            top = max(detection.contributing_factors, key=lambda f: f.score)
            factor_match = top.factor == expected_factor
        else:
            factor_match = False

    composite = (1.0 if quality_match else 0.0) * 0.6 + (1.0 if factor_match else 0.0) * 0.4
    return {
        "quality_match": quality_match,
        "factor_match": factor_match,
        "composite": round(composite, 3),
        "actual_quality": detection.process_quality,
        "actual_top_factor": (
            max(detection.contributing_factors, key=lambda f: f.score).factor
            if detection.contributing_factors
            else None
        ),
        "gain_loss_score": detection.gain_loss_score,
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
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_process_failures.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    detector = ProcessGainLossDetector(
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
