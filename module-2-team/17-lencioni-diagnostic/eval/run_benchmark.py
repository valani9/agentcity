"""
Benchmark runner for the Lencioni Diagnostic.

Loads synthetic_multiagent_failures.yaml, runs the diagnostic on each
scenario, and scores recall on:

  - Dominant-dysfunction match (the expected dominant dysfunction is
    surfaced as the actual dominant)
  - Team-health label match
  - Per-dysfunction score reasonableness (the expected dysfunction has
    a score >= 0.5)

Real-LLM runs produce meaningful scores. Stub-client runs return zero
across the board — useful for plumbing checks but not diagnostic quality.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as e:
    raise SystemExit("PyYAML required. Install: pip install pyyaml") from e

_HERE = Path(__file__).resolve().parent
_PATTERN_ROOT = _HERE.parent
sys.path.insert(0, str(_PATTERN_ROOT))

# Reuse the AAR Generator's clients module
_AAR_LIB = _PATTERN_ROOT.parent / "30-aar-generator" / "lib"
sys.path.insert(0, str(_AAR_LIB))

from clients import (  # noqa: E402
    AnthropicClient,
    OllamaClient,
    OpenAIClient,
    StubClient,
)
from lib.generator import LencioniDiagnostic  # noqa: E402
from lib.schema import AgentMessage, LencioniDiagnosis, MultiAgentTrace  # noqa: E402


def load_corpus(path: Path) -> list[dict[str, Any]]:
    with open(path) as f:
        return yaml.safe_load(f)["scenarios"]


def scenario_to_trace(scenario: dict[str, Any]) -> MultiAgentTrace:
    base = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)
    msgs: list[AgentMessage] = []
    for i, m in enumerate(scenario["trace"]["messages"]):
        msgs.append(
            AgentMessage(
                timestamp=base + timedelta(seconds=i * 5),
                from_agent=m["from_agent"],
                to_agent=m.get("to_agent"),
                content=m["content"],
                message_type=m["message_type"],
            )
        )
    t = scenario["trace"]
    return MultiAgentTrace(
        team_id=scenario["id"],
        framework="benchmark-synthetic",
        goal=t["goal"],
        agents=t["agents"],
        messages=msgs,
        outcome=t["outcome"],
        success=t["success"],
    )


def score_diagnosis(diagnosis: LencioniDiagnosis, scenario: dict[str, Any]) -> dict[str, Any]:
    expected_dominant = scenario["expected_dominant"]
    expected_health = scenario["expected_team_health"]

    dominant_match = diagnosis.dominant_dysfunction == expected_dominant
    health_match = diagnosis.overall_team_health == expected_health

    if expected_dominant == "none-observed":
        score_reasonable = max(diagnosis.pyramid_score.values()) < 0.4
    else:
        expected_score = diagnosis.pyramid_score.get(expected_dominant, 0.0)
        score_reasonable = expected_score >= 0.5

    composite = (
        (1.0 if dominant_match else 0.0) * 0.5
        + (1.0 if health_match else 0.0) * 0.25
        + (1.0 if score_reasonable else 0.0) * 0.25
    )
    return {
        "dominant_match": dominant_match,
        "health_match": health_match,
        "score_reasonable": score_reasonable,
        "composite": round(composite, 3),
        "actual_dominant": diagnosis.dominant_dysfunction,
        "actual_health": diagnosis.overall_team_health,
        "pyramid_score": diagnosis.pyramid_score,
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
        "--client",
        default="stub",
        choices=["stub", "anthropic", "openai", "ollama"],
    )
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_multiagent_failures.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    diagnostic = LencioniDiagnostic(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )

    results: list[dict[str, Any]] = []
    for scenario in corpus:
        trace = scenario_to_trace(scenario)
        try:
            diagnosis = diagnostic.run(trace)
        except Exception as exc:
            results.append({"id": scenario["id"], "error": str(exc), "composite": 0.0})
            continue
        score = score_diagnosis(diagnosis, scenario)
        results.append({"id": scenario["id"], "score": score})
        (out_dir / f"{scenario['id']}.diagnosis.md").write_text(diagnosis.to_markdown())

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
