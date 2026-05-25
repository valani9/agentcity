"""CrewAI demo -- one agent uses the Lencioni vstack tool.

Run:
    pip install 'valanistack[anthropic,crewai]'
    export ANTHROPIC_API_KEY="sk-ant-..."
    python examples/crewai_demo.py
"""

from __future__ import annotations

from crewai import Agent, Crew, Task

from vstack.adapters.crewai import as_crewai_tools


def main() -> None:
    tools = as_crewai_tools()
    # Pick one tool; the demo only exercises Lencioni.
    lencioni_tool = next(t for t in tools if t.name == "vstack_lencioni")

    diagnostician = Agent(
        role="Multi-agent crew diagnostician",
        goal="Audit the supplied multi-agent crew trace using vstack patterns.",
        backstory=(
            "You are a careful diagnostic specialist. Use the vstack_lencioni "
            "tool to score the crew on the five-dysfunctions pyramid."
        ),
        tools=[lencioni_tool],
        verbose=True,
    )

    task = Task(
        description=(
            "Run the vstack_lencioni tool against this trace and report the "
            "dominant dysfunction layer + the top intervention.\n\n"
            "Trace shape: a MultiAgentTrace with `goal`, `agents`, `messages`, "
            "`outcome`, `success`. Use the canonical campaign-team example "
            "from the vstack composition runbook (Chain T1)."
        ),
        expected_output=(
            "A one-paragraph report naming the dominant_dysfunction and the "
            "single highest-impact intervention from the detection."
        ),
        agent=diagnostician,
    )

    crew = Crew(agents=[diagnostician], tasks=[task], verbose=True)
    result = crew.kickoff()
    print("\n=== Final crew output ===")
    print(result)


if __name__ == "__main__":
    main()
