# vstack — runnable framework demos

Seven self-contained scripts showing each `vstack.adapters` integration in use. Each script:

- Imports its target framework + vstack
- Builds a tiny canonical agent task
- Wires one or more vstack patterns as tools
- Runs the chain and prints the structured detection

The demos assume `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) is set; switch the LLM client at the top of each script if you want to use a different provider.

## Run

```bash
pip install 'valanistack[anthropic,langchain]'      # for the langchain demo
pip install 'valanistack[anthropic,langgraph]'      # for the langgraph demo
pip install 'valanistack[anthropic,crewai]'         # for the crewai demo
pip install 'valanistack[anthropic,llamaindex]'     # for the llamaindex demo
pip install 'valanistack[anthropic,pydantic_ai]'    # for the pydantic-ai demo
# autogen / openai-assistants demos need no extra valanistack extra
# (the adapters are pure JSON / pure Python).

export ANTHROPIC_API_KEY="sk-ant-..."
python examples/langchain_demo.py
python examples/langgraph_demo.py
python examples/crewai_demo.py
python examples/autogen_demo.py
python examples/llamaindex_demo.py
python examples/pydantic_ai_demo.py
python examples/openai_assistants_demo.py
```

Each script ends with `print(detection.model_dump_json(indent=2))` so you can paste a real output into a writeup or an issue.

## What the demos exercise

| Script | Adapter | Pattern(s) | What it shows |
|---|---|---|---|
| `langchain_demo.py` | `vstack.adapters.langchain` | `vstack_lewin` | Wrap pattern as `StructuredTool`, invoke directly. |
| `langgraph_demo.py` | `vstack.adapters.langgraph` | `vstack_aar`, `vstack_lewin` | Two-node graph: AAR → Lewin, with state passing. |
| `crewai_demo.py` | `vstack.adapters.crewai` | `vstack_lencioni` | Crew with one agent that uses the Lencioni tool. |
| `autogen_demo.py` | `vstack.adapters.autogen` | `vstack_lewin` | Function-call manifest + Python callable registered manually. |
| `llamaindex_demo.py` | `vstack.adapters.llamaindex` | `vstack_lewin` | `FunctionTool` with the pattern's input model. |
| `pydantic_ai_demo.py` | `vstack.adapters.pydantic_ai` | `vstack_aar` | `Agent.tool_plain` registration. |
| `openai_assistants_demo.py` | `vstack.adapters.openai` | All 34 | Build the full OpenAI Assistants `tools` JSON. |

The demos are intentionally small (~60 lines each). They're not production examples — they're the "does the adapter actually work end-to-end?" sanity check that ships alongside the adapter unit tests.
