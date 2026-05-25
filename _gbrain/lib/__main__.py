"""Allow ``python -m vstack.gbrain`` as an alias for ``vstack-gbrain``."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
