# Python version note

This library requires Python 3.11+ (as declared in `pyproject.toml`).

If you see an error like
`TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`
when importing the module, you are likely on Python 3.9. The codebase uses
PEP 604 union syntax (`str | None`) and PEP 585 generic syntax (`list[str]`),
which are 3.10+ features. The `from __future__ import annotations` directive
makes the annotations themselves lazy, but Pydantic v2 still evaluates them
at class-construction time.

Fix: use Python 3.11+ in a virtual environment.

```
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[anthropic]"
```
