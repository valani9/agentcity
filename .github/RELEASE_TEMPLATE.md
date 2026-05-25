# vstack {{ version }}

**Organizational behavior, practiced on AI agents.** vstack is a curated library
of 34 diagnostic patterns drawn from organizational behavior, social psychology,
and group dynamics — each rewritten for the domain of AI agents rather than
human teams.

## Install

```bash
pip install valanistack=={{ version }}
```

Optional extras: `[anthropic]`, `[openai]`, `[ollama]`, `[mcp]`, `[api]`,
`[browser]`, `[langchain]`, `[langgraph]`, `[crewai]`, `[llamaindex]`,
`[pydantic-ai]`, `[adapters]`, `[all]`.

Docker:

```bash
docker pull ghcr.io/valani9/vstack:{{ version }}
```

## What changed in this release

{{ changelog_section }}

## Verify the install

```bash
vstack-doctor          # 25+ install checks
vstack-hello           # 30-second end-to-end demo
```

## Resources

- [Docs](https://valani9.github.io/vstack/) — hosted mkdocs site
- [CHANGELOG](https://github.com/valani9/vstack/blob/main/CHANGELOG.md) — full history
- [Patterns index](https://github.com/valani9/vstack/blob/main/PATTERNS.md) — all 34 patterns + literature anchors
- [Security policy](https://github.com/valani9/vstack/security/policy)
