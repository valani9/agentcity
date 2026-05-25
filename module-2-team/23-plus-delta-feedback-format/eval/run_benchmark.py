"""Benchmark runner for the Plus/Delta Feedback Format generator."""

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
    from vstack.plus_delta import (
        FeedbackRequest,
        PlusDeltaFeedback,
        PlusDeltaFeedbackGenerator,
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


def scenario_to_request(scenario: dict[str, Any]) -> FeedbackRequest:
    r = scenario["request"]
    return FeedbackRequest(
        feedback_id=scenario["id"],
        reviewer_agent=r["reviewer_agent"],
        subject_agent=r["subject_agent"],
        task_context=r["task_context"],
        contribution_summary=r["contribution_summary"],
        contribution_artifact=r["contribution_artifact"],
        success_criteria=r.get("success_criteria", []),
        style=r.get("style", "balanced"),
    )


def score_feedback(feedback: PlusDeltaFeedback, scenario: dict[str, Any]) -> dict[str, Any]:
    expected_overall = scenario["expected_overall"]
    expected_min_plus = scenario["expected_min_plus"]
    expected_min_delta = scenario["expected_min_delta"]

    overall_match = feedback.overall_assessment == expected_overall
    plus_ok = len(feedback.plus_items) >= expected_min_plus
    delta_ok = len(feedback.delta_items) >= expected_min_delta

    composite = (
        (1.0 if overall_match else 0.0) * 0.5
        + (1.0 if plus_ok else 0.0) * 0.25
        + (1.0 if delta_ok else 0.0) * 0.25
    )
    return {
        "overall_match": overall_match,
        "plus_ok": plus_ok,
        "delta_ok": delta_ok,
        "composite": round(composite, 3),
        "actual_overall": feedback.overall_assessment,
        "actual_plus_count": len(feedback.plus_items),
        "actual_delta_count": len(feedback.delta_items),
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
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_feedback_requests.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    generator = PlusDeltaFeedbackGenerator(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )

    results: list[dict[str, Any]] = []
    for scenario in corpus:
        request = scenario_to_request(scenario)
        try:
            feedback = generator.run(request)
        except Exception as exc:
            results.append({"id": scenario["id"], "error": str(exc), "composite": 0.0})
            continue
        score = score_feedback(feedback, scenario)
        results.append({"id": scenario["id"], "score": score})
        (out_dir / f"{scenario['id']}.feedback.md").write_text(feedback.to_markdown())

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
