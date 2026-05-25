"""Regenerate the canonical Span-of-Control baselines committed to the repo.

Run from the repo root:

    python _baselines/scripts/generate_canonical.py

The patterns whose math is fully deterministic (no LLM in the
metrics) end up with reproducible JSON output here; everything else
is documented in ``_baselines/README.md`` with a per-pattern recipe
for users to generate their own.
"""

from __future__ import annotations

import sys
from pathlib import Path

from vstack.aar import StubClient
from vstack.span_of_control import AgentNode, CrewLoadTrace, SpanLoadCalculator

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "_baselines" / "canonical"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stub = StubClient([])
    calc_quick = SpanLoadCalculator(stub, mode="quick")

    cases = [
        (
            "span_of_control_small_flat.json",
            CrewLoadTrace(
                crew_id="canonical-small-flat",
                task="Three-agent peer crew under moderate load.",
                agents=[
                    AgentNode(agent_id="orchestrator", decision_authority="full"),
                    AgentNode(
                        agent_id="worker-1",
                        reports_to=["orchestrator"],
                        decision_authority="advisory",
                    ),
                    AgentNode(
                        agent_id="worker-2",
                        reports_to=["orchestrator"],
                        decision_authority="advisory",
                    ),
                ],
                incoming_request_rate=10.0,
                outcome="Comfortable handling.",
                success=True,
            ),
        ),
        (
            "span_of_control_hub_and_spoke.json",
            CrewLoadTrace(
                crew_id="canonical-hub-and-spoke",
                task="One orchestrator routing to 12 workers under high load.",
                agents=[
                    AgentNode(agent_id="orchestrator", decision_authority="full"),
                    *[
                        AgentNode(
                            agent_id=f"worker-{i}",
                            reports_to=["orchestrator"],
                            decision_authority="advisory",
                        )
                        for i in range(12)
                    ],
                ],
                incoming_request_rate=100.0,
                outcome="Throughput collapsed; orchestrator queue saturated.",
                success=False,
            ),
        ),
        (
            "span_of_control_two_layer.json",
            CrewLoadTrace(
                crew_id="canonical-two-layer",
                task="Two-layer hierarchy: orchestrator -> 3 team leads -> 9 workers.",
                agents=[
                    AgentNode(agent_id="orchestrator", decision_authority="full"),
                    AgentNode(
                        agent_id="lead-A",
                        reports_to=["orchestrator"],
                        decision_authority="partial",
                    ),
                    AgentNode(
                        agent_id="lead-B",
                        reports_to=["orchestrator"],
                        decision_authority="partial",
                    ),
                    AgentNode(
                        agent_id="lead-C",
                        reports_to=["orchestrator"],
                        decision_authority="partial",
                    ),
                    *[
                        AgentNode(
                            agent_id=f"worker-A{i}",
                            reports_to=["lead-A"],
                            decision_authority="advisory",
                        )
                        for i in range(3)
                    ],
                    *[
                        AgentNode(
                            agent_id=f"worker-B{i}",
                            reports_to=["lead-B"],
                            decision_authority="advisory",
                        )
                        for i in range(3)
                    ],
                    *[
                        AgentNode(
                            agent_id=f"worker-C{i}",
                            reports_to=["lead-C"],
                            decision_authority="advisory",
                        )
                        for i in range(3)
                    ],
                ],
                incoming_request_rate=50.0,
                outcome="Balanced load handling.",
                success=True,
            ),
        ),
    ]

    for filename, trace in cases:
        analysis = calc_quick.run(trace)
        out_path = OUT_DIR / filename
        out_path.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
        print(
            f"wrote {out_path.relative_to(REPO_ROOT)}  "
            f"(profile={analysis.profile_pattern}, severity={analysis.severity})"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
