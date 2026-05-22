"""Benchmark runner for the Johari Window Self-Audit.

Loads synthetic_johari_failures.yaml, runs the audit on each scenario,
and scores recall on:

  - Dominant-quadrant match
  - Self-awareness score is in the expected range for the scenario

Real-LLM runs produce meaningful scores. Stub-client runs return zero
across the board.
"""

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
    from agentcity.johari import (
        AgentSelfReportTrace,
        InteractionTurn,
        JohariSelfAudit,
        JohariSelfAuditor,
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


def scenario_to_trace(scenario: dict[str, Any]) -> AgentSelfReportTrace:
    t = scenario["trace"]
    turns = [InteractionTurn(role=turn["role"], content=turn["content"]) for turn in t["turns"]]
    return AgentSelfReportTrace(
        agent_id=scenario["id"],
        model_name=t.get("model_name", "benchmark-synthetic"),
        task=t["task"],
        turns=turns,
        self_report=t["self_report"],
        outcome=t["outcome"],
        success=t["success"],
    )


def score_audit(audit: JohariSelfAudit, scenario: dict[str, Any]) -> dict[str, Any]:
    expected = scenario["expected_dominant"]
    dominant_match = audit.dominant_quadrant == expected

    # Self-awareness reasonableness: OPEN scenarios should be high; BLIND
    # and UNKNOWN scenarios should be low; HIDDEN scenarios mid.
    awareness_ok = True
    if expected == "open":
        awareness_ok = audit.self_awareness_score >= 0.6
    elif expected == "blind":
        awareness_ok = audit.self_awareness_score <= 0.5
    elif expected == "hidden":
        awareness_ok = 0.3 <= audit.self_awareness_score <= 0.8
    elif expected == "unknown":
        awareness_ok = audit.self_awareness_score <= 0.6

    composite = (1.0 if dominant_match else 0.0) * 0.7 + (1.0 if awareness_ok else 0.0) * 0.3
    return {
        "dominant_match": dominant_match,
        "awareness_ok": awareness_ok,
        "composite": round(composite, 3),
        "actual_dominant": audit.dominant_quadrant,
        "self_awareness_score": audit.self_awareness_score,
        "quadrant_weights": audit.quadrant_weights,
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
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_johari_failures.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    auditor = JohariSelfAuditor(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )

    results: list[dict[str, Any]] = []
    for scenario in corpus:
        trace = scenario_to_trace(scenario)
        try:
            audit = auditor.run(trace)
        except Exception as exc:
            results.append({"id": scenario["id"], "error": str(exc), "composite": 0.0})
            continue
        score = score_audit(audit, scenario)
        results.append({"id": scenario["id"], "score": score})
        (out_dir / f"{scenario['id']}.audit.md").write_text(audit.to_markdown())

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
