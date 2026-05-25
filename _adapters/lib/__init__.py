"""vstack.adapters -- framework-native bindings that expose all 34
diagnostic patterns to the major AI agent / LLM frameworks.

Reuses the same registry that powers ``vstack-mcp`` and ``vstack-api``
so the LangChain tool list, the LangGraph node set, the CrewAI tool
roster, the AutoGen function manifest, the LlamaIndex tool spec, the
Pydantic AI tool roster, the OpenAI Assistants-API tool JSON, and the
Open WebUI plugin all describe the same 34 patterns with the same
input/output models. Adding a pattern to the registry instantly adds
it to every adapter.

Quick start
-----------

::

    # LangChain
    from vstack.adapters.langchain import as_langchain_tools
    tools = as_langchain_tools(llm_client=AnthropicClient())
    agent = create_react_agent(llm, tools, prompt)

    # CrewAI
    from vstack.adapters.crewai import as_crewai_tools
    tools = as_crewai_tools(llm_client=AnthropicClient())

    # OpenAI Assistants
    from vstack.adapters.openai import as_openai_tool_schemas
    spec = as_openai_tool_schemas()  # JSON for Assistants API

    # AutoGen
    from vstack.adapters.autogen import as_autogen_function_manifest
    manifest = as_autogen_function_manifest()

Each adapter is import-gated -- the framework dependency is loaded
lazily on first call, so users who only want LangChain pay nothing for
the CrewAI / AutoGen / etc. imports. Install only the framework
extras you need::

    pip install 'valanistack[langchain]'
    pip install 'valanistack[langgraph]'
    pip install 'valanistack[crewai]'
    pip install 'valanistack[autogen]'
    pip install 'valanistack[llamaindex]'
    pip install 'valanistack[pydantic_ai]'
    pip install 'valanistack[openwebui]'
    pip install 'valanistack[adapters]'   # all of the above
"""

from ._base import (
    AdapterImportError,
    PatternToolSpec,
    list_pattern_tool_specs,
    pattern_tool_spec_for,
    serialize_detection,
)

__all__ = [
    "AdapterImportError",
    "PatternToolSpec",
    "list_pattern_tool_specs",
    "pattern_tool_spec_for",
    "serialize_detection",
]

__version__ = "0.4.0"
