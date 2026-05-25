"""Benchmark runner for the Psychological Safety Detector."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as e:
    raise SystemExit("PyYAML required. Install: pip install pyyaml") from e

try:
    from vstack.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from vstack.psych_safety import (
        AgentMessage,
        MultiAgentSafetyTrace,
        PsychologicalSafetyDetection,
        PsychologicalSafetyDetector,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc

_HERE = Path(__file__).resolve().parent


def load_corpus(path: Path) -> list[dict[str, Any]]:
    with open(path) as f:
        return yaml.safe_load(f)["scenarios"]


def scenario_to_trace(scenario: dict[str, Any]) -> MultiAgentSafetyTrace:
    base = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)
    t = scenario["trace"]
    msgs = [
        AgentMessage(
            timestamp=base + timedelta(seconds=i * 5),
            from_agent=m["from_agent"],
            to_agent=m.get("to_agent"),
            content=m["content"],
            message_type=m["message_type"],
        )
        for i, m in enumerate(t["messages"])
    ]
    return MultiAgentSafetyTrace(
        team_id=scenario["id"],
        framework="benchmark-synthetic",
        goal=t["goal"],
        agents=t["agents"],
        messages=msgs,
        outcome=t["outcome"],
        success=t["success"],
    )


def score_detection(
    detection: PsychologicalSafetyDetection, scenario: dict[str, Any]
) -> dict[str, Any]:
    expected = scenario["expected_climate"]
    climate_match = detection.team_climate == expected
    composite = 1.0 if climate_match else 0.0
    return {
        "climate_match": climate_match,
        "composite": composite,
        "actual_climate": detection.team_climate,
        "safety_score": detection.safety_score,
        "behavior_scores": detection.behavior_scores,
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
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_safety_failures.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    detector = PsychologicalSafetyDetector(
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
