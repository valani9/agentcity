"""File-backed telemetry sink that appends one JSONL line per LLM call."""

from __future__ import annotations

import dataclasses
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vstack.aar import TelemetryEvent, TelemetrySink, set_default_sink
from vstack.memory import get_analytics_dir

logger = logging.getLogger(__name__)

DEFAULT_FILENAME = "telemetry.jsonl"


class FileTelemetrySink(TelemetrySink):
    """A :class:`vstack.aar.TelemetrySink` that appends to a JSONL file.

    Thread-safe under the typical multi-pattern call pattern (one
    lock guards writes; analyzers don't fan out massively in
    parallel within a single process).
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (get_analytics_dir() / DEFAULT_FILENAME)
        self._lock = threading.Lock()

    def record(self, event: TelemetryEvent) -> None:
        payload = self._serialize(event)
        try:
            # Lock the JSONL file via the cross-process advisory lock
            # so concurrent vstack processes can't interleave bytes
            # on the same line. The in-process `_lock` is still held
            # under that to guard the per-process file handle.
            from vstack.memory._fs_atomic import append_locked

            with self._lock:
                with append_locked(self.path) as f:
                    f.write(json.dumps(payload))
                    f.write("\n")
        except OSError as e:  # pragma: no cover - filesystem failures are rare
            logger.warning("FileTelemetrySink: failed to write event: %s", e)

    @staticmethod
    def _serialize(event: TelemetryEvent) -> dict[str, Any]:
        payload = dataclasses.asdict(event)
        ts = payload.get("timestamp")
        if isinstance(ts, datetime):
            payload["timestamp"] = ts.astimezone(timezone.utc).isoformat()
        elif ts is None:
            payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        return payload


def enable_file_telemetry(path: Path | None = None) -> FileTelemetrySink:
    """Install :class:`FileTelemetrySink` as the default vstack sink.

    Call once at startup. Every pattern's ``record_llm_call`` invocation
    will then flow through this sink in addition to any previously
    registered one (see :func:`vstack.aar.set_default_sink`).
    """
    sink = FileTelemetrySink(path=path)
    set_default_sink(sink)
    return sink
