"""Allow ``python -m vstack.browser`` as an alias for ``vstack-browser``."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
