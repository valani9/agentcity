"""Atomic-write + file-lock helpers used by the persistent stores.

The learning store, telemetry sink, config.json, and baselines all
share the same failure mode under concurrent processes:

* Two `vstack-config set` runs racing on `config.json` — last write
  wins, with the chance of a partial file if the loser is killed
  mid-write.
* Two analyzer processes appending to `learnings.jsonl` —
  interleaved bytes on POSIX kernels older than the per-process
  `O_APPEND` guarantee was clarified.
* A `vstack-analytics` reader iterating the JSONL while the sink is
  appending — partial-line decoding errors.

This module ships two primitives:

* :func:`atomic_write_text` / :func:`atomic_write_bytes` — write
  via tmp-file + ``os.replace`` so the destination is never
  half-written.
* :class:`FileLock` — POSIX advisory lock with a timeout. Uses
  ``fcntl.flock`` on Unix and ``msvcrt.locking`` on Windows.

Both are dependency-free (stdlib only). The performance overhead is
<1ms per call on local disks.
"""

from __future__ import annotations

import contextlib
import errno
import os
import tempfile
import time
from pathlib import Path
from typing import IO, Any, Iterator

# fcntl is POSIX-only; on Windows we use msvcrt. Both modules are
# stdlib so we don't need install-time guards; we just need runtime
# guards because exactly one of the two will import on any given
# platform.
fcntl: Any
msvcrt: Any
try:
    import fcntl as _fcntl

    fcntl = _fcntl
    _HAVE_FCNTL = True
except ImportError:
    fcntl = None
    _HAVE_FCNTL = False

try:
    import msvcrt as _msvcrt

    msvcrt = _msvcrt
    _HAVE_MSVCRT = True
except ImportError:
    msvcrt = None
    _HAVE_MSVCRT = False


class FileLockTimeout(TimeoutError):
    """Raised when :class:`FileLock` couldn't acquire within the timeout."""


def atomic_write_text(path: Path | str, data: str, *, encoding: str = "utf-8") -> None:
    """Atomically replace ``path`` with ``data``.

    Writes to a tempfile in the same directory + ``os.replace``-s
    over the destination. Crash-safe: a partial write never lands
    at the destination path.
    """
    atomic_write_bytes(path, data.encode(encoding))


def atomic_write_bytes(path: Path | str, data: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=target.name + ".",
        suffix=".tmp",
        dir=str(target.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # fsync not supported (e.g. on some filesystems);
                # the os.replace below is the durability guarantee
                # we actually need for correctness.
                pass
        os.replace(tmp_path, target)
    except Exception:
        # Clean up the tempfile on any failure path.
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


@contextlib.contextmanager
def append_locked(path: Path | str, *, timeout: float = 5.0) -> Iterator[IO[Any]]:
    """Open ``path`` in append mode under an exclusive advisory lock.

    Concurrent processes calling this on the same path serialize
    their writes; reads via :func:`iter_lines_consistent` see only
    fully-written lines.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fh = target.open("a", encoding="utf-8")
    try:
        _acquire_exclusive(fh, timeout=timeout)
        try:
            yield fh
            fh.flush()
            with contextlib.suppress(OSError):
                os.fsync(fh.fileno())
        finally:
            _release(fh)
    finally:
        fh.close()


@contextlib.contextmanager
def shared_read_lock(path: Path | str, *, timeout: float = 5.0) -> Iterator[IO[Any]]:
    """Open ``path`` for reading under a shared advisory lock.

    Multiple shared readers run concurrently; an active exclusive
    writer blocks readers and vice versa.
    """
    target = Path(path)
    fh = target.open("r", encoding="utf-8")
    try:
        _acquire_shared(fh, timeout=timeout)
        try:
            yield fh
        finally:
            _release(fh)
    finally:
        fh.close()


class FileLock:
    """A standalone advisory lock with a context-manager API.

    Use this when you need to gate a logical operation on a sentinel
    file (e.g. "no two processes regenerating canonical baselines at
    once"). The lock file persists; it's the LOCK that's exclusive,
    not the file's content.
    """

    def __init__(self, path: Path | str, *, timeout: float = 5.0) -> None:
        self.path = Path(path)
        self.timeout = timeout
        self._fh: IO[Any] | None = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a+", encoding="utf-8")
        try:
            _acquire_exclusive(self._fh, timeout=self.timeout)
        except FileLockTimeout:
            self._fh.close()
            self._fh = None
            raise
        return self

    def __exit__(self, *exc: object) -> None:
        if self._fh is not None:
            with contextlib.suppress(Exception):
                _release(self._fh)
            self._fh.close()
            self._fh = None


# ----------------------------------------------------------------------
# Platform abstractions
# ----------------------------------------------------------------------


def _acquire_exclusive(fh: IO[Any], *, timeout: float) -> None:
    _acquire(fh, exclusive=True, timeout=timeout)


def _acquire_shared(fh: IO[Any], *, timeout: float) -> None:
    _acquire(fh, exclusive=False, timeout=timeout)


def _acquire(fh: IO[Any], *, exclusive: bool, timeout: float) -> None:
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        try:
            if _HAVE_FCNTL:
                flag = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                fcntl.flock(fh.fileno(), flag | fcntl.LOCK_NB)
                return
            if _HAVE_MSVCRT:
                # Windows doesn't have a shared-vs-exclusive distinction
                # in the way fcntl does; LK_NBLCK is exclusive.
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                return
            # No locking primitive available -- accept the risk. Tests
            # on these platforms still exercise correctness of the
            # serial path.
            return
        except (BlockingIOError, OSError) as e:
            # EWOULDBLOCK / EAGAIN on fcntl; permission-denied on
            # msvcrt also surfaces here.
            if e.errno not in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
                raise
            if time.monotonic() >= deadline:
                raise FileLockTimeout(
                    f"Failed to acquire lock on {fh.name} within {timeout}s"
                ) from e
            time.sleep(0.05)


def _release(fh: IO[Any]) -> None:
    try:
        if _HAVE_FCNTL:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        elif _HAVE_MSVCRT:
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
