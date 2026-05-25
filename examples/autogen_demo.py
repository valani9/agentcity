"""AutoGen demo -- register vstack functions on an AutoGen agent.

Run:
    pip install 'valanistack[anthropic]' autogen-agentchat
    export ANTHROPIC_API_KEY="sk-ant-..."
    python examples/autogen_demo.py

The vstack.adapters.autogen module returns both the function manifest
(pure JSON, no autogen import required) and a dict of Python
callables. This demo wires them onto a manual AssistantAgent without
depending on AutoGen's exact tool-registration API (which has changed
across releases).
"""

from __future__ import annotations

import json

from vstack.adapters.autogen import (
    as_autogen_callables,
    as_autogen_function_manifest,
)


def main() -> None:
    manifest = as_autogen_function_manifest()
    callables = as_autogen_callables()

    print(f"vstack exposes {len(manifest)} functions to AutoGen.")
    print(f"First function: {manifest[0]['name']}")
    print()

    # Run one directly.
    fn = callables["vstack_lewin"]
    detection = fn(
        task="Answer 'When was Pluto reclassified?'",
        steps=[
            {"type": "input", "content": "When was Pluto reclassified?"},
            {"type": "tool_call", "content": "rag.search(query='pluto')"},
            {"type": "observation", "content": "stale 2003 wiki snapshot"},
            {"type": "output", "content": "Pluto was reclassified in 2003."},
        ],
        outcome="Confidently wrong year (2006 is correct).",
        success=False,
        initial_attribution="model is bad at facts",
        mode="standard",
    )
    print("vstack_lewin detection (truncated):")
    print(json.dumps(detection, indent=2, default=str)[:1000])
    print()

    # Register-on-AutoGen sketch (commented; real wiring depends on
    # the autogen version you have installed):
    # from autogen_agentchat.agents import AssistantAgent
    # agent = AssistantAgent(
    #     name="diagnostician",
    #     tools=manifest,
    # )
    # for name, fn in callables.items():
    #     agent.register_for_llm(name=name)(fn)


if __name__ == "__main__":
    main()
