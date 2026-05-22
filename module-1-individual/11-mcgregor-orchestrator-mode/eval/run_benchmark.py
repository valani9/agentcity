"""Benchmark runner for the McGregor Theory X/Y Orchestrator Mode diagnostic."""

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
    from agentcity.mcgregor import (
        OrchestratorModeDetection,
        OrchestratorModeDetector,
        OrchestratorStep,
        OrchestratorTrace,
        TaskProperties,
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


def scenario_to_trace(scenario: dict[str, Any]) -> OrchestratorTrace:
    t = scenario["trace"]
    props = TaskProperties(
        risk_level=t["task_properties"]["risk_level"],
        complexity=t["task_properties"]["complexity"],
        reversibility=t["task_properties"].get("reversibility", "reversible"),
        regulatory_exposure=t["task_properties"].get("regulatory_exposure", False),
        agent_capability=t["task_properties"].get("agent_capability", "moderate"),
    )
    steps = [
        OrchestratorStep(
            step_type=s["step_type"],
            actor=s["actor"],
            sub_agent=s.get("sub_agent"),
            content=s["content"],
        )
        for s in t["steps"]
    ]
    return OrchestratorTrace(
        trace_id=t.get("trace_id", scenario["id"]),
        task=t["task"],
        sub_agents=t["sub_agents"],
        task_properties=props,
        steps=steps,
        outcome=t["outcome"],
        success=t.get("success", False),
    )


def score_detection(
    detection: OrchestratorModeDetection, scenario: dict[str, Any]
) -> dict[str, Any]:
    expected_observed = scenario["expected_observed"]
    expected_optimal = scenario["expected_optimal"]
    expected_quality = scenario["expected_quality"]

    observed_match = detection.observed_mode == expected_observed
    optimal_match = detection.optimal_mode == expected_optimal
    quality_match = detection.mode_quality == expected_quality

    composite = (
        (1.0 if observed_match else 0.0) * 0.4
        + (1.0 if optimal_match else 0.0) * 0.3
        + (1.0 if quality_match else 0.0) * 0.3
    )
    return {
        "observed_match": observed_match,
        "optimal_match": optimal_match,
        "quality_match": quality_match,
        "composite": round(composite, 3),
        "actual_observed": detection.observed_mode,
        "actual_optimal": detection.optimal_mode,
        "actual_quality": detection.mode_quality,
        "mode_mismatch": detection.mode_mismatch,
    }


def pick_client(name: str) -> object:
    name = name.lower()
    if name == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if name == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if name == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient(["{}", "[]"] * 100)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client", default="stub", choices=["stub", "anthropic", "openai", "ollama"]
    )
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_orchestrator_failures.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    detector = OrchestratorModeDetector(
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
