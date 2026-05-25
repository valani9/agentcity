"""API-key authentication for the REST surface.

The default mode for ``vstack-api serve`` is no-auth + loopback bind
(127.0.0.1). When you bind to a public interface or run inside an
orchestrator, set ``VSTACK_API_KEYS=key1,key2,key3`` (or a
newline-separated file via ``VSTACK_API_KEYS_FILE``) and pass
``--require-auth`` to the CLI. Requests then need a header
``Authorization: Bearer <key>`` or ``X-API-Key: <key>`` to be accepted.

Keys are validated in constant time via :func:`hmac.compare_digest`
so the server can't be timing-side-channeled to enumerate them.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


DEFAULT_API_KEYS_ENV = "VSTACK_API_KEYS"
DEFAULT_API_KEYS_FILE_ENV = "VSTACK_API_KEYS_FILE"
MIN_API_KEY_LENGTH = 24
"""Minimum acceptable key length. Generated keys come out at 32 chars
hex (16 bytes of entropy) which clears this bar comfortably."""


@dataclass(frozen=True)
class APIKey:
    """One configured API key with metadata.

    The ``name`` is a human label (used in logs + metrics; never
    surfaced over the wire). The ``key_hash`` is a SHA-256 digest of
    the raw key so the keystore never holds the raw value in memory
    after construction.
    """

    name: str
    key_hash: bytes

    @classmethod
    def from_raw(cls, name: str, raw: str) -> "APIKey":
        if len(raw) < MIN_API_KEY_LENGTH:
            raise ValueError(
                f"API key for {name!r} is shorter than {MIN_API_KEY_LENGTH} chars. "
                "Generate a stronger one with secrets.token_urlsafe(24)."
            )
        return cls(name=name, key_hash=_hash_key(raw))


@dataclass
class APIKeyStore:
    """A bag of configured API keys.

    Construct via :func:`load_keys_from_env`, or pass an explicit
    list of :class:`APIKey` for tests. Lookup is O(N) over the keys
    (N is small for the production cases vstack targets); switch to
    a hashed-set lookup if N exceeds the low hundreds.
    """

    keys: list[APIKey] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.keys)

    def __bool__(self) -> bool:
        return bool(self.keys)

    def verify(self, raw: str | None) -> APIKey | None:
        """Return the matching :class:`APIKey` if ``raw`` is valid, else None.

        Returns ``None`` for missing keys, empty strings, and unknown
        keys alike; the API layer decides what HTTP code to use.
        The comparison is constant-time per stored key.
        """
        if not raw:
            return None
        candidate = _hash_key(raw)
        for key in self.keys:
            if hmac.compare_digest(candidate, key.key_hash):
                return key
        return None


def load_keys_from_env(env: dict[str, str] | None = None) -> APIKeyStore:
    """Build an :class:`APIKeyStore` from the standard env vars.

    Resolution order:

    1. ``VSTACK_API_KEYS`` -- comma-separated raw keys. Each becomes
       a key named ``key-0``, ``key-1``, etc.
    2. ``VSTACK_API_KEYS_FILE`` -- path to a newline-separated file
       of ``name=key`` pairs (anything without an ``=`` becomes a
       positional entry).

    The two sources merge. Empty result means no keys configured,
    which the API treats as "auth not enforced for this server."
    """
    env = env if env is not None else dict(os.environ)
    keys: list[APIKey] = []

    raw_list = env.get(DEFAULT_API_KEYS_ENV) or ""
    for idx, item in enumerate(_split_env_list(raw_list)):
        if "=" in item:
            name, value = item.split("=", 1)
        else:
            name, value = f"key-{idx}", item
        if value:
            keys.append(APIKey.from_raw(name=name, raw=value))

    path_str = env.get(DEFAULT_API_KEYS_FILE_ENV)
    if path_str:
        path = Path(path_str).expanduser()
        if path.exists():
            for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    name, value = line.split("=", 1)
                else:
                    name, value = f"file-key-{idx}", line
                if value:
                    keys.append(APIKey.from_raw(name=name, raw=value))
        else:
            logger.warning("VSTACK_API_KEYS_FILE=%s does not exist; ignoring", path)

    return APIKeyStore(keys=keys)


def verify_api_key(raw: str | None, store: APIKeyStore) -> APIKey | None:
    """Convenience for ``store.verify(raw)`` with a more descriptive name."""
    return store.verify(raw)


def generate_api_key() -> str:
    """Return a fresh random key suitable for ``VSTACK_API_KEYS``.

    Produced via :func:`secrets.token_urlsafe(24)`, which yields a
    32-character URL-safe ASCII string with ~192 bits of entropy.
    """
    return secrets.token_urlsafe(24)


# ----------------------------------------------------------------------
# internals
# ----------------------------------------------------------------------


def _hash_key(raw: str) -> bytes:
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _split_env_list(raw: str) -> Iterable[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]
