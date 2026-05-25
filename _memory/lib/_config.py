"""User-preference config persisted at ``~/.vstack/config.json``.

A small typed wrapper over a flat dict. The schema is intentionally
permissive in v0 -- ``KNOWN_KEYS`` documents the validated set but
unknown keys are stored verbatim so plugins and downstream skills can
piggyback. Strict validation will land alongside the first plugin
spec; until then, the get/set/list flow is enough.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._home import get_config_path


class ConfigError(RuntimeError):
    """Raised on a malformed ``config.json`` or invalid key/value."""


# A typed lookup of the supported user preferences. Each entry is
# (default, one-line description). New keys add an entry here AND a
# section in the ``vstack-config list`` help output below.
KNOWN_KEYS: dict[str, tuple[Any, str]] = {
    "default_mode": (
        "standard",
        "Default pipeline mode for analyzers (quick / standard / forensic).",
    ),
    "default_model": (
        "claude-sonnet-4-6",
        "Default LLM model id passed to analyzers when --model is omitted.",
    ),
    "telemetry": (
        "off",
        "Telemetry sink. 'off' disables; 'memory' uses InMemoryTelemetrySink; "
        "'file' writes JSONL to ~/.vstack/analytics/telemetry.jsonl.",
    ),
    "log_level": ("WARNING", "Default Python logging level for vstack CLIs."),
    "preferred_llm": (
        "auto",
        "Preferred LLM provider for vstack-mcp / vstack-api ("
        "'anthropic' | 'openai' | 'ollama' | 'auto').",
    ),
    "api_host": ("127.0.0.1", "Default bind host for vstack-api serve."),
    "api_port": ("8000", "Default bind port for vstack-api serve."),
    "skills_install_path": (
        "~/.claude/skills/vstack",
        "Where vstack-config install-skills copies the skill set.",
    ),
}


@dataclass
class Config:
    """Container for the persistent user preferences.

    Methods on this class are pure -- they never touch disk. Use
    :func:`load_config` / :func:`save_config` for IO.
    """

    values: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Return ``key`` or its ``KNOWN_KEYS`` default or the supplied default."""
        if key in self.values:
            return self.values[key]
        if key in KNOWN_KEYS:
            return KNOWN_KEYS[key][0]
        return default

    def set(self, key: str, value: Any) -> None:
        if not isinstance(key, str) or not key:
            raise ConfigError(f"Invalid config key: {key!r}")
        self.values[key] = value

    def delete(self, key: str) -> bool:
        if key in self.values:
            del self.values[key]
            return True
        return False

    def as_dict(self) -> dict[str, Any]:
        """Return a defensive copy of the underlying dict."""
        return dict(self.values)

    def merged_with_defaults(self) -> dict[str, Any]:
        """Return values overlaid on top of ``KNOWN_KEYS`` defaults.

        Useful for callers that want a complete snapshot -- the dict
        always has every known key resolved.
        """
        merged: dict[str, Any] = {k: v[0] for k, v in KNOWN_KEYS.items()}
        merged.update(self.values)
        return merged


def load_config(path: Path | None = None) -> Config:
    """Read the config file (returning an empty :class:`Config` if absent)."""
    path = path or get_config_path()
    if not path.exists():
        return Config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"Failed to parse {path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a JSON object, got {type(data).__name__}")
    return Config(values=data)


def save_config(config: Config, path: Path | None = None) -> None:
    """Persist ``config`` to ``path`` (defaults to ``~/.vstack/config.json``)."""
    path = path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.values, indent=2, sort_keys=True), encoding="utf-8")


def get_key(key: str, path: Path | None = None) -> Any:
    """Convenience for ``load_config().get(key)``."""
    return load_config(path).get(key)


def set_key(key: str, value: Any, path: Path | None = None) -> None:
    """Convenience for the round-trip ``load + mutate + save``."""
    config = load_config(path)
    config.set(key, value)
    save_config(config, path)


def delete_key(key: str, path: Path | None = None) -> bool:
    """Convenience for the round-trip ``load + delete + save``.

    Returns ``True`` if the key was present (and is now gone).
    """
    config = load_config(path)
    removed = config.delete(key)
    if removed:
        save_config(config, path)
    return removed


def list_config(path: Path | None = None) -> dict[str, Any]:
    """Return the merged snapshot used by ``vstack-config list``."""
    return load_config(path).merged_with_defaults()
