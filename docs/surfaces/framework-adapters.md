# Framework adapters

`vstack.adapters` wraps all 34 patterns as native tools for the major AI agent / LLM frameworks. Same registry, same input model, same detection output — only the framework wrapper differs.

```python
# LangChain
from vstack.adapters.langchain import as_langchain_tools
tools = as_langchain_tools()

# LangGraph
from vstack.adapters.langgraph import as_langgraph_nodes
nodes = as_langgraph_nodes()

# CrewAI
from vstack.adapters.crewai import as_crewai_tools
tools = as_crewai_tools()

# AutoGen (no autogen import required)
from vstack.adapters.autogen import as_autogen_function_manifest, as_autogen_callables
manifest = as_autogen_function_manifest()
callables = as_autogen_callables()

# LlamaIndex
from vstack.adapters.llamaindex import as_llamaindex_tools
tools = as_llamaindex_tools()

# Pydantic AI
from vstack.adapters.pydantic_ai import as_pydantic_ai_tools
tools = as_pydantic_ai_tools()

# OpenAI Assistants + Anthropic Messages (pure JSON)
from vstack.adapters.openai import as_openai_tool_schemas, as_anthropic_tool_schemas

# Open WebUI plugin manifest
from vstack.adapters.openwebui import as_openwebui_manifest
manifest = as_openwebui_manifest(api_base_url="http://127.0.0.1:8000")
```

## Install

Each adapter is import-gated; install only the framework extras you need:

```bash
pip install 'valanistack[langchain]'
pip install 'valanistack[langgraph]'
pip install 'valanistack[crewai]'
pip install 'valanistack[llamaindex]'
pip install 'valanistack[pydantic_ai]'
pip install 'valanistack[adapters]'   # all five gated adapters
```

The `autogen`, `openai`, and `openwebui` adapters need no extra — they're pure JSON / Python.

## Architecture

Every adapter consumes a `PatternToolSpec` derived from `vstack.mcp._registry`:

```python
from vstack.adapters import list_pattern_tool_specs, pattern_tool_spec_for
specs = list_pattern_tool_specs()          # 34 specs
lewin_spec = pattern_tool_spec_for("lewin")
print(lewin_spec.name, lewin_spec.input_schema)
```

The shared `run_pattern_dispatch()` function is the single chunk of logic every adapter shares: validate input against the pattern's Pydantic model → resolve an LLM client → run the analyzer → return the detection as a JSON-safe dict.

## Running demos

See [`examples/`](https://github.com/valani9/vstack/tree/main/examples) for end-to-end demo scripts (one per framework).
