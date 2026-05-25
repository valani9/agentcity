"""vstack.doctor -- diagnostic CLI that audits the install.

``vstack-doctor`` walks the installed surfaces and reports their
health: which CLIs resolve on PATH, which optional extras are
installed, which API keys are configured, whether the MCP server
boots, whether gbrain is reachable, whether the canonical
benchmarks suite passes the schema check, and whether a newer
release is available on PyPI.

The point is to give a new user one command they can run after
``pip install valanistack`` that tells them what's working,
what's missing, and exactly which next command to run to make
each missing piece work.
"""

from ._doctor import (
    CheckResult,
    DoctorReport,
    HealthStatus,
    run_all_checks,
)

__all__ = ["CheckResult", "DoctorReport", "HealthStatus", "run_all_checks"]

__version__ = "0.6.0"
