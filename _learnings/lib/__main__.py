"""Allow ``python -m vstack.learnings`` as an alias for ``vstack-learn``."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
