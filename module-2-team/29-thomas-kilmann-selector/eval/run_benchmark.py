"""Benchmark runner for the Thomas-Kilmann Conflict Style Selector."""

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
    from vstack.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from vstack.thomas_kilmann import (
        AgentInteractionTrace,
        ConflictStyleSelection,
        ConflictStyleSelector,
        InteractionTurn,
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


def scenario_to_trace(scenario: dict[str, Any]) -> AgentInteractionTrace:
    t = scenario["trace"]
    turns = [InteractionTurn(role=turn["role"], content=turn["content"]) for turn in t["turns"]]
    return AgentInteractionTrace(
        agent_id=scenario["id"],
        model_name=t.get("model_name", "benchmark-synthetic"),
        task=t["task"],
        task_category=t.get("task_category"),
        turns=turns,
        outcome=t["outcome"],
        success=t["success"],
    )


def score_selection(selection: ConflictStyleSelection, scenario: dict[str, Any]) -> dict[str, Any]:
    expected_observed = scenario["expected_observed"]
    expected_optimal = scenario["expected_optimal"]
    observed_match = selection.observed_style == expected_observed
    optimal_match = selection.optimal_style == expected_optimal
    composite = (1.0 if observed_match else 0.0) * 0.5 + (1.0 if optimal_match else 0.0) * 0.5
    return {
        "observed_match": observed_match,
        "optimal_match": optimal_match,
        "composite": round(composite, 3),
        "actual_observed": selection.observed_style,
        "actual_optimal": selection.optimal_style,
        "style_mismatch": selection.style_mismatch,
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
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_style_mismatches.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    selector = ConflictStyleSelector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )

    results: list[dict[str, Any]] = []
    for scenario in corpus:
        trace = scenario_to_trace(scenario)
        try:
            selection = selector.run(trace)
        except Exception as exc:
            results.append({"id": scenario["id"], "error": str(exc), "composite": 0.0})
            continue
        score = score_selection(selection, scenario)
        results.append({"id": scenario["id"], "score": score})
        (out_dir / f"{scenario['id']}.selection.md").write_text(selection.to_markdown())

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
