"""LangGraph demo -- chain AAR -> Lewin in a two-node state graph.

Run:
    pip install 'valanistack[anthropic,langgraph]'
    export ANTHROPIC_API_KEY="sk-ant-..."
    python examples/langgraph_demo.py

State shape:
    {
      "trace": {...},                # AAR input
      "vstack_aar": {...},           # AAR detection (written by aar_node)
      "vstack_lewin": {...}          # Lewin detection (written by lewin_node)
    }

The AAR node consumes state["trace"] and writes state["vstack_aar"];
the Lewin node remaps the trace into AgentFailureTrace shape and
writes state["vstack_lewin"].
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from vstack.adapters.langgraph import node_for


class State(TypedDict, total=False):
    trace: dict[str, Any]
    vstack_aar: dict[str, Any]
    vstack_lewin: dict[str, Any]


def lewin_from_aar(state: State) -> State:
    """Build the Lewin input from the AAR trace + AAR detection.

    AgentTrace and AgentFailureTrace share most fields but Lewin
    needs ``agent_id``, ``model_name``, ``initial_attribution`` and
    typed ``FailureStep`` records.
    """
    aar_trace = state.get("trace") or {}
    aar_detection = state.get("vstack_aar") or {}
    return {
        "trace_for_lewin": {
            "agent_id": "demo-agent",
            "model_name": "claude-opus-4-7",
            "task": aar_trace.get("goal", ""),
            "steps": [
                {"type": s.get("type"), "content": s.get("content", "")}
                for s in aar_trace.get("steps", [])
            ],
            "outcome": aar_trace.get("outcome", ""),
            "success": aar_trace.get("success", False),
            "initial_attribution": aar_detection.get("trace_quality_audit", {}).get(
                "summary", "unknown"
            )[:200],
        }
    }


def main() -> None:
    aar_node = node_for("aar", state_key="trace", output_key_prefix="vstack_")
    lewin_node = node_for("lewin", state_key="trace_for_lewin", output_key_prefix="vstack_")

    graph = StateGraph(State)
    graph.add_node("aar", aar_node)
    graph.add_node("remap_for_lewin", lewin_from_aar)
    graph.add_node("lewin", lewin_node)

    graph.set_entry_point("aar")
    graph.add_edge("aar", "remap_for_lewin")
    graph.add_edge("remap_for_lewin", "lewin")
    graph.add_edge("lewin", END)

    compiled = graph.compile()

    initial = {
        "trace": {
            "goal": "Answer 'When was Pluto reclassified?'",
            "steps": [
                {"type": "input", "content": "When was Pluto reclassified?"},
                {"type": "tool_call", "content": "rag.search(query='pluto')"},
                {"type": "observation", "content": "stale 2003 Wikipedia revision"},
                {"type": "output", "content": "Pluto was reclassified in 2003."},
            ],
            "outcome": "Confidently wrong (correct: 2006).",
            "success": False,
        }
    }
    final_state = compiled.invoke(initial)
    print("=== AAR detection (truncated) ===")
    print(json.dumps(final_state.get("vstack_aar"), indent=2, default=str)[:1000])
    print("\n=== Lewin detection (truncated) ===")
    print(json.dumps(final_state.get("vstack_lewin"), indent=2, default=str)[:1000])


if __name__ == "__main__":
    main()
