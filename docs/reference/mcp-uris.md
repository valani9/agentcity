# MCP resource URIs

The `vstack-mcp` server publishes 102 resources covering the full pattern catalogue.

| URI | Mime | Body |
|---|---|---|
| `vstack://patterns/index` | `application/json` | Catalogue of all 34 patterns with name / friendly / group / tool / summary / input_class / output_class / modes / resource URIs. |
| `vstack://patterns/<name>/citations` | `text/markdown` | The pattern's `CITATIONS.md`. |
| `vstack://patterns/<name>/playbooks` | `application/json` | The pattern's failure-mode playbooks dict, serialized. |
| `vstack://patterns/<name>/composition` | `application/json` | Composition manifest with upstream / downstream pattern recommendations + framework overlays. |

Replace `<name>` with any pattern import name: `lewin`, `aar`, `lencioni`, `schein_culture`, `span_of_control`, etc.

## Reading from MCP

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def read_index():
    params = StdioServerParameters(command="vstack-mcp", args=["serve"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.read_resource("vstack://patterns/index")
            print(result.contents[0].text)

asyncio.run(read_index())
```

## Reading from the REST API

Each resource is mirrored as an HTTP endpoint:

```bash
curl http://127.0.0.1:8000/v1/patterns                          # = index
curl http://127.0.0.1:8000/v1/patterns/lewin/citations
curl http://127.0.0.1:8000/v1/patterns/lewin/playbooks
curl http://127.0.0.1:8000/v1/patterns/lewin/composition
```
