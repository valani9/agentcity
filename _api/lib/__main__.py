"""Allow ``python -m vstack.api`` as an alias for ``vstack-api``.

Also exposes a module-level ``app`` so ``uvicorn vstack.api:app`` works.
"""

from __future__ import annotations

import sys

from ._app import create_default_app
from .cli import main

app = create_default_app()


if __name__ == "__main__":
    sys.exit(main())
