"""Benchmark runner for the SMART Goal Generator."""

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
    from agentcity.smart_goal import GoalRequest, SMARTGoal, SMARTGoalGenerator
except ImportError as exc:
    raise SystemExit(
        "agentcity not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc

_HERE = Path(__file__).resolve().parent


def load_corpus(path: Path) -> list[dict[str, Any]]:
    with open(path) as f:
        return yaml.safe_load(f)["scenarios"]


def scenario_to_request(scenario: dict[str, Any]) -> GoalRequest:
    r = scenario["request"]
    return GoalRequest(
        goal_id=scenario["id"],
        vague_goal=r["vague_goal"],
        context=r.get("context", ""),
        available_resources=r.get("available_resources", []),
        known_constraints=r.get("known_constraints", []),
        deadline_hint=r.get("deadline_hint") or None,
        framework=r.get("framework"),
    )


def score_goal(goal: SMARTGoal, scenario: dict[str, Any]) -> dict[str, Any]:
    expected_quality = scenario["expected_quality"]
    expected_min_kill = scenario["expected_min_kill_criteria"]

    quality_match = goal.smart_quality == expected_quality
    kill_ok = len(goal.kill_criteria) >= expected_min_kill
    has_completion = len(goal.completion_criteria) > 0
    has_metrics = len(goal.success_metrics) > 0

    composite = (
        (1.0 if quality_match else 0.0) * 0.4
        + (1.0 if kill_ok else 0.0) * 0.3
        + (1.0 if has_completion else 0.0) * 0.15
        + (1.0 if has_metrics else 0.0) * 0.15
    )
    return {
        "quality_match": quality_match,
        "kill_criteria_ok": kill_ok,
        "has_completion": has_completion,
        "has_metrics": has_metrics,
        "composite": round(composite, 3),
        "actual_quality": goal.smart_quality,
        "overall_score": goal.overall_smart_score,
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
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_smart_requests.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    generator = SMARTGoalGenerator(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )

    results: list[dict[str, Any]] = []
    for scenario in corpus:
        request = scenario_to_request(scenario)
        try:
            goal = generator.run(request)
        except Exception as exc:
            results.append({"id": scenario["id"], "error": str(exc), "composite": 0.0})
            continue
        score = score_goal(goal, scenario)
        results.append({"id": scenario["id"], "score": score})
        (out_dir / f"{scenario['id']}.goal.md").write_text(goal.to_markdown())

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
