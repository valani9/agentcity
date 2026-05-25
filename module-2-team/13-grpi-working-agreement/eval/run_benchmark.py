"""Benchmark runner for the GRPI Working Agreement Generator.

Loads synthetic_grpi_requests.yaml and scores generated agreements on:

  - Goals section non-trivial (≥1 success criterion, primary goal present)
  - Roles section non-trivial (every requested agent has a role assignment)
  - Processes section non-trivial (decision protocol + escalation present)
  - Interactions section non-trivial (≥1 disagreement norm)
  - Validation errors raised when expected

Real-LLM runs produce meaningful, varied agreements. Stub-client runs
return empty (the benchmark stub returns "{}") and score zero.
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
    from vstack.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from vstack.grpi import (
        AgentRole,
        GRPIWorkingAgreementGenerator,
        TeamSetupRequest,
        WorkingAgreement,
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


def scenario_to_request(scenario: dict[str, Any]) -> TeamSetupRequest:
    r = scenario["request"]
    agents = [AgentRole(name=a["name"], description=a.get("description", "")) for a in r["agents"]]
    return TeamSetupRequest(
        team_id=r.get("team_id"),
        task=r["task"],
        agents=agents,
        constraints=r.get("constraints", []),
        success_criteria=r.get("success_criteria", []),
        kill_criteria=r.get("kill_criteria", []),
    )


def score_agreement(agreement: WorkingAgreement, scenario: dict[str, Any]) -> dict[str, Any]:
    requested_agents = {a["name"] for a in scenario["request"]["agents"]}
    assigned_agents = {ra.agent_name for ra in agreement.roles.role_assignments}

    goals_ok = bool(
        agreement.goals.primary_goal.strip()
        and len(agreement.goals.measurable_success_criteria) >= 1
    )
    roles_ok = requested_agents.issubset(assigned_agents) and all(
        len(ra.responsibilities) >= 1 for ra in agreement.roles.role_assignments
    )
    processes_ok = bool(
        agreement.processes.decision_protocol.strip()
        and len(agreement.processes.escalation_path) >= 1
        and len(agreement.processes.abandonment_criteria) >= 1
    )
    interactions_ok = len(agreement.interactions.disagreement_norms) >= 1 and bool(
        agreement.interactions.feedback_format.strip()
    )

    composite = (goals_ok + roles_ok + processes_ok + interactions_ok) / 4.0
    return {
        "goals_ok": goals_ok,
        "roles_ok": roles_ok,
        "processes_ok": processes_ok,
        "interactions_ok": interactions_ok,
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
    return StubClient(["{}"] * 100)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client", default="stub", choices=["stub", "anthropic", "openai", "ollama"]
    )
    parser.add_argument("--corpus", default=str(_HERE / "synthetic_grpi_requests.yaml"))
    parser.add_argument("--out", default=str(_HERE / "results"))
    args = parser.parse_args()

    corpus = load_corpus(Path(args.corpus))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.client}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    client = pick_client(args.client)
    generator = GRPIWorkingAgreementGenerator(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )

    results: list[dict[str, Any]] = []
    for scenario in corpus:
        expect_error = scenario["request"].get("expect_validation_error", False)
        try:
            request = scenario_to_request(scenario)
            agreement = generator.generate(request)
        except ValueError as exc:
            if expect_error:
                results.append(
                    {
                        "id": scenario["id"],
                        "score": {"composite": 1.0, "validation_caught_expected_error": True},
                    }
                )
            else:
                results.append({"id": scenario["id"], "error": str(exc), "composite": 0.0})
            continue
        if expect_error:
            results.append(
                {
                    "id": scenario["id"],
                    "error": "expected validation error but generation succeeded",
                    "composite": 0.0,
                }
            )
            continue
        score = score_agreement(agreement, scenario)
        results.append({"id": scenario["id"], "score": score})
        (out_dir / f"{scenario['id']}.agreement.md").write_text(agreement.to_markdown())

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
