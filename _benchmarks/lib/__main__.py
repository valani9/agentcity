"""Allow ``python -m vstack.benchmarks`` as an alias for ``vstack-bench``."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
