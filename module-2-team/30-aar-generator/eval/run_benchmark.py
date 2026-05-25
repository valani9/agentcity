"""
Synthetic-failure benchmark for the AAR Generator.

Loads `synthetic_failures.yaml`, runs the AAR Generator on each scenario,
and scores the resulting AAR on four dimensions:

  1. Pattern recall  - did the AAR surface the expected patterns?
  2. Anchor recall   - did the AAR cite the expected OB framework anchors?
  3. Intervention recall - did the AAR propose the expected intervention types?
  4. Wharton-section completeness - all four AAR sections populated and non-trivial?

Run with:

    # Using the stub client (deterministic, no API key):
    python eval/run_benchmark.py --client stub

    # Using a real LLM:
    vstack_LLM=anthropic python eval/run_benchmark.py --client anthropic
    vstack_LLM=openai    python eval/run_benchmark.py --client openai

Output: per-scenario scores + corpus-level summary in eval/results/<run_id>/.

Note: scoring is best-effort string matching for pattern names and anchor
substrings. A full LLM-grader implementation lives in the planned
`run_grader.py` (TODO).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError as e:
    raise SystemExit("PyYAML required to run the benchmark. Install: pip install pyyaml") from e

_HERE = Path(__file__).resolve().parent
_PATTERN_ROOT = _HERE.parent
sys.path.insert(0, str(_PATTERN_ROOT))

from lib.clients import (  # noqa: E402
    AnthropicClient,
    OllamaClient,
    OpenAIClient,
    StubClient,
)
from lib.generator import AARGenerator  # noqa: E402
from lib.schema import AAR, AgentTrace, TraceStep  # noqa: E402


def load_corpus(path: Path) -> list[dict[str, Any]]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["scenarios"]


def scenario_to_trace(scenario: dict[str, Any]) -> AgentTrace:
    base = datetime(2026, 5, 22, 12, 0, 0)
    steps: list[TraceStep] = []
    for i, step in enumerate(scenario["trace"]["steps"]):
        # YAML keeps optional fields like 'attempt' loose; preserve them in metadata.
        step_type = step.pop("type")
        content = step.pop("content")
        metadata = {k: v for k, v in step.items() if k not in {"type", "content"}}
        from datetime import timedelta

        steps.append(
            TraceStep(
                timestamp=base + timedelta(seconds=i * 5),
                type=step_type,
                content=content,
                metadata=metadata,
            )
        )
    t = scenario["trace"]
    return AgentTrace(
        agent_id=scenario["id"],
        agent_framework=t.get("agent_framework"),
        goal=t["goal"],
        steps=steps,
        outcome=t["outcome"],
        success=t["success"],
        retry_count=t.get("retry_count"),
    )


def score_aar(aar: AAR, scenario: dict[str, Any]) -> dict[str, Any]:
    """Score an AAR against the expected outputs declared in the YAML scenario.

    Returns per-dimension scores in [0, 1] plus a composite score.
    """
    expected_patterns = set(scenario.get("expected_patterns", []))
    expected_anchors = scenario.get("expected_framework_anchors", [])
    expected_interventions = set(scenario.get("expected_interventions", []))

    found_patterns = {lesson.pattern for lesson in aar.lessons}
    found_anchors = " ".join(lesson.framework_anchor for lesson in aar.lessons)
    found_interventions = {step.intervention_type for step in aar.next_steps}

    pattern_recall = len(expected_patterns & found_patterns) / max(1, len(expected_patterns))
    anchor_recall = sum(
        1 for a in expected_anchors if any(p in found_anchors for p in a.split(" - "))
    ) / max(1, len(expected_anchors))
    intervention_recall = len(expected_interventions & found_interventions) / max(
        1, len(expected_interventions)
    )

    sections_complete = all(
        [
            bool(aar.goal.strip()),
            bool(aar.results.strip()),
            len(aar.lessons) > 0,
            len(aar.next_steps) > 0,
        ]
    )

    composite = (
        pattern_recall * 0.35
        + anchor_recall * 0.25
        + intervention_recall * 0.25
        + (1.0 if sections_complete else 0.0) * 0.15
    )

    return {
        "pattern_recall": round(pattern_recall, 3),
        "anchor_recall": round(anchor_recall, 3),
        "intervention_recall": round(intervention_recall, 3),
        "sections_complete": sections_complete,
        "composite": round(composite, 3),
    }


def pick_client(name: str) -> object:
    name = name.lower()
    if name == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if name == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if name == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    # Stub returns empty AARs; benchmark will score zero. Useful for plumbing tests.
    return StubClient(["", "", "[]", "[]"] * 100)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client", default="stub", choices=["stub", "anthropic", "openai", "ollama"]
    )
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_failures.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    generator = AARGenerator(llm_client=client, model=getattr(client, "model", "stub"))

    results: list[dict[str, Any]] = []
    for scenario in corpus:
        trace = scenario_to_trace(scenario)
        aar = generator.generate(trace)
        score = score_aar(aar, scenario)
        results.append({"id": scenario["id"], "name": scenario["name"], "score": score})
        # Persist the AAR markdown next to the score for human inspection.
        (out_dir / f"{scenario['id']}.aar.md").write_text(aar.to_markdown())

    summary = {
        "run_id": run_id,
        "client": args.client,
        "corpus_size": len(results),
        "scores": results,
        "corpus_composite_mean": round(
            sum(r["score"]["composite"] for r in results) / max(1, len(results)), 3
        ),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"Benchmark complete. Run id: {run_id}")
    print(f"Corpus composite (mean): {summary['corpus_composite_mean']}")
    print(f"Per-scenario results in: {out_dir}")


if __name__ == "__main__":
    main()
