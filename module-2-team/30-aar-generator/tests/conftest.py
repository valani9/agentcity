"""
pytest configuration for the AAR Generator test suite.

Adds the sibling `lib/` directory to sys.path so that tests can import the
library modules directly without requiring an editable install of the
package. When the package is installed via `pip install -e .` the lib
directory becomes `agentcity.aar` and tests can be updated to use the
installed import path.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add the pattern's root to path so `lib.X` imports resolve cleanly when
# running pytest directly without `pip install -e .`.
_PATTERN_ROOT = Path(__file__).resolve().parents[1]
if str(_PATTERN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PATTERN_ROOT))
