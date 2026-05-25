"""LlamaIndex demo -- FunctionTool per pattern.

Run:
    pip install 'valanistack[anthropic,llamaindex]'
    export ANTHROPIC_API_KEY="sk-ant-..."
    python examples/llamaindex_demo.py
"""

from __future__ import annotations

import json

from vstack.adapters.llamaindex import as_llamaindex_tools


def main() -> None:
    tools = as_llamaindex_tools()
    print(f"Built {len(tools)} LlamaIndex FunctionTool instances.\n")

    lewin = next(t for t in tools if t.metadata.name == "vstack_lewin")
    print(f"Tool name: {lewin.metadata.name}")
    print(f"Description (truncated): {lewin.metadata.description[:200]}...")
    print()

    # Call the tool directly; in a real LlamaIndex agent you'd hand it to
    # an OpenAIAgent / ReActAgent and let the LLM decide when to call.
    result = lewin(
        task="Answer 'When was Pluto reclassified?'",
        steps=[
            {"type": "input", "content": "When was Pluto reclassified?"},
            {"type": "tool_call", "content": "rag.search(query='pluto')"},
            {"type": "observation", "content": "stale 2003 wiki snapshot"},
            {"type": "output", "content": "Pluto was reclassified in 2003."},
        ],
        outcome="Confidently wrong year.",
        success=False,
        initial_attribution="model is bad at facts",
        mode="standard",
    )
    payload = getattr(result, "raw_output", None) or getattr(result, "content", result)
    print("Lewin detection (truncated):")
    print(json.dumps(payload, indent=2, default=str)[:1000])


if __name__ == "__main__":
    main()
