"""Diagnostic checks for ``vstack-doctor``."""

from __future__ import annotations

import importlib
import os
import shutil
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HealthStatus(str, Enum):
    OK = "ok"
    WARNING = "warning"
    """Functional but suboptimal (e.g. running without auth on a
    public interface; recommended extra not installed)."""

    ERROR = "error"
    """A required piece is missing; some functionality won't work."""


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: HealthStatus
    summary: str
    hint: str = ""
    """If non-empty, the exact command to run to fix this."""

    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class DoctorReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(c.status == HealthStatus.ERROR for c in self.checks)

    @property
    def has_warnings(self) -> bool:
        return any(c.status == HealthStatus.WARNING for c in self.checks)


# ----------------------------------------------------------------------
# Individual checks
# ----------------------------------------------------------------------


def _check_python_version() -> CheckResult:
    import sys

    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 11):
        return CheckResult(
            "python_version",
            HealthStatus.ERROR,
            f"Python {major}.{minor} is too old (vstack needs 3.11+).",
            hint="Upgrade Python: 'brew install python@3.13' or pyenv.",
        )
    return CheckResult(
        "python_version",
        HealthStatus.OK,
        f"Python {major}.{minor}",
    )


def _check_vstack_version() -> CheckResult:
    try:
        import vstack

        return CheckResult(
            "vstack_version",
            HealthStatus.OK,
            f"valanistack {vstack.__version__}",
        )
    except ImportError as e:
        return CheckResult(
            "vstack_version",
            HealthStatus.ERROR,
            f"vstack import failed: {e}",
            hint="pip install valanistack",
        )


def _check_pattern_registry() -> CheckResult:
    try:
        from vstack.mcp._registry import PATTERNS

        if len(PATTERNS) == 34:
            return CheckResult(
                "pattern_registry",
                HealthStatus.OK,
                f"{len(PATTERNS)} patterns registered.",
            )
        return CheckResult(
            "pattern_registry",
            HealthStatus.WARNING,
            f"Expected 34 patterns; found {len(PATTERNS)}. The wheel may "
            "have shipped without all force-included subdirs.",
            hint="pip install --force-reinstall valanistack",
        )
    except Exception as e:
        return CheckResult(
            "pattern_registry",
            HealthStatus.ERROR,
            f"Registry import failed: {e}",
            hint="pip install --force-reinstall valanistack",
        )


def _check_cli_on_path(name: str) -> CheckResult:
    path = shutil.which(name)
    if path:
        return CheckResult(f"cli/{name}", HealthStatus.OK, f"{name} -> {path}")
    return CheckResult(
        f"cli/{name}",
        HealthStatus.ERROR,
        f"{name} not on PATH.",
        hint="pip install valanistack (or ensure the venv's bin/ is on PATH)",
    )


def _check_optional_extra(name: str, module: str, extra: str) -> CheckResult:
    try:
        importlib.import_module(module)
        return CheckResult(f"extra/{name}", HealthStatus.OK, f"{name} ({module}) installed.")
    except ImportError:
        return CheckResult(
            f"extra/{name}",
            HealthStatus.WARNING,
            f"{name} not installed (optional).",
            hint=f"pip install 'valanistack[{extra}]'",
        )


def _check_llm_client_resolvable() -> CheckResult:
    try:
        from vstack.mcp._client import resolve_llm_client, LLMResolutionError
    except Exception as e:
        return CheckResult(
            "llm_client",
            HealthStatus.ERROR,
            f"vstack.mcp not importable: {e}",
            hint="pip install 'valanistack[mcp]'",
        )
    try:
        client = resolve_llm_client()
        return CheckResult(
            "llm_client",
            HealthStatus.OK,
            f"resolved {type(client).__name__}",
        )
    except LLMResolutionError as e:
        return CheckResult(
            "llm_client",
            HealthStatus.WARNING,
            "No LLM client configured (vstack-mcp / vstack-api will reject calls).",
            hint=(
                "Set ANTHROPIC_API_KEY (recommended), OPENAI_API_KEY, or "
                "OLLAMA_HOST. Or set VSTACK_MCP_LLM=stub for tests."
            ),
            detail={"resolution_error": str(e)},
        )
    except Exception as e:
        return CheckResult(
            "llm_client",
            HealthStatus.ERROR,
            f"LLM client resolution crashed: {e}",
        )


def _check_home_dir() -> CheckResult:
    try:
        from vstack.memory import get_home

        home = get_home()
    except Exception as e:
        return CheckResult(
            "vstack_home",
            HealthStatus.ERROR,
            f"vstack.memory failed: {e}",
        )
    if not os.access(str(home), os.W_OK):
        return CheckResult(
            "vstack_home",
            HealthStatus.ERROR,
            f"{home} is not writable.",
            hint=(f"Check permissions on {home} or set VSTACK_HOME=/path/to/writable"),
        )
    return CheckResult("vstack_home", HealthStatus.OK, f"{home} (writable)")


def _check_gbrain() -> CheckResult:
    if shutil.which("gbrain"):
        return CheckResult(
            "gbrain",
            HealthStatus.OK,
            "gbrain on PATH (semantic search available).",
        )
    return CheckResult(
        "gbrain",
        HealthStatus.WARNING,
        "gbrain not on PATH (vstack-gbrain falls back to keyword search).",
        hint="Install gbrain to enable semantic search across the 34 patterns.",
    )


def _check_node_for_browser() -> CheckResult:
    if shutil.which("npx") or shutil.which("node"):
        return CheckResult(
            "node_for_browser",
            HealthStatus.OK,
            "Node.js / npx available (vstack-browser can spawn chrome-devtools-mcp).",
        )
    return CheckResult(
        "node_for_browser",
        HealthStatus.WARNING,
        "Node.js / npx not on PATH; vstack-browser won't work without it.",
        hint="brew install node (macOS) or apt install nodejs (Debian)",
    )


def _check_pypi_for_upgrade() -> CheckResult:
    try:
        from vstack.upgrade import fetch_latest_version, get_current_version, is_newer
    except Exception as e:
        return CheckResult(
            "pypi_upgrade",
            HealthStatus.WARNING,
            f"vstack.upgrade import failed: {e}",
        )
    try:
        latest = fetch_latest_version(timeout=3.0)
    except Exception as e:
        return CheckResult(
            "pypi_upgrade",
            HealthStatus.WARNING,
            f"PyPI lookup failed: {e}",
            hint="Check network connectivity to pypi.org.",
        )
    current = get_current_version()
    if is_newer(current, latest):
        return CheckResult(
            "pypi_upgrade",
            HealthStatus.WARNING,
            f"valanistack upgrade available: {current} -> {latest}",
            hint=f"pip install --upgrade 'valanistack=={latest}'",
        )
    return CheckResult(
        "pypi_upgrade",
        HealthStatus.OK,
        f"valanistack {current} is up to date.",
    )


def _check_api_security_posture() -> CheckResult:
    """Warn when require_auth is enabled but no keys are configured.

    Doesn't try to spin up the API; just inspects env vars to surface
    misconfigurations that the API would reject at request time.
    """
    require = (os.environ.get("VSTACK_API_REQUIRE_AUTH") or "").strip().lower()
    has_keys = bool(os.environ.get("VSTACK_API_KEYS") or os.environ.get("VSTACK_API_KEYS_FILE"))
    if require in ("1", "true", "yes", "on") and not has_keys:
        return CheckResult(
            "api_security",
            HealthStatus.ERROR,
            "VSTACK_API_REQUIRE_AUTH is on but no API keys are configured; the API will 500.",
            hint="Set VSTACK_API_KEYS=... or VSTACK_API_KEYS_FILE=/path",
        )
    if has_keys:
        return CheckResult(
            "api_security",
            HealthStatus.OK,
            "API keys configured.",
        )
    return CheckResult(
        "api_security",
        HealthStatus.OK,
        "API keys not set (loopback-only deployment recommended).",
    )


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------


_CLIS = (
    "vstack",
    "vstack-mcp",
    "vstack-api",
    "vstack-config",
    "vstack-upgrade",
    "vstack-learn",
    "vstack-analytics",
    "vstack-browser",
    "vstack-gbrain",
    "vstack-bench",
)

_EXTRAS: tuple[tuple[str, str, str], ...] = (
    ("anthropic", "anthropic", "anthropic"),
    ("openai", "openai", "openai"),
    ("mcp", "mcp", "mcp"),
    ("fastapi", "fastapi", "api"),
    ("langchain_core", "langchain_core", "langchain"),
    ("langgraph", "langgraph", "langgraph"),
    ("llama_index_core", "llama_index.core", "llamaindex"),
    ("pydantic_ai", "pydantic_ai", "pydantic_ai"),
)


def run_all_checks(*, skip_network: bool = False) -> DoctorReport:
    """Run every check + return a :class:`DoctorReport`.

    Network-dependent checks (``pypi_upgrade``) are skipped when
    ``skip_network=True``; useful for CI / air-gapped diagnostics.
    """
    checks: list[CheckResult] = [
        _check_python_version(),
        _check_vstack_version(),
        _check_pattern_registry(),
        _check_home_dir(),
        _check_llm_client_resolvable(),
        _check_api_security_posture(),
        _check_gbrain(),
        _check_node_for_browser(),
    ]
    for name in _CLIS:
        checks.append(_check_cli_on_path(name))
    for extra_name, module, extra_pkg in _EXTRAS:
        checks.append(_check_optional_extra(extra_name, module, extra_pkg))
    if not skip_network:
        checks.append(_check_pypi_for_upgrade())
    return DoctorReport(checks=checks)
