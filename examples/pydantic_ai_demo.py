"""Pydantic AI demo -- register vstack tools on an Agent.

Run:
    pip install 'valanistack[anthropic,pydantic_ai]'
    export ANTHROPIC_API_KEY="sk-ant-..."
    python examples/pydantic_ai_demo.py
"""

from __future__ import annotations

import json

from pydantic_ai import Agent

from vstack.adapters.pydantic_ai import as_pydantic_ai_tools


def main() -> None:
    tools = as_pydantic_ai_tools()
    print(f"Built {len(tools)} pydantic-ai tool triples.\n")

    agent = Agent("anthropic:claude-sonnet-4-5")
    for tool in tools:
        agent.tool_plain(name=tool.name)(tool.func)

    # Call one tool directly without the LLM in the loop, just to
    # show the underlying callable wired correctly.
    aar_tool = next(t for t in tools if t.name == "vstack_aar")
    result = aar_tool.func(
        goal="Refactor the auth module to use JWTs.",
        steps=[
            {"type": "tool_call", "content": "edit_file(auth/middleware.py)"},
            {"type": "observation", "content": "session-middleware tests fail"},
            {"type": "output", "content": "Created JWT tokens but broke sessions."},
        ],
        outcome="Auth module half-migrated; session middleware broken.",
        success=False,
        mode="standard",
    )
    print("AAR detection (truncated):")
    print(json.dumps(result, indent=2, default=str)[:1000])
    print()

    # Real-agent path:
    print("To exercise the LLM path:")
    print(
        "    response = asyncio.run(agent.run("
        "'Run vstack_aar on the JWT-refactor agent trace I just described.'))"
    )


if __name__ == "__main__":
    main()
