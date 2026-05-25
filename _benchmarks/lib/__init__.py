"""vstack.benchmarks -- runnable harness for evaluating vstack
patterns against agent-task benchmarks.

The harness is the kind of thing you'd run yourself with API keys
set; the unit-test suite that ships with it exercises the
*scaffolding* (case schemas, runner state machine, metrics
aggregator) with a stub LLM client. Plug your real LLM client in
when you want real numbers.

Two top-level entry points:

* :class:`BenchmarkSuite` -- a tagged collection of
  :class:`BenchmarkCase` instances. Ships with a small curated
  ``canonical`` suite (3 cases covering Lewin / AAR / Schein) so
  ``vstack-bench run canonical`` produces a non-empty report on
  first use. Adding GAIA / SWE-Bench-multi / AppWorld / AgentBench
  cases is the user's responsibility -- those datasets ship under
  their own licenses and we don't redistribute them.

* :class:`BenchmarkRunner` -- iterates the suite, runs each
  pattern's analyzer on the case's trace, and accumulates a
  :class:`BenchmarkReport` with success rate, severity distribution,
  mean elapsed-ms, total tokens, and per-case detection JSON.

The harness is intentionally pattern-agnostic. A case names which
pattern (or chain) to run; the runner dispatches through the same
``vstack.adapters.run_pattern_dispatch`` shared dispatcher that the
MCP server / REST API / framework adapters use.

CLI: ``vstack-bench run <suite-name>``
     ``vstack-bench list``
     ``vstack-bench report <run-dir>``
"""

from ._comparative import (
    ComparativeCase,
    ComparativeCaseReport,
    ComparativeModeResult,
    comparative_table,
    run_comparative,
)
from ._harness import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkReport,
    BenchmarkRunner,
    BenchmarkSuite,
    canonical_suite,
    load_suite,
    save_report,
)

__all__ = [
    "BenchmarkCase",
    "BenchmarkCaseResult",
    "BenchmarkReport",
    "BenchmarkRunner",
    "BenchmarkSuite",
    "canonical_suite",
    "load_suite",
    "save_report",
    "ComparativeCase",
    "ComparativeCaseReport",
    "ComparativeModeResult",
    "comparative_table",
    "run_comparative",
]

__version__ = "0.5.0"
