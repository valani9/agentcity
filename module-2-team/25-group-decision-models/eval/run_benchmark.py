"""Benchmark runner for the Group Decision Models generator."""

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
    from agentcity.group_decision import (
        DecisionOption,
        DecisionProtocol,
        DecisionProtocolGenerator,
        DecisionRequest,
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


def scenario_to_request(scenario: dict[str, Any]) -> DecisionRequest:
    r = scenario["request"]
    options = [
        DecisionOption(option_id=o["option_id"], description=o["description"]) for o in r["options"]
    ]
    return DecisionRequest(
        decision_id=scenario["id"],
        title=r["title"],
        options=options,
        agents=r["agents"],
        stakes=r["stakes"],
        reversibility=r.get("reversibility", "reversible"),
        time_pressure=r.get("time_pressure", "moderate"),
        expertise_asymmetry=r.get("expertise_asymmetry", "balanced"),
        regulatory_exposure=r.get("regulatory_exposure", False),
        buy_in_required=r.get("buy_in_required", False),
        forced_model=r.get("forced_model"),
    )


def score_protocol(protocol: DecisionProtocol, scenario: dict[str, Any]) -> dict[str, Any]:
    expected_model = scenario["expected_model"]

    model_match = protocol.recommended_model == expected_model
    has_steps = len(protocol.protocol_steps) >= 2
    has_threshold = bool(protocol.threshold.strip())

    composite = (
        (1.0 if model_match else 0.0) * 0.6
        + (1.0 if has_steps else 0.0) * 0.2
        + (1.0 if has_threshold else 0.0) * 0.2
    )
    return {
        "model_match": model_match,
        "has_steps": has_steps,
        "has_threshold": has_threshold,
        "composite": round(composite, 3),
        "actual_model": protocol.recommended_model,
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
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_decision_requests.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    generator = DecisionProtocolGenerator(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )

    results: list[dict[str, Any]] = []
    for scenario in corpus:
        request = scenario_to_request(scenario)
        try:
            protocol = generator.run(request)
        except Exception as exc:
            results.append({"id": scenario["id"], "error": str(exc), "composite": 0.0})
            continue
        score = score_protocol(protocol, scenario)
        results.append({"id": scenario["id"], "score": score})
        (out_dir / f"{scenario['id']}.protocol.md").write_text(protocol.to_markdown())

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
