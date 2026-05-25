"""OpenAI Assistants demo -- pure JSON; no SDK install required for the adapter.

Run:
    pip install valanistack
    python examples/openai_assistants_demo.py

This demo just prints the OpenAI tool-schema array; you'd normally
hand the array to ``openai.beta.assistants.create(tools=...)`` or to
``openai.chat.completions.create(tools=...)``.
"""

from __future__ import annotations

import json

from vstack.adapters.openai import (
    as_anthropic_tool_schemas,
    as_openai_tool_schemas,
)


def main() -> None:
    openai_tools = as_openai_tool_schemas()
    anthropic_tools = as_anthropic_tool_schemas()
    print(f"OpenAI tool array: {len(openai_tools)} functions")
    print(f"Anthropic tool array: {len(anthropic_tools)} tools")
    print()

    print("Spec sample (first OpenAI function):")
    print(json.dumps(openai_tools[0], indent=2)[:1200])
    print()

    # Sketch the call you'd do for real:
    print("To use with OpenAI's API:")
    print(
        "    import openai\n"
        "    client = openai.OpenAI()\n"
        "    assistant = client.beta.assistants.create(\n"
        "        name='vstack-diagnostician',\n"
        "        model='gpt-5',\n"
        "        tools=openai_tools,\n"
        "    )"
    )
    print()
    print("Pair with vstack-api (REST) at 127.0.0.1:8000 to actually run the tools.")


if __name__ == "__main__":
    main()
