"""Benchmark runner for the Yerkes-Dodson Optimal Workload Diagnostic."""

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
    from agentcity.yerkes_dodson import (
        AgentPerformanceTrace,
        PressureInputs,
        WorkloadDetection,
        WorkloadDetector,
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


def scenario_to_trace(scenario: dict[str, Any]) -> AgentPerformanceTrace:
    t = scenario["trace"]
    p = t.get("pressure", {})
    pressure = PressureInputs(
        deadline_pressure=p.get("deadline_pressure", "moderate"),
        budget_pressure=p.get("budget_pressure", "moderate"),
        retry_cap=p.get("retry_cap"),
        error_visibility=p.get("error_visibility", "medium"),
        task_complexity=p.get("task_complexity", "moderate"),
    )
    return AgentPerformanceTrace(
        agent_id=scenario["id"],
        task=t["task"],
        pressure=pressure,
        observed_behaviors=t["observed_behaviors"],
        outcome=t["outcome"],
        success=t.get("success", False),
    )


def score_detection(detection: WorkloadDetection, scenario: dict[str, Any]) -> dict[str, Any]:
    expected_zone = scenario["expected_zone"]
    expected_failure = scenario["expected_failure"]

    zone_match = detection.observed_zone == expected_zone
    failure_match = detection.failure_mode == expected_failure

    composite = (1.0 if zone_match else 0.0) * 0.5 + (1.0 if failure_match else 0.0) * 0.5
    return {
        "zone_match": zone_match,
        "failure_match": failure_match,
        "composite": round(composite, 3),
        "actual_zone": detection.observed_zone,
        "actual_failure": detection.failure_mode,
        "distance_from_optimal": detection.distance_from_optimal,
    }


def pick_client(name: str) -> object:
    name = name.lower()
    if name == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if name == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if name == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient(["{}"] * 100)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client", default="stub", choices=["stub", "anthropic", "openai", "ollama"]
    )
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_workload_failures.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    detector = WorkloadDetector(
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
