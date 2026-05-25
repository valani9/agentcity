"""Allow ``python -m vstack.mcp`` as an alias for ``vstack-mcp``."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
