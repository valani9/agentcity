"""Optional Sentry integration.

We never hard-depend on ``sentry-sdk`` — many vstack users don't
care about Sentry, and the SDK pulls in a non-trivial dep tree. If
the user has the SDK installed AND ``SENTRY_DSN`` is set, we
initialize it with sensible defaults; otherwise this module is a
no-op.

Importing this module does NOT import ``sentry-sdk`` — that
happens inside :func:`install_sentry_if_configured`.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_sentry_installed = False
_sentry_module: Any | None = None


def install_sentry_if_configured(env: dict[str, str] | None = None) -> bool:
    """Initialize Sentry if ``SENTRY_DSN`` is set + ``sentry-sdk`` is installed.

    Idempotent: safe to call multiple times. Returns ``True`` if
    Sentry is now active, ``False`` otherwise.

    Environment variables consulted:
      * ``SENTRY_DSN`` -- required to enable
      * ``SENTRY_ENVIRONMENT`` -- default ``"production"``
      * ``SENTRY_RELEASE`` -- default ``"valanistack@<version>"``
      * ``SENTRY_TRACES_SAMPLE_RATE`` -- default ``0.05``
      * ``SENTRY_PROFILES_SAMPLE_RATE`` -- default ``0.0``
    """
    global _sentry_installed, _sentry_module
    if _sentry_installed:
        return True

    env = env if env is not None else dict(os.environ)
    dsn = env.get("SENTRY_DSN")
    if not dsn:
        return False

    try:
        import sentry_sdk
    except ImportError:
        logger.info(
            "SENTRY_DSN is set but sentry-sdk is not installed; skipping. "
            "Run: pip install sentry-sdk"
        )
        return False

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=env.get("SENTRY_ENVIRONMENT", "production"),
            release=env.get("SENTRY_RELEASE", _release_string()),
            traces_sample_rate=_float_env(env, "SENTRY_TRACES_SAMPLE_RATE", 0.05),
            profiles_sample_rate=_float_env(env, "SENTRY_PROFILES_SAMPLE_RATE", 0.0),
            send_default_pii=False,
        )
    except Exception as e:  # noqa: BLE001 - sentry-sdk init can throw anything
        logger.warning("Failed to initialize Sentry: %s", e)
        return False

    _sentry_module = sentry_sdk
    _sentry_installed = True
    logger.info("Sentry initialized; reporting to %s", _redact_dsn(dsn))
    return True


def is_sentry_active() -> bool:
    """Return whether Sentry is currently active in this process."""
    return _sentry_installed


def _release_string() -> str:
    try:
        import vstack

        return f"valanistack@{vstack.__version__}"
    except Exception:
        return "valanistack@unknown"


def _float_env(env: dict[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return default


def _redact_dsn(dsn: str) -> str:
    """Return the DSN host without the auth segment for safe logging."""
    if "@" in dsn:
        return "https://***@" + dsn.split("@", 1)[1]
    return "<dsn>"
