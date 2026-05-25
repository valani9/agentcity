"""LangChain demo -- wrap vstack patterns as StructuredTools.

Run:
    pip install 'valanistack[anthropic,langchain]'
    export ANTHROPIC_API_KEY="sk-ant-..."
    python examples/langchain_demo.py
"""

from __future__ import annotations

import json

from vstack.adapters.langchain import as_langchain_tools


def main() -> None:
    tools = as_langchain_tools()
    print(f"Built {len(tools)} LangChain StructuredTool instances from vstack patterns.\n")

    lewin_tool = next(t for t in tools if t.name == "vstack_lewin")
    print(f"Tool: {lewin_tool.name}")
    print(f"Description (first 200 chars): {lewin_tool.description[:200]}...")
    print()

    # Build a tiny canonical Lewin input and invoke the tool directly.
    sample_input = {
        "task": "Answer 'When was Pluto reclassified?'",
        "steps": [
            {"type": "input", "content": "When was Pluto reclassified?"},
            {"type": "tool_call", "content": "rag.search(query='pluto')"},
            {"type": "observation", "content": "returned a 2003 Wikipedia revision"},
            {"type": "output", "content": "Pluto was reclassified in 2003."},
        ],
        "outcome": "Confidently wrong year (correct: 2006).",
        "success": False,
        "initial_attribution": "model is bad at facts",
        "mode": "standard",
    }
    result = lewin_tool.invoke(sample_input)
    print("Lewin detection (truncated):")
    print(json.dumps(result, indent=2, default=str)[:1000])


if __name__ == "__main__":
    main()
