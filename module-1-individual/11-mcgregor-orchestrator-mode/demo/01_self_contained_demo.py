"""Self-contained demo of the McGregor Theory X/Y Orchestrator Mode diagnostic.

Synthetic scenario: an orchestrator runs a single proven sub-agent that
handles routine PR test-running. The orchestrator is in TIGHT Theory-X
mode — it requires pre-approval before every test execution, checks in
after every step, and intervenes mid-run if the agent so much as
re-orders fixtures. The task is low-risk, routine, reversible, and the
agent has a clean track record. The result: every test cycle is 5x
slower than it could be because the orchestrator overhead dominates.

Theory-X on Theory-Y-appropriate tasks wastes cycles. The diagnostic
recommends loosening oversight + removing pre-approval gates.

Run with the stub client (no API key required):

    python demo/01_self_contained_demo.py

Run with a real LLM:

    vstack_LLM=anthropic python demo/01_self_contained_demo.py
"""

from __future__ import annotations

import json
import os

try:
    from vstack.aar.clients import (
        AnthropicClient,
        OllamaClient,
        OpenAIClient,
        StubClient,
    )
    from vstack.mcgregor import (
        OrchestratorModeDetector,
        OrchestratorStep,
        OrchestratorTrace,
        TaskProperties,
    )
except ImportError as exc:
    raise SystemExit(
        "vstack not installed. Run: pip install -e . from the repo root.\n"
        f"(Original import error: {exc})"
    ) from exc


def build_trace() -> OrchestratorTrace:
    steps = [
        OrchestratorStep(
            step_type="delegate",
            actor="orchestrator",
            sub_agent="runner-1",
            content=(
                "I am authorizing you to begin pre-test setup. Do not proceed past the "
                "setup phase until I approve."
            ),
        ),
        OrchestratorStep(
            step_type="observation",
            actor="agent",
            sub_agent="runner-1",
            content="Pre-test setup complete. Awaiting approval.",
        ),
        OrchestratorStep(
            step_type="approve",
            actor="orchestrator",
            sub_agent="runner-1",
            content="Approved. You may now execute test step 1.",
        ),
        OrchestratorStep(
            step_type="observation",
            actor="agent",
            sub_agent="runner-1",
            content="Test step 1 complete. Result: pass. Awaiting next instruction.",
        ),
        OrchestratorStep(
            step_type="approve",
            actor="orchestrator",
            sub_agent="runner-1",
            content="Approved. Execute step 2.",
        ),
        OrchestratorStep(
            step_type="observation",
            actor="agent",
            sub_agent="runner-1",
            content="Step 2 complete. Pass. Awaiting next instruction.",
        ),
        OrchestratorStep(
            step_type="approve",
            actor="orchestrator",
            sub_agent="runner-1",
            content="Approved. Execute step 3.",
        ),
        OrchestratorStep(
            step_type="intervene",
            actor="orchestrator",
            sub_agent="runner-1",
            content=(
                "Wait — you ordered the fixtures alphabetically. Re-order them in the "
                "explicit list order. Do not proceed until reordered."
            ),
        ),
        OrchestratorStep(
            step_type="observation",
            actor="agent",
            sub_agent="runner-1",
            content="Reordered. Awaiting approval.",
        ),
        OrchestratorStep(
            step_type="approve",
            actor="orchestrator",
            sub_agent="runner-1",
            content="Approved. Continue.",
        ),
    ]
    return OrchestratorTrace(
        trace_id="demo-ci-runner-001",
        task="Run the integration test suite on the latest PR and report pass/fail.",
        sub_agents=["runner-1"],
        task_properties=TaskProperties(
            risk_level="low",
            complexity="routine",
            reversibility="reversible",
            regulatory_exposure=False,
            agent_capability="proven",
        ),
        steps=steps,
        outcome=(
            "Test run completed correctly. End-to-end wall-clock time was 5x the "
            "single-agent baseline because the orchestrator required pre-approval on "
            "every test step and intervened mid-run for cosmetic fixture ordering. The "
            "agent did the work correctly; the orchestrator overhead dominated cost."
        ),
        success=True,
    )


def stub_responses() -> list[str]:
    mode = json.dumps(
        {
            "observed_mode": "theory_x",
            "optimal_mode": "theory_y",
            "mode_mismatch": 0.8,
            "indicators": {
                "check_in_frequency": 0.9,
                "autonomy_granted": 0.1,
                "pre_approval_required": 0.9,
                "intervention_rate": 0.4,
                "explanation": (
                    "Orchestrator required pre-approval before every step (9 of the 10 "
                    "trace steps include an orchestrator check-in or approval). Autonomy "
                    "granted to the proven sub-agent was minimal. One mid-run "
                    "intervention was cosmetic (fixture ordering)."
                ),
                "evidence_quotes": [
                    "Orchestrator: 'Approved. Execute step 2.' (repeated for every step)",
                    "Orchestrator: 'Wait — you ordered the fixtures alphabetically. Re-order them.'",
                ],
            },
            "mode_quality": "severe-mismatch",
            "rationale": (
                "Task is low-risk, routine, reversible, and assigned to a proven agent. "
                "Theory-Y would have completed the task at 1x baseline cost. Theory-X "
                "added 5x overhead with no risk-mitigation benefit because there was "
                "no meaningful risk to mitigate."
            ),
        }
    )
    interventions = json.dumps(
        [
            {
                "target_mode": "theory_y",
                "intervention_type": "remove_pre_approval_gates",
                "description": (
                    "Drop pre-approval requirements for routine test execution on this "
                    "agent's known-good test suite."
                ),
                "suggested_implementation": (
                    "Orchestration config: set `require_pre_approval=False` for "
                    "agent runner-1 on tasks tagged 'routine_test_run'. Keep pre-approval "
                    "for tasks tagged 'database_migration' or 'production_deploy'."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Directly removes the 5x overhead. Proven agent on reversible task "
                    "does not need step-by-step approval."
                ),
            },
            {
                "target_mode": "theory_y",
                "intervention_type": "decrease_check_in_cadence",
                "description": ("Change from per-step check-ins to per-run summary check-ins."),
                "suggested_implementation": (
                    "Orchestration config: orchestrator receives a single end-of-run "
                    "summary from the agent. Intermediate steps do not trigger check-ins."
                ),
                "estimated_impact": "high",
                "rationale": (
                    "Eliminates the polling pattern that drove overhead. Orchestrator "
                    "still gets the information it needs (pass/fail + summary)."
                ),
            },
            {
                "target_mode": "hybrid",
                "intervention_type": "add_risk_classifier",
                "description": (
                    "Add a pre-task risk classifier that selects Theory-X or Theory-Y "
                    "based on the specific task being run."
                ),
                "suggested_implementation": (
                    "Pipeline step: before each task, a classifier emits "
                    "`{risk: low|medium|high, reversibility: ...}` and the orchestrator "
                    "uses these to decide oversight mode. Default to Theory-Y on low risk."
                ),
                "estimated_impact": "medium",
                "rationale": (
                    "Structural fix that survives task-type changes. Avoids the "
                    "alternative failure mode (Theory-Y on truly risky tasks)."
                ),
            },
        ]
    )
    return [mode, interventions]


def pick_client() -> object:
    choice = os.environ.get("vstack_LLM", "stub").lower()
    if choice == "anthropic":
        return AnthropicClient(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    if choice == "openai":
        return OpenAIClient(model=os.environ.get("OPENAI_MODEL", "gpt-5"))
    if choice == "ollama":
        return OllamaClient(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"))
    return StubClient(stub_responses())


def main() -> None:
    trace = build_trace()
    client = pick_client()
    detector = OrchestratorModeDetector(
        llm_client=client,  # type: ignore[arg-type]
        model=getattr(client, "model", "stub"),
    )
    detection = detector.run(trace)
    print(detection.to_markdown())


if __name__ == "__main__":
    main()
