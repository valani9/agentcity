"""vstack.memory -- standard local data directory for vstack.

Mirrors the convention used by gstack at ``~/.gstack/``: a single
top-level directory under the user's home where vstack stores
calibration baselines, session history, and user preferences. Every
subsystem that needs to persist state outside the wheel writes
through this module so paths stay consistent across patterns and
honor the ``VSTACK_HOME`` override.

Layout
------

::

    ~/.vstack/
    +-- baselines/         # per-pattern calibration JSON (relocated lazily)
    +-- sessions/          # session-history JSONL (one per run, optional)
    +-- config.json        # user preferences (vstack-config get/set/list)
    +-- analytics/         # opt-in telemetry sink output (off by default)

Environment overrides
---------------------

``VSTACK_HOME``
    Absolute path to override the default ``~/.vstack/``.

``XDG_DATA_HOME`` is NOT consulted. Linux XDG conformance is a
follow-up; keeping the path predictable across platforms matters more
in v0.

Programmatic surface
--------------------

* :func:`get_home` -- resolved root directory (creates if missing)
* :func:`get_baselines_dir` -- ``~/.vstack/baselines/``
* :func:`get_sessions_dir` -- ``~/.vstack/sessions/``
* :func:`get_analytics_dir` -- ``~/.vstack/analytics/``
* :func:`get_config_path` -- ``~/.vstack/config.json``
* :class:`Config` -- typed wrapper over ``config.json``
* :func:`load_config`, :func:`save_config`
* :func:`baseline_path_for` -- canonical path per pattern name

CLI
---

::

    vstack-config get <key>
    vstack-config set <key> <value>
    vstack-config list
    vstack-config path  # prints VSTACK_HOME
"""

from ._fs_atomic import (
    FileLock,
    FileLockTimeout,
    append_locked,
    atomic_write_bytes,
    atomic_write_text,
    shared_read_lock,
)
from ._home import (
    DEFAULT_HOME_ENV,
    baseline_path_for,
    get_analytics_dir,
    get_baselines_dir,
    get_config_path,
    get_home,
    get_sessions_dir,
)
from ._config import (
    Config,
    ConfigError,
    KNOWN_KEYS,
    delete_key,
    get_key,
    list_config,
    load_config,
    save_config,
    set_key,
)

__all__ = [
    "DEFAULT_HOME_ENV",
    "baseline_path_for",
    "get_analytics_dir",
    "get_baselines_dir",
    "get_config_path",
    "get_home",
    "get_sessions_dir",
    "Config",
    "ConfigError",
    "KNOWN_KEYS",
    "delete_key",
    "get_key",
    "list_config",
    "load_config",
    "save_config",
    "set_key",
    "FileLock",
    "FileLockTimeout",
    "append_locked",
    "atomic_write_bytes",
    "atomic_write_text",
    "shared_read_lock",
]

__version__ = "0.3.0"
